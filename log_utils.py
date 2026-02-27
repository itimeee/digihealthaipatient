"""
Lightweight structured logging helpers for this project.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

_LEVEL_ORDER = {
    "DEBUG": 10,
    "INFO": 20,
    "PERF": 25,
    "WARNING": 30,
    "ERROR": 40,
}

_DEFAULT_LEVEL = os.environ.get("APP_LOG_LEVEL", "PERF").upper()
_SHOW_PERF = os.environ.get("APP_LOG_SHOW_PERF", "1") not in {"0", "false", "False"}


def _normalize_level(level: str) -> str:
    lvl = (level or "INFO").upper()
    if lvl == "WARN":
        lvl = "WARNING"
    return lvl if lvl in _LEVEL_ORDER else "INFO"


def _should_log(level: str) -> bool:
    lvl = _normalize_level(level)
    cfg = _normalize_level(_DEFAULT_LEVEL)
    if lvl == "PERF" and not _SHOW_PERF:
        return False
    return _LEVEL_ORDER[lvl] >= _LEVEL_ORDER[cfg]


def _fmt_value(value):
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _fmt_field(key: str, value) -> str:
    safe_val = _fmt_value(value).replace("\n", "\\n")
    if any(ch in safe_val for ch in (" ", "=", '"')):
        safe_val = '"' + safe_val.replace('"', "'") + '"'
    return f"{key}={safe_val}"


def log_event(level: str, component: str, event: str, message: str = "", **fields):
    """
    Emit one-line structured log.
    """
    lvl = _normalize_level(level)
    if not _should_log(lvl):
        return

    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    parts = [
        _fmt_field("ts", ts),
        _fmt_field("lvl", lvl),
        _fmt_field("cmp", component),
        _fmt_field("evt", event),
    ]

    if message:
        parts.append(_fmt_field("msg", message))

    for key in sorted(fields.keys()):
        value = fields[key]
        if value is None:
            continue
        parts.append(_fmt_field(key, value))

    print("[LOG] " + " ".join(parts))


def classify_tts_error(error_msg: str) -> tuple[str, str]:
    """
    Classify TTS errors into compact reason codes for easier triage.
    """
    msg = (error_msg or "").lower()

    if any(token in msg for token in ("deadline exceeded", "timeout", "timed out", "504")):
        return ("upstream_timeout", "TTS upstream timeout/deadline")
    if any(token in msg for token in ("502", "503", "gateway", "service unavailable", "unavailable")):
        return ("upstream_gateway", "TTS upstream gateway/service unstable")
    if "quota" in msg:
        return ("quota_exceeded", "TTS quota exceeded")
    if "permission" in msg or "403" in msg:
        return ("permission_denied", "Missing TTS permissions/API enablement")
    if "voice" in msg and "does not exist" in msg:
        return ("invalid_voice", "Requested voice not available for model/language")
    if "model" in msg and "not found" in msg:
        return ("invalid_model", "Requested TTS model unavailable")
    if "prompt" in msg and "support" in msg:
        return ("sdk_version_mismatch", "Installed SDK missing Gemini TTS fields")

    return ("unknown", "Unknown TTS failure")
