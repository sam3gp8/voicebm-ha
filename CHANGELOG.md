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
