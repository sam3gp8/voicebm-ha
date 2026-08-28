"""Best-effort supervisor for the VoiceBM engine add-on.

Removes the last manual setup steps: instead of asking the user to open the
add-on and set `stt.mode: integration` and make sure it's running, the
integration does it — the same companion-add-on pattern Z-Wave JS and Matter
use (homeassistant.components.hassio.AddonManager).

Everything here is strictly best-effort:
  * runs as a background task after setup, never blocks or fails the entry;
  * only acts when running under the Supervisor (HAOS/Supervised);
  * if the add-on is missing, it raises a Repairs issue with instructions
    (an integration cannot copy files into /addons for you) and clears the
    issue automatically once the add-on appears.
"""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Local add-ons get the "local_" prefix from the Supervisor.
ENGINE_ADDON_SLUG = "local_voicebm"
ENGINE_ADDON_NAME = "VoiceBM engine"
ISSUE_ENGINE_MISSING = "engine_addon_missing"


async def async_ensure_engine(hass: HomeAssistant) -> None:
    """Detect/configure/start the engine add-on. Never raises."""
    try:
        from homeassistant.components.hassio import is_hassio
        from homeassistant.components.hassio.addon_manager import (
            AddonManager,
            AddonState,
        )
    except ImportError:
        _LOGGER.debug("hassio component unavailable; skipping engine check")
        return

    try:
        if not is_hassio(hass):
            _LOGGER.debug("Not a Supervisor install; skipping engine management")
            return

        manager = AddonManager(hass, _LOGGER, ENGINE_ADDON_NAME, ENGINE_ADDON_SLUG)
        info = await manager.async_get_addon_info()

        if info.state == AddonState.NOT_INSTALLED:
            _LOGGER.warning(
                "VoiceBM engine add-on (%s) is not installed — identity will not "
                "work until it is. See the Repairs panel for instructions.",
                ENGINE_ADDON_SLUG,
            )
            ir.async_create_issue(
                hass,
                DOMAIN,
                ISSUE_ENGINE_MISSING,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_ENGINE_MISSING,
                learn_more_url="https://github.com/sam3gp8/voicebm-ha",
            )
            return

        # Add-on exists — clear any stale "missing" issue.
        ir.async_delete_issue(hass, DOMAIN, ISSUE_ENGINE_MISSING)

        # Ensure stt.mode = integration (merge into existing options).
        opts = dict(info.options or {})
        stt_opts = dict(opts.get("stt") or {})
        needs_mode = stt_opts.get("mode") != "integration"
        if needs_mode:
            stt_opts["mode"] = "integration"
            opts["stt"] = stt_opts
            _LOGGER.info(
                "Setting VoiceBM engine add-on stt.mode=integration (was %r)",
                info.options.get("stt", {}).get("mode") if info.options else None,
            )
            await manager.async_set_addon_options(opts)

        if info.state == AddonState.RUNNING:
            if needs_mode:
                _LOGGER.info("Restarting engine add-on to apply integration mode")
                await manager.async_restart_addon()
        else:
            _LOGGER.info("Starting VoiceBM engine add-on")
            await manager.async_start_addon()

    except Exception as err:  # noqa: BLE001 — best-effort by design
        _LOGGER.warning(
            "Could not verify/configure the VoiceBM engine add-on (continuing; "
            "transcription is unaffected): %s",
            err,
        )
