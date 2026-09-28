# Changelog

## 3.10.1 — integration-first naming
- Metadata only, no behavior change. The add-on is now named **VoiceBM engine**
  (was "VoiceBM") with a description and sidebar title that identify it as the
  engine backend for the VoiceBM Home Assistant integration, matching the
  repo's integration-first direction (see `DIRECTION.md`). The `slug` is
  unchanged (`voicebm` → `local_voicebm`), so existing installs and the
  integration's add-on lookup are unaffected.

## 3.10.0 — delete individual voice samples
- New per-sample management: a small `sample_manager` service (s6 longrun) lists
  and deletes INDIVIDUAL voice samples from an enrolled speaker, so a sample
  that captured the TV, music, or a visitor can be pruned without deleting the
  whole identity. It removes the sample's embedding (.txt) + recording (.wav),
  rewrites metadata.json, and restarts the identity service so the change takes
  effect live; if a speaker's last sample is removed, the empty identity is
  cleaned up. Driven from the integration's Speakers panel (Samples button).
  Implemented as a standalone service — no vendored engine file is modified.

## 3.9.4 — copy-proof packaging (fixes on-device build failure)
- A deploy on real hardware failed with `"/rootfs/...": not found` and a 23KB
  build context: the add-on's 150+ nested files under `rootfs/` hadn't survived
  the copy to `/addons` (the HA File editor can't upload folders, and a Samba
  drag of a folder's *contents* drops the nested tree). The zip was verified
  intact — the failure mode is structural to shipping a deep tree.
- Fix: the entire rootfs tree now ships as ONE flat file, `rootfs.tar.gz`,
  extracted inside the Docker build (`/tmp/build-rootfs`) with every former
  `COPY rootfs/...` converted to an equivalent `cp -a` from the extraction.
  Verified byte-identical to the old tree (diff -r, file counts, zero-byte s6
  dependency files, exec bits). The add-on folder is now a handful of flat
  files — ANY copy method works, including single-file uploads — and a missing
  tarball fails loudly on the first COPY instead of half-building.

## 3.9.3 — make thresholds.active real (first confirmed-working release)
- First release validated end-to-end on live hardware: integration STT →
  /share handoff → engine analysis → pending → JARVIS-labelled hands-free
  enrollment, all confirmed in production logs.
- Init now seeds `out/thresholds.json` (`MATCH_T_ACTIVE`) from the
  `thresholds.active` option on every start. Previously the engine fell back to
  a hardcoded 0.50 because only the (idle-in-integration-mode) dashboard ever
  wrote that file — the exposed option was silently ignored. The option is now
  the source of truth; also kills the "file read failed" warning per utterance.
- Known-benign, verified: an enroll command is handled by two engine services
  (upstream design); the second logs "Failed to move files" and aborts before
  writing metadata, so the net result is one clean enrollment. Harmless noise.
- Known-cosmetic: the emote/SER hook fires opportunistically and fails fast
  (rc=1) when the emote stack isn't built in (INCLUDE_EMOTE=false default).
  Harmless; enrollment/identity unaffected.

## 3.9.2 — self-diagnosing startup banner
- Start log now prints the effective `stt.mode`, warns if it isn't
  `integration` (the tell that the HA integration isn't loaded and self-healing
  it), and states the health invariant: one `Analysis request:` line per spoken
  utterance once the pipeline STT is set to VoiceBM. Live logs showed the
  engine receiving zero requests while looking healthy otherwise — this makes
  that state unmistakable at a glance.

## 3.9.1 — fixes from the first live logs
- **JARVIS enroll race fixed.** Live log showed the bridge receiving JARVIS's
  candidate ("enroll 'Sam'") and finding the pending buffer empty — because
  JARVIS fires the instant speech happens, while the engine needs a moment to
  embed the audio before a pending entry exists. The bridge now polls up to 10s
  (`JARVIS_PENDING_APPEAR_WAIT`) for a fresh entry before giving up, and its
  give-up message now points at the real question (is the identity pipeline
  flowing at all?).
- `cluster_publisher` now idles in integration mode — nothing in that
  architecture consumes its cluster sensors, and its loop was the source of the
  endless "Loading unprocessed samples / Found 0" log spam.

## 3.9.0 — annotated model dropdowns for the built-in ASR
- All four `active.*` fields are now **dropdown menus** covering the complete
  supported model list (verified against onnx-asr's own docs), each option
  annotated with its example use in parentheses — e.g.
  `whisper-base (Whisper Base — accent + noise tolerant English)`. HA's add-on
  UI shows raw schema values, so the annotation lives in the value and is
  stripped automatically before reaching the engine (run script + gen_config;
  `none (…)` maps to unset). Defaults are the JARVIS-appropriate choices:
  Parakeet TDT 0.6B v2 (English), no multilingual, full precision, CPU.
- Models still auto-download on first ASR start into `/data/wyoming-models`
  (persistent) rather than being baked into the image — in the default
  integration mode the built-in ASR never runs, so pre-baking ~1GB of model
  would be dead weight for most installs.
- Fixed the stale "External Wyoming ONNX ASR container wiring" section label in
  the add-on options UI.

## 3.8.1 — integration mode is now the default
- `stt.mode` defaults to `integration` (was `internal`): this package's purpose
  is the HA-integration architecture, and the companion integration also
  self-heals this option via the Supervisor if it's ever flipped. Set it back
  to `internal`/`external_whisper` explicitly if you want the standalone modes.

## 3.8.0 — audit fixes for the integration architecture
- **Critical: shared state moved from `/config/voicebm` to `/share/voicebm`.**
  Supervisor's legacy `config` map semantics changed (add-ons now normally get
  an add-on-private folder at `/config`, with HA's config at `/homeassistant`),
  which could silently make the add-on's `/config/voicebm` a DIFFERENT folder
  than the one HA Core (and thus the integration's panel) reads — empty gallery
  forever, no error. `/share` maps identically in HA Core and every add-on with
  no legacy baggage. First start migrates existing data from both old
  locations (`/config/voicebm`, `/data/voicebm`).
- In `stt.mode: integration`, the Flask dashboard and its Ingress proxy now
  idle — the HA-native panel replaces them, so no redundant UI runs.
- Watchdog repointed from the dashboard (`:5000`, idle in integration mode —
  would have crash-looped the add-on) to the always-on audio server (`:9090`).

## 3.7.0 — HA custom integration ("integration route") + loopback bug fix
- **Fixed the bug that made the bundled Whisper ASR invisible to HA:** it bound
  to `tcp://127.0.0.1:10300` (loopback *inside the container*) and port 10300
  wasn't exposed, so Home Assistant could never reach it — and switching the
  pipeline off the working Whisper add-on killed satellites. Now binds
  `0.0.0.0` and exposes 10300 (for internal mode).
- **New `stt.mode: integration`.** The add-on runs as the identity ENGINE only
  (its ASR/bridge/proxy idle); a companion HA custom integration
  (`integration/custom_components/voicebm/`) is the native STT provider. The
  integration delegates transcription to the user's existing Whisper STT entity
  and drives the add-on's identity engine over MQTT + shared `/share` WAVs — no
  add-on code change needed (the STT service already reads the request's
  audio_path). Transcription is guaranteed independent of identity, so choosing
  VoiceBM as the pipeline STT can't break satellites.
- Gated the bundled ASR + STT bridge to idle in any non-internal mode.

## 3.6.0 — use the existing HAOS Whisper (external STT mode)
For setups with a Voice PE/ESPHome satellite (no room mic to tap) that already
run a Whisper add-on and don't want a second transcriber:
- New `stt.mode: external_whisper`. VoiceBM stops transcribing (its bundled ASR
  + STT bridge idle) and a new thin **Wyoming proxy** (`voicebm-whisper-proxy`,
  port 10400) becomes the Assist STT. It forwards audio to the external Whisper
  add-on for the transcript, and in parallel drives VoiceBM's identity engine
  via its `voicebm/stt/analyze_request` MQTT + a shared WAV — so Whisper is the
  only transcriber while VoiceBM still publishes speaker identity. No fork of
  VoiceBM's vendored handler; the identity engine's request interface is
  transcription-independent, which made this clean.
- Added `stt` options: `mode`, `whisper_uri`, `proxy_port`, `identity_inject`,
  `identity_wait_ms`. Default `mode: internal` (unchanged behavior).
- Gated the bundled ASR and STT bridge to idle when `external_whisper` is set,
  so no redundant transcriber runs.

## 3.5.0 — native integration with the haos-gpu-ai OS
Studied the actual OS being run (github.com/sam3gp8/haos-gpu-ai) and aligned
VoiceBM with how that image really works:
- **Corrected the GPU access pattern.** 3.3.0 used a `/dev/nvidia*` `devices:`
  list; the haos-gpu-ai image (and its bundled Ollama add-on) instead grant GPU
  via `full_access: true` + `NVIDIA_VISIBLE_DEVICES` / `NVIDIA_DRIVER_CAPABILITIES`,
  relying on that OS's conditional `default-runtime: nvidia`. A named device
  node would break on the image's Intel/AMD hosts and is the brittle path its
  README explicitly warns against. Switched to the proven `full_access`
  pattern; removed the device-node list. Also added `share:rw` to the map to
  match the OS's add-on convention.
- **OS overlay to bake VoiceBM into the image** (`haos-gpu-ai-voicebm-overlay/`,
  shipped alongside the add-on). It drops the VoiceBM add-on source into the
  read-only rootfs under `/usr/share/haos-gpu/addon-voicebm/` and replaces the
  OS's ollama-only `seed-local-addons.sh` with a generalized seeder that seeds
  *every* bundled `/usr/share/haos-gpu/addon-*` (reading each add-on's slug from
  its own config). Result: VoiceBM appears pre-installed under Local add-ons on
  first boot, exactly like Ollama — no manual copying.

## 3.4.0 — fits the HAOS setup better (Ingress + /config storage)
Aligned VoiceBM with the conventions the other add-ons on this setup use:
- **HA Ingress.** The dashboard now appears in the HA sidebar (panel "VoiceBM",
  authenticated by HA) instead of on a raw, unauthenticated port. A small
  built-in reverse proxy (`voicebm-ingress`, port 8099) sits in front of the
  upstream Flask dashboard and rewrites its absolute `/api/` paths to be
  Ingress-relative on the fly — so it works under the Ingress prefix without
  modifying vendored dashboard code. Port 5000 is now unmapped by default
  (opt-in if you want direct access too).
- **`/config` storage.** User-facing state (config.json, enrollment gallery,
  embeddings, metadata, pending buffer, auto-enroll state) moved from the
  hidden `/data` volume to `/config/voicebm/`, so it's visible in the File
  Editor/Samba and included in HA backups — matching the house convention.
  High-churn caches (raw recordings, downloaded ASR/speaker models) stay in
  `/data` to keep backups small and the File Editor uncluttered. First start
  after upgrade auto-migrates existing enrolled voices from `/data/voicebm`.

## 3.3.0 — GPU support + JARVIS-AIO integration
- **NVIDIA/CUDA GPU support** (opt-in via `ENABLE_GPU=true` build arg): swaps
  the ASR stack to `onnxruntime-gpu` (CUDA execution provider — the hot path)
  and the passive-VAD/emote torch to the CUDA wheel. The bundled ASR server
  already honors `active.device: gpu` / `gpu-trt` (upstream builds the
  CUDA/TensorRT provider list), so the runtime path needed no change.
  Declares the `/dev/nvidia*` device nodes and sets `NVIDIA_VISIBLE_DEVICES`
  / `NVIDIA_DRIVER_CAPABILITIES`. **Only works where the NVIDIA container
  runtime is exposed to add-ons** (Supervised / custom GPU-enabled HAOS — not
  stock HAOS, which blocks the NVIDIA runtime for add-ons); a GPU image still
  falls back to CPU cleanly on a CPU-only host.
- **JARVIS-AIO integration.** JARVIS already consumes VoiceBM's
  `binary_sensor.<person>_voice` entities into its identity resolver — so
  identity is pure config on the JARVIS side. Added a bridge
  (`voicebm-jarvis-bridge`, `jarvis.enroll_bridge`) that closes the
  hands-free *labelled* enrollment loop: it listens on an MQTT topic JARVIS
  publishes the confident person name to (via a one-line HA automation on
  `jarvis_voice_enroll_candidate`) and enrolls VoiceBM's newest fresh pending
  voice under that exact name, using the existing enroll path. This is
  strictly better than the blind auto-enroller since JARVIS supplies the
  correct label. Added `jarvis` options block.

## 3.2.0 — optional automatic enrollment
- New **auto-enroll** feature (off by default): a new supervised service
  (`voicebm-auto-enroll`) that periodically clusters unrecognized voices —
  using VoiceBM's *own* `voice_clustering` module — and auto-enrolls
  clusters that are big enough (`min_samples`), tight enough
  (`min_cohesion`), and not already a likely match for an enrolled person.
  It enrolls by publishing the same `voicebm/pending_active/enroll` MQTT
  command the dashboard uses, so no vendored engine code is touched; the
  engine's own `handle_pending_enroll` does the actual work. New people are
  named `{name_prefix} N` and can be renamed from the dashboard/HA device.
- Added `auto_enroll` options: `enabled`, `min_samples`, `min_cohesion`,
  `interval_s`, `name_prefix`, with bounded schema validation.
- Gated behind the `active` component (that's what produces pending voices),
  and it degrades to a cheap idle when disabled.

## 3.1.0 — build reliability (base image + dependency restructuring)
Verified the build far more rigorously (real PyPI dependency resolution;
confirmed base-image tags on ghcr) and fixed what that surfaced:
- **Base image → HA's multi-arch `base-debian:trixie`.** Was
  `${BUILD_ARCH}-base-debian:bookworm`. HA moved to multi-arch base images
  (2026.03.1+) and now recommends them over the arch-prefixed names; `trixie`
  is the current codename (`bookworm` still publishes but is frozen). Using
  the current multi-arch base is the more future-proof, less surprising
  choice.
- **Heavy dependency stacks are now opt-in, off by default.** Previously a
  single `INCLUDE_HEAVY_MODELS=true` (default on) baked in torch + funasr +
  transformers — and a real dependency-resolution test showed `funasr` alone
  pulls 80+ transitive packages (its own torch, transformers, numba,
  llvmlite, librosa, modelscope, the Aliyun SDK…), the single most fragile
  and multi-GB part of any build here, none of which Active or the identity
  engine needs. Split into two independent, default-off args:
  `INCLUDE_PASSIVE_VAD` (torch + silero-vad, for the passive VAD filter) and
  `INCLUDE_EMOTE` (funasr + transformers, for SER). The default image is now
  ~40 packages that resolve cleanly (verified), instead of 120+.
- **Silero VAD now via the `silero-vad` pip package** (ships the model in
  the wheel) plus the existing build-time torch.hub pre-cache, rather than
  relying solely on a runtime hub fetch.
- **torch pinned to the CPU wheel before funasr installs**, so funasr can't
  pull the multi-GB CUDA torch from PyPI and clobber it.
- **Graceful degradation when an optional stack is enabled but not built
  in:** the VAD (needs `torch`) and Ambient (needs `transformers`) services
  now check for their module and idle with a clear "rebuild with
  INCLUDE_… to enable" message instead of crash-looping. (Emote already
  no-ops via upstream's own soft-import.)

## 3.0.2 — startup ordering, missing dependency, and VAD crash-loop
Three issues surfaced once the container actually booted (3.0.1 got it
starting):
- **Services started before config.json existed.** The 3.0.1 approach put
  the init logic in `/etc/cont-init.d`, but in this base image the s6-rc
  `user` bundle (all the daemons) comes up *before* `legacy-cont-init` runs
  — so every service launched against a missing `/home/user/voicebm/config.json`
  and either crashed or fell back to `localhost:1883`. Fixed the correct
  s6-v3 way (per the official MOVING-TO-V3 guide): the init steps are real
  s6-rc **oneshots** again, but each `up` file contains only the *path* to a
  separate executable script (`/etc/s6-overlay/scripts/...`) rather than the
  script body, and **every longrun now declares `base` + `wait-mqtt` as
  dependencies** so it cannot start until config generation and the broker
  wait have completed.
- **STT bridge crashed on missing `python-multipart`.** FastAPI needs it for
  the multipart file upload on `/v1/audio/transcriptions`; without it the
  bridge threw `RuntimeError: Form data requires "python-multipart"` on
  every start. Added to the pip install list.
- **Passive VAD retry-looped hundreds of times.** `vad_filter.py` calls
  `torch.hub.load('snakers4/silero-vad', ...)` with no local cache, which at
  runtime tries to clone from GitHub and blocks on an unanswerable
  interactive trust prompt (`EOF when reading a line`), crashes, and gets
  restarted endlessly. Two fixes: (1) the Silero model is now pre-cached
  into the torch hub dir at **build time** with `trust_repo=True`, so the
  runtime load is offline and silent; (2) the VAD service is now correctly
  gated behind the `passive` component toggle (it's a passive-pipeline
  service — it watches passive node recording dirs), so it doesn't run at
  all unless passive is enabled.

## 3.0.1 — fixes container failing to start (`unable to exec set`)
- **Root cause:** `init-voicebm-config` and `voicebm-wait-mqtt` were
  implemented as s6-rc **oneshot** services with multi-line bash `up`
  scripts. That's not how oneshots work: unlike a longrun's `run` script
  (which s6-supervise really `exec`s, honoring the shebang), a oneshot's
  `up` file is parsed by `s6-rc-compile` itself using execline's
  text-parsing rules at boot — there's no shell involved at all. It choked
  on the second line (`set -e`), trying to literally execute a program
  named `set`, which doesn't exist as a standalone binary: `s6-rc-oneshot-run:
  fatal: unable to exec set: No such file or directory`. Every start failed
  and the container stopped immediately.
- **Fix:** moved both scripts to `/etc/cont-init.d/` (`10-voicebm-config.sh`,
  `20-voicebm-wait-mqtt.sh`) — the base image's real, sequential, real-bash
  init mechanism, confirmed already present and working in the base image
  (`legacy-cont-init` in the boot log) and guaranteed to complete before any
  s6-rc "user" bundle service starts. Removed the two broken oneshot
  service directories and every dangling `dependencies.d` reference to them.

## 3.0.0 — fully self-contained (no external ASR container)
- **Removed the external Wyoming ASR container dependency entirely.**
  Upstream's Active pipeline is designed against a separately-installed
  `wyoming-onnx-asr` container that VoiceBM's own `deploy_handler.sh`
  `docker cp`'s a custom `handler.py` into. Traced that dependency to its
  actual upstream ([tboby/wyoming-onnx-asr](https://github.com/tboby/wyoming-onnx-asr),
  MIT, © Michael Hansen & Thomas Boby) and vendored it directly — it now
  runs as one more supervised process (`voicebm-wyoming-asr`) inside this
  same container, loopback-only. VoiceBM's `handler.py.template` was
  verified to be written directly against this package's exact handler
  constructor signature, so "deploying" it is now just rendering the
  template with this add-on's MQTT settings and overwriting the installed
  package's `handler.py` before that process starts — no docker cp, no
  container restart, no second container to keep alive.
- **Removed `docker_api: true` and `host_network: true`.** Neither was
  needed for anything else; both existed solely to support the old
  cross-container handler deployment. Back to standard bridge networking
  with mapped ports.
- **Removed the Docker CLI install from the Dockerfile** — nothing in the
  container needs to talk to Docker anymore.
- Replaced `active.asr_container` / `handler_path_in_container` /
  `wyoming_host` / `wyoming_port` options with `active.model_en` /
  `model_multilingual` / `quantization` / `device`, controlling the bundled
  ASR model directly.
- ASR models now cache under `/data/wyoming-models` (persistent, not
  re-downloaded on restart).

## 2.2.0 — targets current HAOS build pipeline
- **Removed `build.yaml`.** Home Assistant retired the legacy builder
  container in April 2026 in favor of Docker BuildKit; `build.yaml` still
  works via a backward-compat shim in Supervisor but is deprecated (warns,
  will eventually be dropped). Migrated its contents directly into the
  `Dockerfile`: `FROM ghcr.io/home-assistant/${BUILD_ARCH}-base-debian:bookworm`
  using the `BUILD_ARCH` build arg Supervisor still supplies by default, and
  explicit `LABEL`s (`io.hass.version`, `io.hass.type="app"`, `io.hass.arch`,
  plus standard OCI labels) since Supervisor no longer infers these without
  the old builder.
- **Docker CLI install rewritten.** Was `apt-get install docker.io`, which
  pulls in containerd/runc and a full daemon package meant for a real host
  (plus postinst hooks that can misbehave in a minimal build environment).
  Now fetches the static `docker` CLI binary from Docker's official
  download server for the matching architecture — this add-on only ever
  needs to speak to the *host's* mounted docker socket, never run its own
  daemon.
- Documented actual HAOS install paths (Samba share vs. SSH+git into
  `/addons`), since this ships as a local/on-device build, not a
  registry-hosted image.
- Documented why `docker_api`/`host_network` "just work" for a local add-on
  on HAOS without extra configuration (Supervisor's protected-mode
  distinction), and the AppArmor escape hatch if needed.

## 2.1.1
- **Fix:** switched to `host_network: true`. Upstream's Active pipeline
  assumes `127.0.0.1` reaches the Wyoming ASR container (true when both are
  systemd services on one host); on Docker bridge networking that loopback
  would only ever resolve to this container itself, silently breaking the
  STT bridge's default `wyoming_host`. Dropped the now-irrelevant `ports:`
  remap block accordingly (host networking binds the four ports directly).
- Added `voicebm-wait-mqtt`, a oneshot every service now depends on: blocks
  up to 30s until the configured broker accepts a TCP connection, so boot
  logs aren't a wall of every service's own MQTT retry noise.
- Replaced the cleanup loop's 30s polling with an exact sleep-until-next-02:00
  calculation.
- Added a Supervisor `watchdog` against the dashboard, so the add-on
  restarts itself if that process wedges.
- Fixed a `find` operator-precedence bug in the Dockerfile that meant the
  `-type f` filter wasn't actually applied to the `up`/`finish` chmod passes.
- Removed an unused/incorrect `map: addon_config` entry — persistent storage
  already comes from `/data` without declaring it.
- Verified `sherpa-onnx` publishes manylinux (glibc) wheels for both amd64
  and aarch64 against current PyPI, confirming the Debian-over-Alpine base
  image choice.

## 2.1.0
- Initial add-on packaging of upstream VoiceBM 2.0/2.1
  (github.com/cybericebyte/VoiceBM), version-matched to upstream's tagged
  release.
- Vendors upstream's `bin/*.py`, `bin/*.sh`, and `templates/active/handler.py.template`
  unmodified.
- Replaces `setup_voicebm.sh`'s interactive wizard with `gen_config.py`,
  which builds `config.json` from the add-on's options + the Supervisor's
  MQTT service.
- Replaces `scripts/deploy_global_services.sh`'s per-service systemd units
  with s6-overlay longruns/oneshots (one process each, same restart
  semantics: `Restart=always` -> longrun auto-restart, the daily cleanup
  timer -> a loop).
- Replaces `scripts/replicate_node.sh` (one systemd unit per script per
  node) with `node_supervisor.py`, a single process that starts/restarts
  the recorder/embedder/publisher trio for every configured passive node.
- Replaces `scripts/deploy_handler.sh` with an equivalent run against the
  add-on's `docker_api` socket, executed automatically on every start.
- Recordings/embeddings/enrollment gallery/config.json persisted under
  `/data` via symlinks into upstream's hardcoded `/home/user/voicebm/*`
  paths.
