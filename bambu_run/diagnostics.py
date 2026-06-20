"""
Pure helpers for the `bambu_diagnose` management command.

Kept separate from the command itself (and free of Django/network imports)
so the report-building and redaction logic can be unit-tested without
talking to the real Bambu Lab cloud or MQTT broker.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Keys whose values are always replaced outright, regardless of nesting depth.
_SECRET_KEY_SUBSTRINGS = ("password", "token", "secret", "access_code", "authorization")

# Keys that identify a specific physical device/spool/account — not secret,
# but identifying, so they're partially masked by default before anything
# gets pasted into a public GitHub issue.
_IDENTIFIER_KEYS = {"dev_id", "device_id", "serial_number", "tray_uuid", "tag_uid", "uid"}


def _mask_identifier(value: Any) -> Any:
    if not isinstance(value, str) or len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def redact_diagnostics(data: Any, redact: bool = True) -> Any:
    """Recursively redact secrets and mask identifiers in a diagnostics payload.

    `redact=False` returns the data unchanged — only for the reporter's own
    local debugging, never for anything posted publicly.
    """
    if not redact:
        return data
    return _redact(data)


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            lowered = key.lower()
            if any(secret in lowered for secret in _SECRET_KEY_SUBSTRINGS):
                result[key] = "***REDACTED***"
            elif lowered in _IDENTIFIER_KEYS:
                result[key] = _mask_identifier(value)
            else:
                result[key] = _redact(value)
        return result
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    return obj


def build_diagnostics_report(
    devices: List[Dict[str, Any]],
    raw_payloads: Dict[str, Optional[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Assemble the (pre-redaction) diagnostics report from discovered devices
    and whatever raw MQTT payload was captured for each during the listen window.
    """
    device_entries = []
    for device in devices:
        dev_id = device.get("dev_id")
        payload = raw_payloads.get(dev_id)
        entry = {
            "device_info": device,
            "raw_mqtt_payload": payload,
        }
        if payload is None:
            entry["note"] = "No MQTT data received within the listen window."
        device_entries.append(entry)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "device_count": len(devices),
        "devices": device_entries,
    }
