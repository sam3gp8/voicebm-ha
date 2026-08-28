"""Speech-to-text entity for VoiceBM.

This is the seam that makes the whole thing work without any manual Wyoming
wiring: it registers as a native Home Assistant STT entity, so it appears
directly in the Assist pipeline's "Speech-to-text" dropdown. Pick it, and:

  * transcription is DELEGATED to the user's existing Whisper STT entity
    (their already-working, GPU-accelerated add-on) — we don't run a second
    ASR and we don't re-enter any endpoints;
  * in parallel, the same utterance audio is handed to VoiceBM's identity
    engine (the add-on) via a shared WAV file + an MQTT analyze_request, so
    VoiceBM identifies the speaker and publishes it for JARVIS / Ollama.

Crucially, transcription NEVER depends on the identity path. If the VoiceBM
add-on is down, MQTT is unavailable, or the share dir isn't writable, we still
return Whisper's transcript. That is what permanently fixes "lost voice
satellites": choosing this engine can't break your pipeline, because it always
falls through to the transcript.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
import wave
from collections.abc import AsyncIterable

from homeassistant.components import stt
from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BACKEND_STT,
    CONF_IDENTITY_INJECT,
    CONF_IDENTITY_WAIT_MS,
    CONF_LANGUAGES,
    CONF_SHARE_DIR,
    DEFAULT_IDENTITY_INJECT,
    DEFAULT_IDENTITY_WAIT_MS,
    DEFAULT_LANGUAGES,
    DEFAULT_SHARE_DIR,
    DOMAIN,
    NON_SPEAKER_VALUES,
    TOPIC_ACTIVE_SPEAKER,
    TOPIC_ANALYZE_REQUEST,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VoiceBM STT entity from a config entry."""
    async_add_entities([VoiceBMSTTEntity(hass, config_entry)])


