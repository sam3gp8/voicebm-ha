"""Config flow for VoiceBM.

Guided setup that does the wiring for the user: it discovers the existing STT
entities (their Whisper add-on/integration shows up here), lets them pick which
one VoiceBM should transcribe with, and confirms MQTT is available (the add-on
talks to this integration over MQTT). No endpoints or ports to type.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_BACKEND_STT,
    CONF_GALLERY_DIR,
    CONF_IDENTITY_INJECT,
    CONF_IDENTITY_WAIT_MS,
    CONF_SHARE_DIR,
    DEFAULT_GALLERY_DIR,
    DEFAULT_IDENTITY_INJECT,
    DEFAULT_IDENTITY_WAIT_MS,
    DEFAULT_SHARE_DIR,
    DOMAIN,
)


def _own_stt_entities(hass: HomeAssistant) -> list[str]:
    """STT entities that aren't ours (candidates to transcribe with)."""
    reg = er.async_get(hass)
    return [
        e.entity_id
        for e in reg.entities.values()
        if e.domain == "stt" and e.platform != DOMAIN
    ]


class VoiceBMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the VoiceBM config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single-instance setup: choose the transcription backend."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        candidates = _own_stt_entities(self.hass)

        if not candidates:
            # No other STT engine present — the user needs Whisper first.
            return self.async_abort(reason="no_backend_stt")

        if user_input is not None:
            return self.async_create_entry(
                title="VoiceBM (Whisper + Identity)",
                data={CONF_BACKEND_STT: user_input[CONF_BACKEND_STT]},
            )

        if len(candidates) == 1:
            # Exactly one other STT engine (the common case: just Whisper) —
            # nothing to ask; wire it up directly.
            return self.async_create_entry(
                title="VoiceBM (Whisper + Identity)",
                data={CONF_BACKEND_STT: candidates[0]},
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_BACKEND_STT): EntitySelector(
                    EntitySelectorConfig(domain="stt", include_entities=candidates)
                ),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VoiceBMOptionsFlow(config_entry)


class VoiceBMOptionsFlow(OptionsFlow):
    """Options: transcription backend + identity tuning."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        cur = {**self._entry.data, **self._entry.options}
        candidates = _own_stt_entities(self.hass)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BACKEND_STT, default=cur.get(CONF_BACKEND_STT)
                ): EntitySelector(
                    EntitySelectorConfig(domain="stt", include_entities=candidates)
                ),
                vol.Required(
                    CONF_IDENTITY_INJECT,
                    default=cur.get(CONF_IDENTITY_INJECT, DEFAULT_IDENTITY_INJECT),
                ): BooleanSelector(),
                vol.Required(
                    CONF_IDENTITY_WAIT_MS,
                    default=cur.get(CONF_IDENTITY_WAIT_MS, DEFAULT_IDENTITY_WAIT_MS),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=5000, step=100, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_SHARE_DIR,
                    default=cur.get(CONF_SHARE_DIR, DEFAULT_SHARE_DIR),
                ): str,
                vol.Required(
                    CONF_GALLERY_DIR,
                    default=cur.get(CONF_GALLERY_DIR, DEFAULT_GALLERY_DIR),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
