FROM ghcr.io/home-assistant/base-debian:trixie

# Base image: HA's multi-arch base-debian (amd64+arm64), trixie codename.
# HA moved to multi-arch base images (2026.03.1+) and now recommends them
# over the old ${arch}-base-* names; trixie is current (bookworm is frozen).
# This add-on ships no build.yaml — Supervisor's legacy-builder support for
# it is deprecated as of the April 2026 BuildKit migration, so base image,
# labels, and args all live in this Dockerfile using the BUILD_ARCH /
# BUILD_VERSION args Supervisor supplies by default.
ARG BUILD_ARCH
ARG BUILD_VERSION="3.9.4"
# Optional pillars, OFF by default so the DEFAULT build is small and reliable:
#   INCLUDE_PASSIVE_VAD — pulls torch (CPU) + silero-vad for the passive VAD
#     filter. ~1GB. Needed only if you enable the "passive" component.
#   INCLUDE_EMOTE — pulls funasr (+transformers, numba, librosa, modelscope,
#     the Aliyun SDK: 80+ packages, several GB, the most fragile part of any
#     build here). Needed only if you enable the "emote" (SER) component.
# Active (voice-assistant STT + identity) and the identity engine need
# NEITHER, so leaving both off gives a lean image that builds fast.
ARG INCLUDE_PASSIVE_VAD="false"
ARG INCLUDE_EMOTE="false"
# GPU (NVIDIA/CUDA) acceleration. OFF by default because it only works where
# the container is actually given the GPU — i.e. a host with the NVIDIA
# Container Toolkit and the `nvidia` runtime exposed to add-ons (a Supervised
# install you control, or a custom GPU-enabled HAOS). Stock HAOS does NOT give
# add-ons the NVIDIA runtime, so the default CPU image is correct there.
# When true: onnxruntime-gpu (CUDA ASR — the hot path), CUDA torch, and the
# NVIDIA runtime env below. The engine still falls back to CPU at runtime if
# no device is visible, so a GPU image is safe to run on a CPU-only host too.
ARG ENABLE_GPU="false"
ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONNOUSERSITE=1 \
    VOICEBM_HOME=/home/user \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

# ---------------------------------------------------------------------------
# System packages
# VoiceBM's own scripts assume: python3, ffmpeg (recorder + ambient/passive),
# ffprobe (rtsp validation), curl (model download).
# ---------------------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        ffmpeg curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Copy-proof packaging: the entire rootfs tree ships as ONE flat file
# (rootfs.tar.gz) instead of 200+ nested files. Rationale: a partial folder
# copy to /addons (File editor can't upload folders; a Samba drag of the
# files instead of the folder drops the nested tree) previously produced a
# build context missing rootfs/ entirely — Supervisor failed with
# "/rootfs/...: not found" and a 23KB context. With a flat layout, ANY copy
# method that moves plain files works, and a missing tarball fails loudly on
# the very first COPY below.
# ---------------------------------------------------------------------------
COPY rootfs.tar.gz /tmp/rootfs.tar.gz
RUN mkdir -p /tmp/build-rootfs && \
    tar -xzf /tmp/rootfs.tar.gz -C /tmp/build-rootfs && \
    test -d /tmp/build-rootfs/opt/voicebm-addon && \
    test -d /tmp/build-rootfs/etc/s6-overlay

# ---------------------------------------------------------------------------
# Core Python dependencies — identity engine, dashboard, STT bridge, watchers.
# Always installed; resolves cleanly on its own (verified).
# ---------------------------------------------------------------------------
RUN pip3 install --break-system-packages --no-cache-dir \
        paho-mqtt \
        numpy \
        sherpa-onnx \
        watchdog \
        flask \
        flask-cors \
        fastapi \
        "uvicorn[standard]" \
        python-multipart \
        soundfile \
        requests

