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

Ordered roughly by value-to-effort, not committed to dates:

1. **Trim the add-on `DOCS.md` for integration-first.** It still reads as a
   standalone-engine manual (its own dashboard, GPU, JARVIS, nodes). Lead it
   with the integration-mode role; move the standalone-mode material into a
   clearly-marked "standalone / advanced" section.
2. **Repairs-panel install guidance.** The integration already raises a Repairs
   issue when the engine add-on is missing (`engine.py`). Make that issue link
   straight to the add-on install steps so the happy path is discoverable from
   inside HA.
3. **HACS default-store readiness.** As a custom repository the integration
   works today. If we want the default HACS store later, the integration needs
   the usual hygiene (brands entry, `hassfest`/HACS validation in CI, a tagged
   release per change). Track separately.
4. **Consider retiring the add-on's Ingress panel in integration mode.** It
   already idles there; hiding the sidebar entry in that mode would remove a
   confusing duplicate of the native **VoiceBM Speakers** panel. This is a
   behavior change — do it deliberately, with a migration note, not casually.

## Non-goals

- **Collapsing the add-on into the integration.** The glibc/ONNX runtime
  constraint is real; the engine cannot run inside HA Core's Alpine environment.
  The two-piece split stays.
- **Dropping standalone modes.** They serve setups without a separate Whisper
  (e.g. a room-mic-only passive pipeline) and cost little to keep.
