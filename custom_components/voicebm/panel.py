"""Register the VoiceBM speaker-management panel through HA's own frontend.

Modeled on the JARVIS-AIO panel_register pattern: the panel's JS is served from
a static path ON the HA server (async_register_static_paths), and registered as
a native web component via panel_custom (embed_iframe=False). Because everything
loads from the HA origin, it inherits HTTPS automatically and there is no
cross-origin iframe to be blocked — unlike pointing panel_iframe at the add-on's
:5000 dashboard over HTTP.
"""
from __future__ import annotations

import logging
import os

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import (
    PANEL_ICON,
    PANEL_JS_FILENAME,
    PANEL_STATIC_URL,
    PANEL_TITLE,
    PANEL_URL_PATH,
    PANEL_WEBCOMPONENT,
)

_LOGGER = logging.getLogger(__name__)


def _hash_file_sync(path: str) -> str:
    """Synchronous hash — MUST be called via the executor, never in the loop."""
    try:
        import hashlib

        with open(path, "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()[:10]
    except Exception:
        try:
            return str(int(os.path.getmtime(path)))
        except Exception:
            import time

            return str(int(time.time()))


async def async_register_panel(hass: HomeAssistant) -> bool:
    panel_dir = os.path.join(os.path.dirname(__file__), "frontend")
    js_path = os.path.join(panel_dir, PANEL_JS_FILENAME)
    if not os.path.isfile(js_path):
        _LOGGER.error("VoiceBM panel: JS not found at %s", js_path)
        return False

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_STATIC_URL, panel_dir, cache_headers=False)]
        )
    except RuntimeError:
        # already registered (entry reload) — fine
        pass

    # Hash the JS off-loop (blocking file read must not run in the event loop).
    cache_bust = await hass.async_add_executor_job(_hash_file_sync, js_path)
    module_url = f"{PANEL_STATIC_URL}/{PANEL_JS_FILENAME}?v={cache_bust}"
    try:
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
    except Exception:
        pass
    try:
        await panel_custom.async_register_panel(
            hass,
            webcomponent_name=PANEL_WEBCOMPONENT,
            frontend_url_path=PANEL_URL_PATH,
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            module_url=module_url,
            embed_iframe=False,
            require_admin=False,
        )
        _LOGGER.info("VoiceBM panel registered: /%s", PANEL_URL_PATH)
        return True
    except ValueError:
        return True
    except Exception as exc:
        _LOGGER.error("VoiceBM panel registration failed: %s", exc)
        return False


def async_unregister_panel(hass: HomeAssistant) -> None:
    try:
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
    except Exception:
        pass
