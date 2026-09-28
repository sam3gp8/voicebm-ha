## [1.0.3] — Speakers panel survives an engine restart

**Fixes the "Couldn't load samples: No response from the VoiceBM engine" error that appeared when the engine add-on was mid-restart, and stops the integration from causing those restarts.**

- **Samples list falls back to disk.** Listing a speaker's samples used a live
  MQTT round-trip to the engine's `sample_manager`; if the add-on was restarting
  (or its MQTT was briefly down) the click timed out with an error. Listing is
  read-only and the samples live in `enroll/<pid>/metadata.json`, which HA Core
  reads directly — so on a timeout the panel now reads them off disk instead of
  erroring. Deleting a sample still goes through the engine (it removes files and
  reloads the gallery).
- **No more disruptive add-on restarts on a mode flip.** When the integration
  finds the engine add-on's `stt.mode` isn't `integration`, it sets it — but it
  no longer restarts a *running* add-on to apply it. The identity service runs
  regardless of `stt.mode`, so identity keeps working; the mode change takes
  effect on the add-on's next natural restart. This removes the ~30-60s windows
  where a running add-on was yanked out from under the Speakers panel. (A stopped
  add-on is still started.)

## [1.0.2] — declare the hassio dependency; add validation CI

**HACS default-store readiness: `hassfest` + HACS validation now run in CI, and the integration correctly declares the `hassio` dependency it was already using.**

- The integration imports `homeassistant.components.hassio` (`AddonManager` /
  `is_hassio`) to detect and manage the engine add-on, but the manifest never
  declared it. Added `hassio` to `after_dependencies` — a soft dependency, so
  non-Supervisor installs are unaffected while setup ordering is correct when
  the Supervisor is present. (`hassfest` flagged this.)
- New `.github/workflows/validate.yml`: `hassfest`, `hacs/action`
  (`category: integration`), and a panel JS syntax check, on push / PR / weekly.
  The HACS `brands` check is ignored pending the `home-assistant/brands`
  submission (see `DIRECTION.md`); everything else is validated.
- Normalized `LICENSE` to the standard MIT text (both copyright notices
  retained) so GitHub identifies it as MIT — the HACS license check needs a
  recognized SPDX license; the explanatory attribution lives in the README.

## [1.0.1] — integration-first direction

**The repo now leads with the integration; the engine add-on is the engine it drives, and hides its idle sidebar panel in the default integration mode.**

Integration (`custom_components/voicebm/`):
- The "engine add-on not installed" Repairs issue's **Learn more** button now
  deep-links to the README's engine add-on install steps instead of the repo
  root, so the happy path is one click away from inside Home Assistant.

Engine add-on (`voicebm-engine-addon/`, 3.11.0):
- In the default `stt.mode: integration`, the add-on's Flask dashboard and its
  Ingress proxy already idle (the integration's native **VoiceBM Speakers**
  panel is the UI) — the add-on now also **hides its own sidebar entry** so
  there's no dead duplicate to click, setting `ingress_panel` over the
  Supervisor on start. It's shown again in the `internal` / `external_whisper`
  standalone modes, and re-evaluated on every start so switching modes flips it
  automatically. Best-effort and non-fatal.
- Renamed to **VoiceBM engine** with an engine-backend description (slug
  unchanged), matching the integration-first framing.

Docs & metadata:
- README reframed to lead with the integration; the engine add-on is presented
  as its dependency.
- The engine add-on's `DOCS.md` restructured to lead with the integration-mode
  role, with standalone STT modes, RTSP nodes, auto-enroll, JARVIS-AIO, GPU, and
  the full options reference moved into a marked **Advanced / standalone**
  section.
- New `DIRECTION.md` states the integration-first direction, rationale, roadmap,
  and non-goals.

## [1.0.0] — initial release

**Standalone Home Assistant packaging of VoiceBM: a HACS integration plus a headless engine add-on.**

- `custom_components/voicebm/` — a native HA integration that registers as a
  speech-to-text engine (transcribes through your existing Whisper and adds
  speaker identity on the same audio) and provides a native **VoiceBM Speakers**
  sidebar panel.
- `voicebm-engine-addon/` — the headless voice-biometrics engine add-on, run in
  its own glibc container because the ONNX runtime can't run inside HA Core's
  Alpine environment. The integration configures and starts it over the
  Supervisor.
- Built on the open-source [VoiceBM](https://github.com/cybericebyte/VoiceBM) by
  [@cybericebyte](https://github.com/cybericebyte) (MIT); this repo adds the HA
  integration and add-on packaging.
