# VoiceBM engine — Home Assistant add-on

This is the **engine backend** for the [VoiceBM Home Assistant
integration](https://github.com/sam3gp8/voicebm-ha). It packages upstream
[cybericebyte/VoiceBM](https://github.com/cybericebyte/VoiceBM) (a
systemd-service-based, host-installed voice biometrics engine) into a single
Home Assistant add-on container, built and run entirely on **Home Assistant
OS** — no separate host, no systemd, no manual Python environment. The engine
code itself is vendored unmodified; everything install/deploy-related (the
interactive wizard, `config.json` generation, per-node systemd units, and the
ASR handler copy step) is replaced with add-on-native equivalents that HAOS's
Supervisor runs directly.

> **You configure and use VoiceBM through the integration, not here.** Install
> the integration via HACS, install this add-on once, and the integration wires
> the two together (it even sets this add-on's `stt.mode: integration` and
> starts it for you over the Supervisor). This page is the engine's reference:
> read the [repo README](https://github.com/sam3gp8/voicebm-ha) and
> [`DIRECTION.md`](https://github.com/sam3gp8/voicebm-ha/blob/main/DIRECTION.md)
> for the integration-first setup.

## Its role: the identity engine behind the integration

In the default architecture (`stt.mode: integration`, the shipped default):

- **The integration is the speech-to-text provider and the UI.** It transcribes
  through your existing Whisper and provides the native **VoiceBM Speakers**
  sidebar panel.
- **This add-on runs as the identity engine only.** Its bundled Wyoming ASR, the
  STT bridge, the `external_whisper` proxy, the Flask dashboard, and the
  dashboard's Ingress proxy all **idle** — the integration replaces them. The
  add-on embeds the audio, matches it against the gallery, and publishes speaker
  identity.
- **The two communicate over MQTT + a shared `/share/voicebm` folder.** The
  integration drops STT audio for the engine to analyze; the engine publishes
  identity back. Transcription never depends on identity — if the engine is down
  you still get Whisper's transcript.

You normally never touch `stt.mode`: the integration self-heals it to
`integration` over the Supervisor. The standalone modes (`internal`,
`external_whisper`) and the passive/ambient pipelines are documented under
[Advanced / standalone configurations](#advanced--standalone-configurations)
below, and are not needed for the default setup.

## Installing on HAOS

This is a **local** add-on (built on your device from source, not pulled
from a container registry), which is how HAOS is designed to run
custom/community add-ons. Two ways to get the folder onto your HAOS box:

**Option A — Samba Share add-on** (easiest if you don't already use git):
1. Install the official **Samba share** add-on if you don't have it, and
   start it.
2. From another computer, connect to `\\<haos-ip>\addons` (Windows) or
   `smb://<haos-ip>/addons` (Mac/Linux).
3. Copy this repo's `voicebm/` folder in as-is — you should end up with
   `addons/voicebm/config.yaml` etc. directly under the share.
4. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ (top right)
   → Check for updates**. **VoiceBM engine** appears under **Local add-ons**.

**Option B — SSH & Web Terminal add-on** (if you're comfortable with git):
1. Install the official **Terminal & SSH** add-on and connect.
2. `cd /addons && git clone https://github.com/sam3gp8/<your-fork>.git voicebm-repo`
   (or `scp`/copy this folder there directly) so that
   `/addons/voicebm-repo/voicebm/config.yaml` exists.
3. Same as above: Add-on Store → Check for updates → **Local add-ons**.

Either way, click into **VoiceBM engine**, hit **Install**, and HAOS's
Supervisor builds the image on-device (Debian base + Python deps + the vendored
engine — expect several minutes, longer with Ambient/Emote's `torch` pull). In
the default integration setup you don't need to change any options before
starting it — the integration configures it. (If you're using the standalone
Passive/Ambient pipelines, set `nodes` first; see below.)

If you'd rather publish this as a proper GitHub add-on repository (so it
shows up like any store add-on via **Repositories** instead of `/addons`),
push the whole folder — `repository.json` at the root, `voicebm/` as the
add-on folder — to a GitHub repo and add that URL under Add-on Store → ⋮ →
Repositories.

## Built for HAOS's current build pipeline

Home Assistant retired the old `home-assistant/builder` container in favor
of plain Docker BuildKit in April 2026, and `build.yaml` is deprecated
under it (Supervisor still reads one if present, for backward
compatibility, but warns and will eventually drop support). This add-on
doesn't ship a `build.yaml` — the base image, labels, and build args all
live directly in the `Dockerfile`, using the `BUILD_ARCH`/`BUILD_VERSION`
args Supervisor supplies automatically. That's also what lets you
`docker build` it locally (outside Supervisor) if you want to iterate
faster than a full on-device rebuild — see
[Local app testing](https://developers.home-assistant.io/docs/apps/testing)
if you go that route.

## What runs

Every upstream service that isn't per-node runs as its own s6 supervised
process inside the container: global publisher, cluster publisher,
enrollment watcher, VAD filter, retention, audio server, WAV HTTP server,
dashboard, thing engine, node engine, and (if `components.active` is on)
the STT service, STT bridge, and the bundled Wyoming ASR server itself. A
daily cleanup loop replaces the upstream `voicebm-cleanup.timer`.

In the default `stt.mode: integration`, the transcription-side processes (the
bundled Wyoming ASR, the STT bridge, the `external_whisper` proxy) and the Flask
dashboard + its Ingress proxy idle — the integration provides transcription and
the UI. The identity-side services (embedding, gallery matching, enrollment,
audio server) run as usual.

Passive nodes (RTSP audio sources) are handled by one supervisor process
(`node_supervisor.py`) that starts/restarts the recorder → embedder →
publisher trio for every node you define with `recorder_enabled: true`,
instead of upstream's `replicate_node.sh` writing three systemd units per
node.

Ambient (audio-event detection) runs as one process across every node
with `ambient_enabled: true`, same as upstream.

## Access and ports

In the default integration setup, the UI is the integration's native **VoiceBM
Speakers** panel — the add-on's own Flask dashboard and its Ingress proxy idle,
and the add-on **hides its own sidebar entry** so there's no dead duplicate to
click (it sets `ingress_panel` off over the Supervisor on start; the Ingress
endpoint itself stays reachable from the add-on's info page). Home Assistant
talks to VoiceBM entirely over MQTT: the **Voice Biometrics** device appears
automatically under Settings → Devices & Services → MQTT once the add-on is
running.

In a standalone mode the add-on's dashboard runs behind **Home Assistant
Ingress** (sidebar entry, authenticated by HA, no open port) and the add-on
shows its sidebar entry again; a small built-in reverse proxy keeps the upstream
dashboard's absolute API paths working under the Ingress prefix without
modifying upstream code. The add-on re-evaluates this on every start, so
switching modes flips the sidebar entry automatically.

A few services stay on mapped ports because external tools may need them
directly:

| Port | What |
|---|---|
| 8005 | STT Bridge — OpenAI-compatible `/v1/audio/transcriptions`, for OpenWebUI etc. (idle in integration mode) |
| 8000 | Raw WAV recordings (per-node segments) |
| 9090 | Audio server — serves pending/enrollment clips back to Home Assistant |

The dashboard's own port 5000 is unmapped by default (use the sidebar or, in the
default setup, the integration's panel). If you want direct port access, set
`5000/tcp` to `5000` in the add-on's Network panel. The bundled ASR's Wyoming
port (10300) stays loopback-only.

## Storage: browsable in the File Editor

Persistent data is split by how useful it is to you:

- **`/share/voicebm/`** — `config.json`, the enrollment gallery, embeddings,
  metadata, the pending buffer, auto-enroll state. This is the stuff worth
  seeing, editing, and backing up, so it lives under `/share` where the
  **File Editor**/**Samba** show it and HA **backups include it**. `/share` maps
  identically in HA Core and every add-on, so the integration's panel reads the
  same gallery the engine writes.
- **`/data/`** — raw per-node recordings and the downloaded ASR/speaker
  models. Large, regenerable, not worth backing up, so they stay out of
  `/share` to keep the File Editor uncluttered and backups small.

Upgrading from a pre-3.4 version auto-migrates your enrolled voices from the
old `/data/voicebm` (and pre-3.8 `/config/voicebm`) location into
`/share/voicebm` on first start (a `.migrated` marker prevents it repeating), so
nothing is lost.

## Data persistence

Recordings, embeddings, the enrollment gallery, `config.json`, and the
downloaded ASR model(s) all live under this add-on's `/data` volume
(engine data mapped from upstream's
`/home/user/voicebm/{recordings,embeddings,enroll,meta,out,pending_active}`
via symlinks created at container start; ASR models cache under
`/data/wyoming-models`). Uninstalling and reinstalling the add-on with the
same options will not lose your enrolled voices or re-download models
unless you also delete the add-on's data.

## Startup ordering

Two s6-rc **oneshot** services run before any of VoiceBM's daemons:
- `init-voicebm-config` — builds `config.json`, symlinks persistent storage,
  fetches the speaker model.
- `wait-mqtt` — blocks up to 30s until the configured broker accepts a TCP
  connection (depends on `init-voicebm-config`, so config exists first).

Every longrun declares both `base` and `wait-mqtt` as dependencies, which
guarantees `config.json` exists and the broker has been waited-for before
any daemon starts — without that, the daemons race ahead and come up against
a missing config / unreachable `localhost` broker.

Implementation note, since this bit twice during development: an s6-rc
oneshot's `up` file is **not** a shell script — `s6-rc-compile` parses it
with execline's text rules, so a multi-line bash body there fails outright.
The actual init logic lives in separate executable files under
`/etc/s6-overlay/scripts/`, and each `up` file contains just the path to
one. (`/etc/cont-init.d` — the other obvious place — doesn't work here
either: in this base image it runs *after* the s6-rc user bundle, so the
daemons would still start first.)

## HAOS privilege notes

This add-on no longer requests `docker_api` or `host_network` — the ASR
server that used to require the docker socket is now bundled in-process
(see [Standalone STT](#standalone-stt-the-bundled-transcriber-internal-mode)),
so there's nothing elevated to grant. Default AppArmor confinement applies and
hasn't needed loosening for anything here (ffmpeg's RTSP sockets and outbound
MQTT/HTTP both fall inside the generated profile). If you hit an AppArmor denial
in the log for something add-on-specific, the escape hatch is `apparmor: false`
in `config.yaml`, at the cost of confinement.

## Known limitations of this packaging

- **Passive VAD and Emote (SER) are opt-in at build time.** By default the
  image builds *without* the torch / silero-vad stack (needed for the
  passive VAD filter) or the funasr / transformers stack (needed for Emote).
  This keeps the default build small and reliable — Active (voice-assistant
  STT + speaker identity) needs neither. If you enable the `passive` or
  `emote` component in options *without* having built those stacks in, the
  affected service idles with a log message telling you to rebuild; nothing
  crash-loops. To include them, rebuild with the matching build arg
  (`INCLUDE_PASSIVE_VAD=true` and/or `INCLUDE_EMOTE=true`). On a local
  add-on that means adding them under `args:` — but note the deprecated
  `build.yaml` path; the supported way now is to edit the `ARG` defaults at
  the top of the `Dockerfile` to `"true"` before installing.
- Emote's soft-import (`from voicebm_emote import ...`) resolves against
  `/home/user/voicebm`, but `voicebm_emote.py` is vendored under `bin/`.
  With Emote off (default) this is a harmless no-op; if you enable the emote
  stack and want it actually active, you'd also need that module reachable
  on the path.
- `sherpa-onnx` and `onnx-asr` both ship manylinux (glibc) wheels for amd64
  and aarch64 — verified against current PyPI, and the full default
  dependency set was confirmed to resolve without conflict — which is why
  this add-on builds on the Debian (not Alpine/musl) base. (This is also why
  the biometrics can't run inside HA Core's Alpine environment, and hence why
  the engine is a separate add-on rather than part of the integration.)

---

# Advanced / standalone configurations

**You do not need anything below for the default integration setup.** These
sections cover running the engine as a standalone transcriber, tapping room-mic
RTSP audio, automatic and hands-free enrollment, GPU acceleration, JARVIS-AIO,
and the full options reference.

## Standalone STT: the bundled transcriber (internal mode)

In `stt.mode: internal`, VoiceBM transcribes speech itself instead of the
integration doing it. Upstream VoiceBM's Active pipeline is designed against a
*separately installed* Wyoming ONNX ASR container: you'd run
[tboby/wyoming-onnx-asr](https://github.com/tboby/wyoming-onnx-asr)
yourself, then upstream's `scripts/deploy_handler.sh` would `docker cp` a
custom `handler.py` into it and restart it. That's two moving parts outside
this add-on's control, which is exactly what made it not self-contained.

This add-on vendors that same project (MIT-licensed, © Michael Hansen,
Thomas Boby) directly and runs it as one more supervised process
(`voicebm-wyoming-asr`) inside this container, on loopback only
(`127.0.0.1:10300` — never exposed to the host or network). VoiceBM's own
`handler.py.template` is written directly against this package's handler
constructor signature, so "deploying" it is just rendering the template
with this add-on's MQTT settings and overwriting the installed package's
`handler.py` in place before the ASR server starts — no external container,
no docker socket, no cross-container file copy.

Set the model under **Configuration → active**:
- `model_en` — English model name (default `nemo-parakeet-tdt-0.6b-v2`,
  see [onnx-asr's supported models](https://github.com/istupakov/onnx-asr?tab=readme-ov-file#supported-model-names)
  for alternatives, including smaller ones for lower-end hardware).
- `model_multilingual` — optional second model; leave blank to skip.
- `quantization` — e.g. `int8` for a smaller/faster (usually slightly less
  accurate) variant, where the model supports it.
- `device` — `cpu` (default), `gpu`, or `gpu-trt` if you've mapped a GPU
  into the add-on yourself.

The model downloads on first start into `/data/wyoming-models` (persistent
— not re-downloaded on restart or add-on update). Size varies by model;
the default is roughly 600MB–1GB. In the default integration mode the bundled
ASR never runs, so nothing is pre-baked into the image.

## Using your existing HAOS Whisper (external STT mode)

`stt.mode: external_whisper` is the standalone way to reuse an existing
**Whisper** add-on without the integration. (The integration itself already
transcribes through your Whisper, so if you're using the integration you don't
need this mode.) In that mode:

- **Whisper does all transcription** — VoiceBM stops transcribing entirely (its
  bundled ASR and STT bridge idle). One transcriber, no duplication.
- **VoiceBM still identifies the speaker** on the same utterance. A small
  Wyoming proxy (port `10400`) becomes the STT that Assist talks to: it forwards
  the audio to your Whisper add-on for the text, and in parallel hands the same
  audio to VoiceBM's identity engine (via its `analyze_request` MQTT + a shared
  WAV — no fork of VoiceBM's transcription code). VoiceBM publishes identity to
  MQTT exactly as before (`sensor.voicebm_active_speaker`,
  `binary_sensor.<person>_voice`), for JARVIS / the Ollama prompt to consume.

This is the right mode for a **Voice PE / ESPHome satellite** (no room mic to
tap for the passive pipeline) when you want to reuse your existing Whisper
*without* the integration.

Options under `stt`:
- `mode` — `internal` (VoiceBM transcribes), `external_whisper` (proxy + your
  Whisper), or `integration` (the default; the HA integration is the STT).
- `whisper_uri` — the Whisper add-on's Wyoming address, e.g.
  `tcp://a0d7b954-whisper:10300` (the official Whisper add-on's hostname) or
  `tcp://<ip>:10300`. **Find your exact value** in the Whisper add-on (its
  hostname is shown on its info page; container hostnames look like
  `<slug>-whisper`).
- `proxy_port` — the port Assist connects to (default `10400`).
- `identity_inject` — if `true`, prepend `"<name>: "` to Whisper's transcript
  (waits up to `identity_wait_ms` for the verdict). Default `false`, since
  identity already flows to JARVIS/Ollama via MQTT sensors — leave off unless
  you specifically want the name in the transcript text.

**Pipeline wiring in this mode:** point Assist's speech-to-text at the **proxy**
(Wyoming Protocol integration → your HA IP, port `10400`), *not* at the Whisper
add-on directly and *not* at VoiceBM's `10300`. The proxy is what fans out to
both. (Add a second Wyoming integration for `10400` if you already have one for
Whisper on 10300; set the pipeline to use the 10400 one.)

Note the port: VoiceBM's own bundled ASR uses 10300 in internal mode, and the
official Whisper add-on also uses 10300 — they don't collide because in
external mode VoiceBM's 10300 ASR is idle, and the proxy reaches Whisper at
`whisper_uri`. The proxy itself is on 10400 so it never clashes with either.

## RTSP audio nodes (Passive / Ambient)

The Passive and Ambient pipelines listen to always-on room audio rather than
voice-assistant utterances. A **node** is any device/process serving an RTSP
audio stream — not a camera. You still need something producing that stream;
VoiceBM just consumes it. Everything else — MQTT, speech-to-text, and speaker
identity — runs inside this one container with nothing else to install.

Define nodes under `nodes` (see the options reference below). Each needs
`node_id` (lowercase, no spaces), `rtsp_url`, and `recorder_enabled` and/or
`ambient_enabled`. Passive VAD and Ambient are opt-in at build time (see
[Known limitations](#known-limitations-of-this-packaging)).

## Automatic enrollment (optional)

By default, enrollment is manual: unrecognized voices land in the Speakers
panel's Pending list and you name them. If you'd rather have the add-on enroll
recurring speakers on its own, enable **Configuration → auto_enroll**.

It does this *conservatively*, reusing VoiceBM's own clustering and the same
enroll path the panel uses — so it behaves like a careful human, not a
firehose:
- It groups unrecognized utterances by voiceprint similarity (using
  VoiceBM's own clustering), rather than enrolling every raw utterance —
  otherwise every stranger, guest, or TV voice would become its own person.
- It only auto-enrolls a cluster that has at least `min_samples` samples
  (a real recurring speaker, not a one-off), is internally tight
  (`min_cohesion`, average intra-cluster voiceprint similarity — guards
  against a loose blob of different people being merged), and is **not**
  already a likely match for someone you've enrolled (so it won't create a
  duplicate identity).
- New people are named `{name_prefix} N` (default "Speaker 1", "Speaker
  2", …). Rename them any time from the panel or the Home Assistant
  device — the voiceprint is what matters, the label is cosmetic.

Options:
- `auto_enroll.enabled` — master switch (default off).
- `auto_enroll.min_samples` — how many clustered samples before a new
  speaker is created (default 6). Lower = enrolls sooner but riskier.
- `auto_enroll.min_cohesion` — 0–1 tightness gate (default 0.55). Raise it
  if you see different people merged into one; lower it if real speakers
  aren't being picked up.
- `auto_enroll.interval_s` — how often it checks (default 300s).
- `auto_enroll.name_prefix` — the auto-name prefix (default "Speaker").

Honest caveats: this is unsupervised speaker enrollment, and it *will*
sometimes enroll a house guest, or split one person across two IDs if their
voice varies a lot (phone vs. across-the-room). It only ever operates on the
Active pipeline's pending voices, so it needs the `active` component on.
Treat it as a convenience that gets you 80% there, then tidy names/merges in
the panel. Start with it off, watch what the manual Pending list catches
for a day, then enable it once you trust the clustering on your household.

## JARVIS-AIO integration

[JARVIS-AIO](https://github.com/sam3gp8/jarvis-aio) already has first-class
VoiceBM support built in — VoiceBM answers *"who is speaking,"* which is
exactly the signal JARVIS's identity resolver and visitor-learning want.
Wiring the two together is mostly configuration, plus one bridge this add-on
provides for hands-free enrollment.

**1. Identity (no code — just point JARVIS at VoiceBM's entities).** VoiceBM
publishes a per-person `binary_sensor.<person>_voice` (ON while they speak).
In JARVIS's config, set:
- `identity_voice_fingerprint: true`
- `voice_recognition_source: binary_sensor.*_voice`

JARVIS then treats VoiceBM's "current speaker" as its strongest identity tier.
That's the whole identity integration.

**2. Hands-free labelled enrollment (the good part).** When JARVIS is
confident who's speaking from its *other* signals (sole occupant, a recent
camera face match) but VoiceBM hasn't enrolled that voice yet, JARVIS fires a
`jarvis_voice_enroll_candidate` event carrying the **correct name**. That's a
labelled enrollment opportunity — strictly better than VoiceBM's blind
auto-enroller, which can only invent "Speaker N."

To close the loop, enable this add-on's bridge (`jarvis.enroll_bridge: true`)
and add a one-line HA automation that republishes JARVIS's event to the
bridge's topic:

```yaml
automation:
  - alias: JARVIS -> VoiceBM enroll
    trigger:
      - platform: event
        event_type: jarvis_voice_enroll_candidate
    action:
      - service: mqtt.publish
        data:
          topic: voicebm/jarvis/enroll_current
          payload: '{"display_name": "{{ trigger.event.data.person }}"}'
```

The bridge enrolls VoiceBM's newest pending voice under that name (via the
same enroll path the panel uses), but only if that pending clip is fresh
(≤30s), so it can't mislabel an older clip. Result: voice profiles build
themselves from ordinary conversation, under the *right* names, with no
manual clicks.

If you use JARVIS's labelled enrollment, leave VoiceBM's own `auto_enroll`
**off** — otherwise both try to enroll and you'll get duplicate/"Speaker N"
identities competing with JARVIS's correctly-named ones.

## GPU acceleration (NVIDIA/CUDA)

**The honest constraint first:** on *stock* Home Assistant OS, add-ons cannot
use an NVIDIA GPU — the Supervisor doesn't expose the NVIDIA container runtime
to add-ons. GPU works on a host built for it — specifically the
[`haos-gpu-ai`](https://github.com/sam3gp8/haos-gpu-ai) image, which promotes
`default-runtime: nvidia` at boot (via `gpu-autodetect`) so the NVIDIA runtime
hook injects the GPU into any container that requests it.

This add-on already matches that OS's **proven** GPU pattern: `full_access:
true` plus `NVIDIA_VISIBLE_DEVICES=all` /
`NVIDIA_DRIVER_CAPABILITIES=compute,utility` — the same approach as that
image's bundled Ollama add-on. (It deliberately does *not* use a
`/dev/nvidia*` `devices:` list, which would fail to start on the universal
image's Intel/AMD hosts.) The env vars are what fire the runtime hook; the
CUDA libraries come from the host's driver via the container toolkit.

To actually run on the GPU, two steps:
1. **Build the image with `ENABLE_GPU=true`** (edit the `ARG ENABLE_GPU`
   default at the top of the `Dockerfile` to `"true"`). This swaps the ASR
   stack to `onnxruntime-gpu` (CUDA execution provider — the hot path) and,
   if you enabled the passive-VAD/emote stacks, the CUDA build of torch.
2. **Set `active.device: gpu`** (or `gpu-trt` for TensorRT) in options — this
   flows straight to the bundled ASR server's provider selection.

A GPU image still runs CPU-only cleanly where no device is visible
(onnxruntime falls back). Verify it's on the GPU: `nvidia-smi` on the host
should show a python process holding VRAM once an utterance has been
transcribed. If it doesn't, the runtime isn't injecting and it's silently on
CPU.

Note that the bundled ASR (the main GPU consumer) idles in the default
`integration` mode, so the GPU build mainly matters for `internal` mode.

**Baking this into the OS image:** the accompanying
`haos-gpu-ai-voicebm-overlay/` folder drops VoiceBM into the `haos-gpu-ai`
build so it's *pre-installed* under Local add-ons (seeded like Ollama), rather
than copied in by hand. See that overlay's README.

## Full options reference

- `network.public_host` — how other devices (Home Assistant) reach this
  add-on for the audio server (port 9090). Leave blank to auto-use the
  container's hostname, which normally resolves fine inside the Supervisor
  network. Set it explicitly if you're proxying or on host networking.
- `components.*` — enable Active / Passive / Ambient / Emote independently,
  same as upstream's wizard step 1.
- `mqtt.use_addon_mqtt_service` — when true (default), pulls broker/user/pass
  from the Mosquitto broker add-on automatically via the Supervisor. Turn
  off and fill in `mqtt.broker` etc. to point at an external broker.
- `thresholds.*`, `voicebm.*` — same tunables as upstream's `config.json`
  (`gallery_max`, `active_lead_trim_ms`, `inject_identity`,
  `transcript_preferred`, match thresholds). These can also be changed live
  from the Speakers panel or Home Assistant entities — the engine writes back to
  `config.json` directly, and that file lives on the add-on's persistent
  storage, so it isn't reset by add-on restarts or updates.
- `active.*` — which bundled ASR model(s) to run; see
  [Standalone STT](#standalone-stt-the-bundled-transcriber-internal-mode).
- `stt.*` — transcription mode and its parameters; see
  [Using your existing HAOS Whisper](#using-your-existing-haos-whisper-external-stt-mode).
- `auto_enroll.*` — automatic enrollment; see
  [Automatic enrollment](#automatic-enrollment-optional).
- `jarvis.*` — JARVIS-AIO hands-free enrollment bridge; see
  [JARVIS-AIO integration](#jarvis-aio-integration).
- `nodes` — list of RTSP audio sources. Each needs `node_id` (lowercase, no
  spaces), `rtsp_url`, and `recorder_enabled` and/or `ambient_enabled`.