# ---------------------------------------------------------------------------
# Bundled Wyoming ONNX ASR server (vendored from tboby/wyoming-onnx-asr,
# MIT-licensed — © Michael Hansen, Thomas Boby). Upstream VoiceBM's Active
# pipeline expects this running as a SEPARATE container that it docker-cp's
# a custom handler.py into. Since VoiceBM's handler.py.template is written
# directly against this exact package's constructor signature
# (NemoAsrEventHandler(wyoming_info, models, model_lock, *args, **kwargs) —
# verified against the vendored source), it runs as one more supervised
# process in THIS container instead: no separate container, no docker
# socket, no cross-container file copy. The voicebm-wyoming-asr s6 service
# renders the handler from VoiceBM's template with this add-on's MQTT
# settings and overwrites the installed package's handler.py with it,
# every time that service (re)starts.
# ---------------------------------------------------------------------------
RUN cp -a /tmp/build-rootfs/opt/wyoming-onnx-asr-src /opt/wyoming-onnx-asr-src
RUN if [ "$ENABLE_GPU" = "true" ]; then \
        echo "Installing GPU (CUDA) ASR extra"; \
        pip3 install --break-system-packages --no-cache-dir "/opt/wyoming-onnx-asr-src[gpu]"; \
    else \
        pip3 install --break-system-packages --no-cache-dir "/opt/wyoming-onnx-asr-src[cpu]"; \
    fi && \
    rm -rf /opt/wyoming-onnx-asr-src

# ---------------------------------------------------------------------------
# OPTIONAL: passive VAD stack (torch CPU + silero-vad). Only when the passive
# component is used. Installed as an explicit CPU-only torch FIRST so nothing
# downstream can pull the multi-GB CUDA torch from PyPI, then silero-vad
# (which ships the model files in the wheel — no runtime GitHub fetch).
# The Silero model is also pre-seeded into the torch.hub cache here so
# vad_filter.py's unmodified torch.hub.load('snakers4/silero-vad', ...) finds
# it locally instead of hitting an unanswerable interactive "trust this repo?
# (y/N)" prompt at runtime (which otherwise crash-loops the VAD service).
# ---------------------------------------------------------------------------
RUN if [ "$INCLUDE_PASSIVE_VAD" = "true" ] || [ "$INCLUDE_EMOTE" = "true" ]; then \
        if [ "$ENABLE_GPU" = "true" ]; then \
            echo "Installing CUDA torch for VAD/emote"; \
            pip3 install --break-system-packages --no-cache-dir torch ; \
        else \
            pip3 install --break-system-packages --no-cache-dir \
                torch --index-url https://download.pytorch.org/whl/cpu && \
            pip3 install --break-system-packages --no-cache-dir onnxruntime ; \
        fi && \
        pip3 install --break-system-packages --no-cache-dir silero-vad && \
        python3 -c "import torch; torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False, onnx=True, trust_repo=True)" \
            || echo 'WARNING: Silero VAD pre-cache failed at build time; passive VAD may retry-loop at runtime' ; \
    fi

# ---------------------------------------------------------------------------
# OPTIONAL: Emote / SER stack (funasr + transformers). Large and the most
# dependency-heavy part of any build (80+ transitive packages). Only when the
# emote component is used. torch is already CPU-pinned above, so funasr reuses
# it rather than pulling its own.
# ---------------------------------------------------------------------------
RUN if [ "$INCLUDE_EMOTE" = "true" ]; then \
        pip3 install --break-system-packages --no-cache-dir \
            transformers funasr ; \
    fi

# ---------------------------------------------------------------------------
# Vendor the VoiceBM engine, laid out exactly as upstream expects it, because
# the engine scripts hardcode /home/user/voicebm paths internally (this is
# how upstream's own deploy_global_services.sh works too — it sed-rewrites
# a generic /home/user placeholder to the real target path). Here the
# container itself IS the dedicated machine, so /home/user/voicebm is real
# and permanent; only the data-bearing subdirectories get symlinked to /data
# (the add-on's persistent volume) at startup by init-voicebm-config.
# ---------------------------------------------------------------------------
RUN mkdir -p /home/user/voicebm/bin /home/user/.local/bin /home/user/sherpa_models

