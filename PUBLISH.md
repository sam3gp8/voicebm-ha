# How to publish this as a standalone repo

I can't create the repo or push for you (no write access to your GitHub
account), so here's the exact copy-paste. This is a **new standalone repo**, not
a fork — clean history, its own `LICENSE` (which preserves @cybericebyte's
original copyright notice as MIT requires).

The repo root already has everything in the right place:

```
custom_components/voicebm/     ← the HA integration (HACS installs this)
voicebm-engine-addon/          ← the headless engine add-on (flat: config.yaml,
                                  Dockerfile, rootfs.tar.gz, docs)
hacs.json                      ← makes HACS recognize the repo (integration)
repository.json                ← makes the add-on installable as an add-on repo
LICENSE                        ← MIT, both copyright notices retained
README.md                      ← credits @cybericebyte prominently
```

## Option A — GitHub UI (simplest)

1. <https://github.com/new> → name it **`voicebm-ha`** → create it **empty**
   (no README/license/gitignore — this bundle provides them).
2. From the folder extracted from this zip:
   ```bash
   cd voicebm-ha
   git init -b main
   git add .
   git commit -m "voicebm-ha: Home Assistant integration + engine add-on for VoiceBM

   Standalone Home Assistant packaging of VoiceBM (by @cybericebyte, MIT):
   - custom_components/voicebm: native STT + speaker-identity integration
     with a native sidebar speaker-management panel
   - voicebm-engine-addon: headless voice-biometrics engine add-on
   Engine and original copyright retained; all biometrics work is @cybericebyte's."
   git remote add origin https://github.com/sam3gp8/voicebm-ha.git
   git push -u origin main
   ```

## Option B — GitHub CLI (`gh`)

```bash
cd voicebm-ha
git init -b main && git add . && git commit -m "voicebm-ha: HA integration + engine add-on for VoiceBM"
gh repo create sam3gp8/voicebm-ha --public --source . --remote origin --push
```

## After pushing — install in Home Assistant

**Integration (HACS):**
1. HACS → Integrations → ⋮ → **Custom repositories**.
2. Add `https://github.com/sam3gp8/voicebm-ha`, category **Integration** → add.
3. Install **VoiceBM (Whisper + Speaker Identity)** → restart HA.

**Engine add-on** (installed separately — it's not a HACS integration):
- Copy `voicebm-engine-addon/` into `/addons/`, **or** add the same repo URL
  under Settings → Add-ons → Add-on Store → ⋮ → **Repositories**.

## Notes

- **Nice to have:** on the GitHub repo page, add topics like `home-assistant`,
  `hacs`, `voice-assistant`, `speaker-recognition`, and cut a release/tag
  (e.g. `v1.0.0`) — HACS shows tagged releases and it's required if you ever
  submit to the public HACS store. As a **custom repository** (steps above) it
  works immediately without any of that.
- **Attribution** is in the README, `LICENSE`, the integration manifest, and the
  add-on docs. Keeping @cybericebyte's copyright notice is MIT's one condition —
  don't remove it.
