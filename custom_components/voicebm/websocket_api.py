"""WebSocket API + audio view for the VoiceBM speaker-management panel.

The panel (a native HA web component) talks to these over Home Assistant's
authenticated WebSocket connection — so there's no iframe, no separate origin,
no auth/HTTPS pitfalls. The backend:

  * READS the speaker gallery and pending list straight off disk. The engine
    add-on stores them under /share/voicebm, which HA Core sees directly.
  * WRITES (enroll / rename / delete / merge) by publishing to the engine's
    EXISTING MQTT command topics. The engine already handles all of these and
    republishes afterwards, so no engine code changes are needed.

Everything here is best-effort and defensive: a missing gallery dir yields an
empty list rather than an error.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

import voluptuous as vol
from datetime import timedelta

from homeassistant.components import mqtt, websocket_api
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback

from .const import (
    AUDIO_VIEW_URL,
    CONF_GALLERY_DIR,
    DEFAULT_GALLERY_DIR,
    DOMAIN,
    TOPIC_MERGE_EXECUTE_TRIGGER,
    TOPIC_MERGE_NAME_SET,
    TOPIC_PENDING_ENROLL,
    TOPIC_SAMPLES_DEL_REQ,
    TOPIC_SAMPLES_DEL_RES,
    TOPIC_SAMPLES_LIST_REQ,
    TOPIC_SAMPLES_LIST_RES,
    topic_delete,
    topic_enable_delete_set,
    topic_merge_tag_set,
    topic_transform_execute,
    topic_transform_name_set,
)

_LOGGER = logging.getLogger(__name__)


def _gallery_dir(hass: HomeAssistant) -> Path:
    entry = next(iter(hass.data.get(DOMAIN, {}).values()), None)
    base = DEFAULT_GALLERY_DIR
    if entry is not None:
        base = {**entry.data, **entry.options}.get(CONF_GALLERY_DIR, DEFAULT_GALLERY_DIR)
    return Path(base)


def _read_enrolled(base: Path) -> list[dict]:
    enroll_dir = base / "enroll"
    people: list[dict] = []
    if not enroll_dir.is_dir():
        return people
    for person_dir in sorted(enroll_dir.iterdir()):
        if not person_dir.is_dir():
            continue
        pid = person_dir.name
        meta_file = person_dir / "metadata.json"
        display_name = pid.replace("_", " ").title()
        sample_count = 0
        if meta_file.is_file():
            try:
                meta = json.loads(meta_file.read_text())
                display_name = meta.get("display_name", display_name)
                sample_count = len(meta.get("samples", []))
            except Exception:
                pass
        people.append(
            {"person_id": pid, "display_name": display_name, "sample_count": sample_count}
        )
    return people


def _read_pending(base: Path) -> list[dict]:
    pending_file = base / "pending_active" / "pending.json"
    if not pending_file.is_file():
        return []
    try:
        buf = json.loads(pending_file.read_text())
    except Exception:
        return []
    out = []
    for e in buf:
        cid = e.get("id")
        if not cid:
            continue
        # Only show rows whose audio still exists on disk — after an enroll the
        # engine MOVES the wav into the gallery, and the buffer entry can
        # briefly outlive it; a row without its wav is just a dead 0:00 player.
        wav = base / "pending_active" / "recordings" / f"{cid}.wav"
        if not wav.is_file() and not (base / "pending_active" / f"{cid}.wav").is_file():
            continue
        out.append(
            {
                "id": cid,
                "timestamp": e.get("timestamp"),
                "source": e.get("source", ""),
            }
        )
    # newest first
    out.sort(key=lambda x: x.get("timestamp") or 0, reverse=True)
    return out


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the WS commands and the audio view."""
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_enroll)
    websocket_api.async_register_command(hass, ws_rename)
    websocket_api.async_register_command(hass, ws_delete)
    websocket_api.async_register_command(hass, ws_merge)
    websocket_api.async_register_command(hass, ws_list_samples)
    websocket_api.async_register_command(hass, ws_delete_samples)
    hass.http.register_view(VoiceBMPendingAudioView())


# --------------------------------------------------------------------------- #
#  READ
# --------------------------------------------------------------------------- #
@websocket_api.websocket_command({vol.Required("type"): "voicebm/list"})
@websocket_api.async_response
async def ws_list(hass, connection, msg):
    base = _gallery_dir(hass)
    enrolled = await hass.async_add_executor_job(_read_enrolled, base)
    pending = await hass.async_add_executor_job(_read_pending, base)
    for entry in pending:
        try:
            entry["audio_url"] = async_sign_path(
                hass, f"{AUDIO_VIEW_URL}/{entry['id']}", timedelta(minutes=15)
            )
        except Exception:  # noqa: BLE001 — fall back to the plain path
            pass
    connection.send_result(msg["id"], {"enrolled": enrolled, "pending": pending})


