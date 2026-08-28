"""Constants for the VoiceBM integration."""

DOMAIN = "voicebm"

# --- config entry keys ---
CONF_BACKEND_STT = "backend_stt_entity"      # existing Whisper STT entity to transcribe with
CONF_LANGUAGES = "languages"
CONF_IDENTITY_INJECT = "identity_inject"
CONF_IDENTITY_WAIT_MS = "identity_wait_ms"
CONF_SHARE_DIR = "share_dir"                 # where STT audio WAVs are dropped for the engine
CONF_GALLERY_DIR = "gallery_dir"             # where the engine stores the speaker gallery

DEFAULT_LANGUAGES = ["en"]
DEFAULT_IDENTITY_INJECT = False
DEFAULT_IDENTITY_WAIT_MS = 1200
DEFAULT_SHARE_DIR = "/share/voicebm/stt_requests"
# The headless engine stores its gallery/pending under /share/voicebm — /share
# maps identically in HA Core and every add-on (unlike the legacy `config` map,
# whose semantics changed in Supervisor and can silently point elsewhere).
DEFAULT_GALLERY_DIR = "/share/voicebm"

# --- MQTT topics (must match the VoiceBM engine add-on) ---
TOPIC_ANALYZE_REQUEST = "voicebm/stt/analyze_request"
TOPIC_ACTIVE_SPEAKER = "voicebm/active_speaker"
TOPIC_PENDING_ENROLL = "voicebm/pending_active/enroll"

TOPIC_MERGE_NAME_SET = "voicebm/thing/merge/name/set"
TOPIC_MERGE_EXECUTE_TRIGGER = "voicebm/thing/merge/execute/trigger"

# per-sample management (handled by the engine add-on's sample_manager service)
TOPIC_SAMPLES_LIST_REQ = "voicebm/samples/list_request"
TOPIC_SAMPLES_LIST_RES = "voicebm/samples/list_response"
TOPIC_SAMPLES_DEL_REQ = "voicebm/samples/delete_request"
TOPIC_SAMPLES_DEL_RES = "voicebm/samples/delete_response"

# Values the engine uses for "no confident speaker"
NON_SPEAKER_VALUES = {"", "none", "user", "unknown", "unavailable", None}

# Frontend panel
PANEL_URL_PATH = "voicebm"
PANEL_TITLE = "VoiceBM Speakers"
PANEL_ICON = "mdi:account-voice"
PANEL_WEBCOMPONENT = "voicebm-panel"
PANEL_STATIC_URL = "/voicebm_panel_static"
PANEL_JS_FILENAME = "voicebm-panel.js"

# Authenticated view that serves a pending clip's audio for playback
AUDIO_VIEW_URL = "/api/voicebm/pending_audio"


# --- per-person topic builders (must match the engine add-on) ---
def topic_transform_name_set(pid: str) -> str:
    return f"voicebm/thing/transform/{pid}/name/set"


def topic_transform_execute(pid: str) -> str:
    return f"voicebm/thing/transform/{pid}/execute"


def topic_enable_delete_set(pid: str) -> str:
    return f"voicebm/identity/{pid}/enable_delete/set"


def topic_delete(pid: str) -> str:
    return f"voicebm/identity/{pid}/delete"


def topic_merge_tag_set(pid: str) -> str:
    return f"voicebm/thing/merge/tag/{pid}/set"