# ---------------------------------------------------------------------------
# Several vendored scripts (embed_node.sh, embed_stt.sh, ser_infer.sh,
# voicebm_ambient_hooks.py) hardcode upstream's conda env path
# (/home/user/miniforge3/envs/vb/bin/python3) rather than reading it from
# config.json. Rather than patch upstream source, shim that exact path to
# the container's real python3 — and give embed_node.sh's
# `source .../conda.sh && conda activate vb` a harmless no-op to run against.
# ---------------------------------------------------------------------------
RUN mkdir -p /home/user/miniforge3/envs/vb/bin /home/user/miniforge3/etc/profile.d && \
    ln -s "$(command -v python3)" /home/user/miniforge3/envs/vb/bin/python3 && \
    printf '%s\n' \
        '# no-op shim: VoiceBM add-on runs system python3 directly, not a real conda env' \
        'conda() { return 0; }' \
        > /home/user/miniforge3/etc/profile.d/conda.sh

RUN cp -a /tmp/build-rootfs/opt/voicebm-src/bin/*.py /home/user/voicebm/bin/ && \
    cp -a /tmp/build-rootfs/opt/voicebm-src/bin/*.sh /home/user/voicebm/bin/ && \
    cp -a /tmp/build-rootfs/opt/voicebm-src/templates /home/user/voicebm/templates && \
    cp -a /tmp/build-rootfs/opt/voicebm-src/VoiceBM_Guide.html /home/user/voicebm/VoiceBM_Guide.html

# voicebm_config.py + voicebm_dashboard.py live at the base ROOT (every
# service does sys.path.insert(0, '/home/user/voicebm') and imports
# voicebm_config from there) — mirrors upstream's deploy layout exactly.
RUN mv /home/user/voicebm/bin/voicebm_config.py    /home/user/voicebm/voicebm_config.py && \
    mv /home/user/voicebm/bin/voicebm_dashboard.py /home/user/voicebm/voicebm_dashboard.py && \
    mv /home/user/voicebm/bin/sherpa_embed.py      /home/user/.local/bin/sherpa_embed.py && \
    mv /home/user/voicebm/bin/ser_worker.py        /home/user/.local/bin/ser_worker.py && \
    chmod +x /home/user/voicebm/bin/*.sh /home/user/.local/bin/*.py

# ---------------------------------------------------------------------------
# Add-on glue: config generator, node supervisor, ASR handler renderer, s6
# service scaffolding
# ---------------------------------------------------------------------------
RUN cp -a /tmp/build-rootfs/opt/voicebm-addon /opt/voicebm-addon
RUN chmod +x /opt/voicebm-addon/*.py /opt/voicebm-addon/*.sh

RUN cp -a /tmp/build-rootfs/etc/s6-overlay/. /etc/s6-overlay/
# Longrun `run` scripts and the oneshot script bodies must be executable.
# NOTE: oneshot `up` files themselves are NOT scripts — each contains a
# single line naming an executable under /etc/s6-overlay/scripts (see
# init-voicebm-config / wait-mqtt). s6-rc-compile parses `up` files with
# execline's text rules, not a shell, so the real bash init logic lives in
# those separate script files, and every longrun depends on `base` +
# `wait-mqtt` so it can't start before config.json exists. (An earlier build
# put the bash directly in the `up` file, which failed with "unable to exec
# set"; a later one moved it to /etc/cont-init.d, which runs AFTER the user
# bundle in this base image and so still raced the services. This is the
# correct arrangement.)
RUN find /etc/s6-overlay/s6-rc.d -type f \( -name run -o -name up -o -name finish \) -exec chmod +x {} \; && \
    chmod +x /etc/s6-overlay/scripts/* && \
    rm -rf /tmp/build-rootfs /tmp/rootfs.tar.gz

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}" \
    org.opencontainers.image.title="VoiceBM" \
    org.opencontainers.image.description="Local voice biometrics engine for Home Assistant" \
    org.opencontainers.image.source="https://github.com/cybericebyte/VoiceBM" \
    org.opencontainers.image.licenses="MIT"
