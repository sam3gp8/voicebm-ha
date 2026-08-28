"""The VoiceBM integration — Whisper transcription + local speaker identity.

The heavy voice biometrics run in the headless VoiceBM engine add-on; this
integration is the Home-Assistant-native half:
  * a native STT entity that transcribes through your existing Whisper and adds
    speaker identity on the same audio;
  * a native speaker-management panel (served through HA, so it works over
    HTTPS with no iframe) that drives the engine's existing MQTT operations.

Built on the open-source VoiceBM by its original creator
(github.com/cybericebyte/VoiceBM); this adds the HA integration layer.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import engine, panel, websocket_api
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.STT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VoiceBM from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register the speaker-management panel + its WebSocket API / audio view.
    websocket_api.async_register(hass)
    await panel.async_register_panel(hass)

    # Best-effort: make sure the engine add-on is configured + running
    # (never blocks setup; logs / raises a Repairs issue instead of failing).
    entry.async_create_background_task(
        hass, engine.async_ensure_engine(hass), name="voicebm_engine_check"
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            panel.async_unregister_panel(hass)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