# --------------------------------------------------------------------------- #
#  WRITE (all via the engine's existing MQTT topics)
# --------------------------------------------------------------------------- #
@websocket_api.websocket_command(
    {
        vol.Required("type"): "voicebm/enroll",
        vol.Required("pending_id"): str,
        vol.Required("display_name"): str,
    }
)
@websocket_api.async_response
async def ws_enroll(hass, connection, msg):
    name = msg["display_name"].strip()
    person_id = name.lower().replace(" ", "_")
    payload = json.dumps(
        {"id": msg["pending_id"], "person_id": person_id, "display_name": name}
    )
    await mqtt.async_publish(hass, TOPIC_PENDING_ENROLL, payload, qos=1)
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "voicebm/rename",
        vol.Required("person_id"): str,
        vol.Required("new_name"): str,
    }
)
@websocket_api.async_response
async def ws_rename(hass, connection, msg):
    pid = msg["person_id"]
    await mqtt.async_publish(hass, topic_transform_name_set(pid), msg["new_name"].strip(), qos=1)
    await asyncio.sleep(0.2)
    await mqtt.async_publish(hass, topic_transform_execute(pid), "PRESS", qos=1)
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {vol.Required("type"): "voicebm/delete", vol.Required("person_id"): str}
)
@websocket_api.async_response
async def ws_delete(hass, connection, msg):
    pid = msg["person_id"]
    # enable the safety switch first, then trigger delete
    await mqtt.async_publish(hass, topic_enable_delete_set(pid), "ON", qos=1)
    await asyncio.sleep(0.2)
    await mqtt.async_publish(hass, topic_delete(pid), "PRESS", qos=1)
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "voicebm/merge",
        vol.Required("person_ids"): [str],
        vol.Required("new_name"): str,
    }
)
@websocket_api.async_response
async def ws_merge(hass, connection, msg):
    pids = msg["person_ids"]
    if len(pids) < 2:
        connection.send_error(msg["id"], "invalid", "Select at least two identities to merge")
        return
    for pid in pids:
        await mqtt.async_publish(hass, topic_merge_tag_set(pid), "ON", qos=1)
        await asyncio.sleep(0.1)
    await mqtt.async_publish(hass, TOPIC_MERGE_NAME_SET, msg["new_name"].strip(), qos=1)
    await asyncio.sleep(0.2)
    await mqtt.async_publish(hass, TOPIC_MERGE_EXECUTE_TRIGGER, "PRESS", qos=1)
    connection.send_result(msg["id"], {"ok": True})


# --------------------------------------------------------------------------- #
#  Per-sample management — round-trips through the engine's sample_manager
# --------------------------------------------------------------------------- #
async def _sample_request(hass, req_topic, res_topic, payload, match_person, timeout=6.0):
    """Publish a request and await the matching response for this person.

    The engine's sample_manager answers list/delete requests on a response
    topic; we subscribe once, publish, and wait for the reply.
    """
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()

    @callback
    def _on_msg(msg):
        if fut.done():
            return
        try:
            data = json.loads(msg.payload)
        except Exception:
            return
        if data.get("person_id") == match_person:
            fut.set_result(data)

    unsub = await mqtt.async_subscribe(hass, res_topic, _on_msg)
    try:
        await mqtt.async_publish(hass, req_topic, json.dumps(payload), qos=1)
        return await asyncio.wait_for(fut, timeout=timeout)
    finally:
        unsub()


@websocket_api.websocket_command(
    {vol.Required("type"): "voicebm/list_samples", vol.Required("person_id"): str}
)
@websocket_api.async_response
async def ws_list_samples(hass, connection, msg):
    pid = msg["person_id"]
    try:
        data = await _sample_request(
            hass, TOPIC_SAMPLES_LIST_REQ, TOPIC_SAMPLES_LIST_RES, {"person_id": pid}, pid
        )
        connection.send_result(msg["id"], data)
    except asyncio.TimeoutError:
        connection.send_error(
            msg["id"], "timeout",
            "No response from the VoiceBM engine (is the add-on running?)",
        )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "voicebm/delete_samples",
        vol.Required("person_id"): str,
        vol.Required("event_ids"): [str],
    }
)
@websocket_api.async_response
async def ws_delete_samples(hass, connection, msg):
    pid = msg["person_id"]
    try:
        data = await _sample_request(
            hass,
            TOPIC_SAMPLES_DEL_REQ,
            TOPIC_SAMPLES_DEL_RES,
            {"person_id": pid, "event_ids": msg["event_ids"]},
            pid,
            timeout=10.0,
        )
        connection.send_result(msg["id"], data)
    except asyncio.TimeoutError:
        connection.send_error(
            msg["id"], "timeout",
            "No response from the VoiceBM engine (is the add-on running?)",
        )


# --------------------------------------------------------------------------- #
#  Pending-clip audio (authenticated view, for playback in the panel)
# --------------------------------------------------------------------------- #
class VoiceBMPendingAudioView(HomeAssistantView):
    """Serve a pending clip's WAV. Auth is required (default), so only
    logged-in HA users can fetch it."""

    url = AUDIO_VIEW_URL + "/{clip_id}"
    name = "api:voicebm:pending_audio"
    requires_auth = True

    async def get(self, request, clip_id: str):
        from aiohttp import web

        hass = request.app["hass"]
        base = _gallery_dir(hass)
        # basic id sanitation
        if "/" in clip_id or ".." in clip_id:
            return web.Response(status=400)
        # pending clips are stored under pending_active/ (a couple of known layouts)
        # Engine stores pending clips at pending_active/recordings/<id>.wav
        # (verified against voicebm_stt_service.add_to_pending_buffer).
        candidates = [
            base / "pending_active" / "recordings" / f"{clip_id}.wav",
            base / "pending_active" / f"{clip_id}.wav",
        ]
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            return web.Response(status=404)
        data = await hass.async_add_executor_job(path.read_bytes)
        return web.Response(body=data, content_type="audio/wav")