class VoiceBMSTTEntity(SpeechToTextEntity):
    """VoiceBM STT: Whisper transcription (delegated) + speaker identity."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_name = "VoiceBM (Whisper + Identity)"
        self._attr_unique_id = f"{entry.entry_id}_stt"
        opts = {**entry.data, **entry.options}
        self._backend_stt: str = opts[CONF_BACKEND_STT]
        self._languages: list[str] = opts.get(CONF_LANGUAGES, DEFAULT_LANGUAGES)
        self._identity_inject: bool = opts.get(CONF_IDENTITY_INJECT, DEFAULT_IDENTITY_INJECT)
        self._identity_wait_ms: int = opts.get(CONF_IDENTITY_WAIT_MS, DEFAULT_IDENTITY_WAIT_MS)
        self._share_dir: str = opts.get(CONF_SHARE_DIR, DEFAULT_SHARE_DIR)

    # ---- capability properties (must mirror what the backend Whisper accepts)
    @property
    def supported_languages(self) -> list[str]:
        """Mirror the backend's languages so Assist's per-pipeline language
        filter matches whenever the backend would match. Hardcoding this (e.g.
        to ["en"]) would silently hide this engine from any non-English
        pipeline even though the delegated Whisper supports it."""
        try:
            backend = stt.async_get_speech_to_text_entity(self.hass, self._backend_stt)
            if backend is not None and backend.supported_languages:
                return backend.supported_languages
        except Exception:  # noqa: BLE001 — fall back to configured list
            pass
        return self._languages

    @property
    def supported_formats(self) -> list[AudioFormats]:
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        return [AudioChannels.CHANNEL_MONO]

    # ---- the pipeline calls this per utterance
    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Transcribe via the backend Whisper; identify the speaker in parallel.

        The audio stream can only be consumed once, so we buffer it, then (a)
        replay it into the backend STT entity for the transcript and (b) write
        it to the shared folder and fire the VoiceBM identity request. (b) is
        best-effort and never blocks or fails (a).
        """
        # Buffer the whole utterance once.
        chunks: list[bytes] = []
        async for chunk in stream:
            chunks.append(chunk)
        audio = b"".join(chunks)

        # Kick off identity (best-effort, fully guarded).
        request_id = str(uuid.uuid4())
        utt_start = time.time()
        try:
            wav_path = await self.hass.async_add_executor_job(
                self._write_wav, audio, metadata, request_id
            )
            payload = json.dumps(
                {"request_id": request_id, "audio_path": wav_path, "timestamp": time.time()}
            )
            from homeassistant.components import mqtt

            await mqtt.async_publish(self.hass, TOPIC_ANALYZE_REQUEST, payload, qos=1)
            # INFO on purpose while this stack is in validation: one line per
            # utterance proving the identity leg fired, matchable against the
            # engine's own "Analysis request:" log line.
            _LOGGER.info("VoiceBM identity request published for %s", wav_path)
        except Exception as err:  # never let identity break transcription
            _LOGGER.warning("VoiceBM identity request failed (continuing): %s", err)

        # Delegate transcription to the user's existing Whisper STT entity.
        text = await self._transcribe_with_backend(metadata, audio)
        if text is None:
            return SpeechResult(None, SpeechResultState.ERROR)

        # Optionally fold the identified name into the transcript.
        if self._identity_inject:
            name = await self._await_identity(utt_start)
            if name:
                text = f"{name}: {text}"

        return SpeechResult(text, SpeechResultState.SUCCESS)

    # ---- transcription delegation --------------------------------------
    async def _transcribe_with_backend(
        self, metadata: SpeechMetadata, audio: bytes
    ) -> str | None:
        backend = stt.async_get_speech_to_text_entity(self.hass, self._backend_stt)
        if backend is None:
            _LOGGER.error(
                "VoiceBM backend STT entity '%s' not found — is your Whisper add-on/"
                "integration set up? Falling back to no transcript.",
                self._backend_stt,
            )
            return None

        async def _replay() -> AsyncIterable[bytes]:
            # Feed the buffered audio back as a stream in reasonable chunks.
            step = 4096
            for i in range(0, len(audio), step):
                yield audio[i : i + step]

        try:
            result = await backend.async_process_audio_stream(metadata, _replay())
        except Exception as err:
            _LOGGER.error("VoiceBM backend transcription failed: %s", err)
            return None

        if result is None or result.result != SpeechResultState.SUCCESS:
            _LOGGER.warning("VoiceBM backend returned no successful transcript")
            return result.text if result else None
        return result.text or ""

    # ---- identity ------------------------------------------------------
    def _write_wav(
        self, audio: bytes, metadata: SpeechMetadata, request_id: str
    ) -> str:
        """Write the utterance WAV to the shared dir (blocking file I/O only —
        runs in an executor). The path is under /share, which the engine add-on
        also mounts, so its STT service can read exactly this file. The MQTT
        publish happens back on the event loop via async_publish."""
        os.makedirs(self._share_dir, exist_ok=True)
        wav_path = os.path.join(self._share_dir, f"stt_{int(time.time()*1000)}_{request_id[:8]}.wav")
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(int(metadata.sample_rate))
            wf.writeframes(audio)
        return wav_path

    async def _await_identity(self, utt_start: float) -> str | None:
        """Wait briefly for VoiceBM's verdict on the active_speaker state.

        We read the add-on's own MQTT-discovery sensor rather than
        re-subscribing, so this reflects exactly what JARVIS/Ollama see. Only
        used when identity_inject is on; otherwise identity flows purely via
        the sensor and this is skipped.
        """
        # sensor.voicebm_active_speaker is published by the add-on
        entity_id = "sensor.voicebm_active_speaker"
        deadline = time.time() + (self._identity_wait_ms / 1000.0)
        while time.time() < deadline:
            state = self.hass.states.get(entity_id)
            if state is not None and state.last_changed.timestamp() >= utt_start:
                val = state.state
                if val not in NON_SPEAKER_VALUES:
                    return val
                return None
            await asyncio.sleep(0.05)
        return None
