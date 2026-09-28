# Direction: integration-first

> **Decision (2026-09):** `voicebm-ha` is a **Home Assistant integration** for
> speaker identity, backed by an engine add-on. The integration is the product;
> the add-on is the engine it drives. Everything in this repo — docs, metadata,
> UI, and future work — leads with the integration and treats the add-on as a
> documented dependency.

## Why

The repo ships two artifacts:

- `custom_components/voicebm/` — the **HA integration** (HACS-installable): a
  native STT entity that transcribes through your existing Whisper and adds
  speaker identity on the same audio, plus a native **VoiceBM Speakers** sidebar
  panel served through Home Assistant.
- `voicebm-engine-addon/` — the **engine add-on**: the ONNX voice-biometrics
  engine. It lives in its own glibc container because the ML runtime can't run
  inside HA Core's Alpine environment — so the split is a runtime constraint,
  not a product choice.

Between the two, the integration is what a user installs, configures, and sees.
The add-on is plumbing that exists only because of that runtime constraint.
Leading with "add-on" would put the accidental complexity in the shop window;
leading with the integration matches what the user actually experiences.

The code already leans this way. As of engine add-on 3.8.x–3.10.x:

- `stt.mode: integration` is the **default** (add-on 3.8.1).
- In that mode the add-on's Flask dashboard, its Ingress proxy, the bundled
  Wyoming ASR, and the STT bridge all **idle** — the add-on runs purely as the
  identity engine, and the integration's native HA panel is the UI (add-on
  3.7.0, 3.8.0).
- The integration self-heals the add-on into `integration` mode over the
  Supervisor, the same companion-add-on pattern Z-Wave JS and Matter use
  (`custom_components/voicebm/engine.py`).

So the architecture is already integration-first. This document makes the
**positioning** match the architecture.

## What "integration-first" means, concretely

1. **The integration is the headline.** The README, HACS metadata, and the repo
   description present `voicebm-ha` as the VoiceBM *integration* for Home
   Assistant. The engine add-on is introduced as the backend it needs, not as a
   co-equal product.
2. **Integration mode is the supported path.** `stt.mode: integration` is the
   default and the documented happy path. `internal` and `external_whisper`
   remain available for standalone use, but are secondary.
3. **One UI: the native panel.** The **VoiceBM Speakers** panel
   (`custom_components/voicebm/frontend/`) is the canonical management surface.
   The add-on's own dashboard is a fallback for standalone modes only.
4. **The add-on is named and described as the engine.** Its `name` and
   `description` say "engine backend," so it never reads as the main event in
   the add-on store or the Supervisor.

## What changed in this pass

- **`README.md`** — reframed to lead with the integration; the add-on is now
  presented as the engine dependency the integration configures and drives.
- **`voicebm-engine-addon/config.yaml`** — `name` → `VoiceBM engine`,
  `description` and `panel_title` reworded to identify it as the engine backend
  for the integration (slug unchanged, so existing installs and the
  integration's `local_voicebm` lookup are unaffected). Version bumped so the
  metadata change propagates on the next Supervisor update check.
- **`DIRECTION.md`** — this file.

No code behavior changed: transcription still runs through Whisper independently
of identity, and the add-on's standalone modes are untouched.

## What stays as-is

- The file layout is already correct for integration-first: the integration
  lives at `custom_components/voicebm/` (where HACS expects it) and the add-on
  at `voicebm-engine-addon/`. No directories move — moving them would break
  HACS discovery, the add-on repository layout, and the `local_voicebm` slug.
- The engine add-on keeps its `internal` and `external_whisper` standalone
  modes. Integration-first is about what we *lead with*, not about removing
  working paths.
- All upstream attribution to [@cybericebyte](https://github.com/cybericebyte)
  in `README.md`, `LICENSE`, the manifest, and the add-on docs. That is an MIT
  requirement and a courtesy, independent of direction.

## Roadmap / next steps

Done since this direction was set:

- ✅ **Trimmed the add-on `DOCS.md` for integration-first** — leads with the
  integration-mode role; standalone STT modes, RTSP nodes, auto-enroll,
  JARVIS-AIO, and GPU moved into a marked "Advanced / standalone" section.
- ✅ **Repairs-panel install guidance** — the engine-missing Repairs issue's
  "Learn more" now deep-links to the README install steps (`engine.py`).
- ✅ **Retired the add-on's Ingress panel in integration mode** — the add-on
  hides its own sidebar entry in `integration` mode (engine add-on 3.11.0),
  shown again in the standalone modes.
- ✅ **Release automation** — `.github/workflows/release.yml` publishes a
  GitHub Release when the integration manifest version lands on `main`, keyed
  off `CHANGELOG.md`.

Remaining:

1. **HACS default-store submission.** In-repo readiness is done: `hassfest` +
   `hacs/action` run in CI (`.github/workflows/validate.yml`), `hacs.json`
   carries the required `name`, the manifest keys are hassfest-ordered, and
   there are tagged releases. Two external steps remain, neither of which can
   be done from inside this repo:
   - **Brands.** The `voicebm` domain must be added to
     [home-assistant/brands](https://github.com/home-assistant/brands) (a
     256×256 `icon.png` + 512×512 `logo.png` submitted there) — that's why the
     CI HACS check currently ignores `brands`. Needs real VoiceBM brand art and
     a PR to their repo; remove the `ignore: brands` line in `validate.yml` once
     accepted.
   - **Default-store listing.** Submit the repo to
     [hacs/default](https://github.com/hacs/default) once brands lands and the
     validation is fully green (no ignored checks). Until then, users install it
     as a custom repository, which works today.

## Non-goals

- **Collapsing the add-on into the integration.** The glibc/ONNX runtime
  constraint is real; the engine cannot run inside HA Core's Alpine environment.
  The two-piece split stays.
- **Dropping standalone modes.** They serve setups without a separate Whisper
  (e.g. a room-mic-only passive pipeline) and cost little to keep.
