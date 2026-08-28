<!-- Release v1.0.0 · integration 1.0.0 · engine add-on 3.10.0 -->
# voicebm-ha — VoiceBM for Home Assistant (HACS integration + engine add-on)

> **Built on [VoiceBM](https://github.com/cybericebyte/VoiceBM) by
> [@cybericebyte](https://github.com/cybericebyte).** All of the voice-biometrics
> engine — speaker embeddings, gallery matching, enrollment, the whole identity
> core — is @cybericebyte's original work, released under the MIT License
> (© 2025 cybericebyte). This project does **not** claim that work. It is a
> standalone Home Assistant packaging of it: a native HA **integration** and a
> headless **engine add-on**, so VoiceBM installs cleanly via HACS and runs as a
> first-class part of a Home Assistant voice pipeline. Both copyright notices are
> retained in [`LICENSE`](LICENSE), as MIT requires. Please star and support the
> [original project](https://github.com/cybericebyte/VoiceBM).

## What this fork adds

Upstream VoiceBM is a host-installed engine. This fork packages it for Home
Assistant OS as two pieces that work together:

- **`custom_components/voicebm/`** — a native HA integration (HACS-installable).
  It registers as a Speech-to-text engine that transcribes through your existing
  Whisper and adds speaker identity on the same audio, and it provides a native
  **VoiceBM Speakers** sidebar panel (rename / merge / delete / enroll), served
  through Home Assistant so it works over HTTPS with no separate port.
- **`voicebm-engine-addon/`** — the headless engine add-on. It runs the original
  VoiceBM biometrics (the ML needs a glibc ONNX runtime, which can't run inside
  HA Core's Alpine environment — hence a separate container). You install it
  once; the integration configures and starts it for you.

The two communicate over MQTT + a shared `/share/voicebm` folder. Transcription
never depends on identity: if the engine is down you still get Whisper's
transcript, so adding VoiceBM as your STT engine can't break your voice pipeline.

## Install

### 1. Integration (HACS)
1. HACS → Integrations → ⋮ → **Custom repositories** → add
   `https://github.com/sam3gp8/voicebm-ha`, category **Integration**.
2. Install **VoiceBM (Whisper + Speaker Identity)** → **restart Home Assistant**.

(Or copy `custom_components/voicebm/` into `config/custom_components/` manually.)

### 2. Engine add-on
Copy the **`voicebm-engine-addon/`** folder into `/addons/` on your HAOS box so
`/addons/voicebm/config.yaml` exists, then Settings → Add-ons → Add-on Store →
⋮ → **Check for updates** → install **VoiceBM** from *Local add-ons*. The folder
is flat (`config.yaml`, `Dockerfile`, `rootfs.tar.gz`, docs) so any copy method
works. First start builds the image on-device (needs internet, a few minutes).

> Prefer an add-on repository? Point Settings → Add-ons → Add-on Store → ⋮ →
> Repositories at `https://github.com/sam3gp8/voicebm-ha` and install from there.

### 3. Wire it up
1. Settings → Devices & Services → **Add Integration** → **VoiceBM** (auto-picks
   your Whisper if it's the only other STT engine).
2. Settings → Voice assistants → your pipeline → **Speech-to-text** →
   **VoiceBM (Whisper + Identity)**.
3. Speak a couple of commands, then open **VoiceBM Speakers** in the sidebar →
   *Pending voices* → name yourself. Done.

Full setup, GPU notes, and the JARVIS / Ollama integration are documented in
`voicebm-engine-addon/DOCS.md` and `custom_components/voicebm/` READMEs.

## Prerequisites
- MQTT configured in Home Assistant.
- A working Whisper add-on (VoiceBM transcribes *through* it — it isn't replaced).
- Home Assistant OS or Supervised (the engine add-on needs the Supervisor).

## Credit & license

Original VoiceBM: **[@cybericebyte](https://github.com/cybericebyte)** —
<https://github.com/cybericebyte/VoiceBM>. Licensed MIT (© 2025 cybericebyte);
see [`LICENSE`](LICENSE), retained from upstream. This fork's added HA
integration and add-on packaging are provided under the same MIT terms.
