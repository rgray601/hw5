"""Append-only audit log. Runs add steps. Nothing here clears the file."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_core import to_json

from models import AuditStep

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "output" / "audit_trail.json"
PREVIEW_CHARS = 500
_lock = threading.Lock()


def _preview(value: Any) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else to_json(value).decode("utf-8", "replace")
    text = " ".join(text.split())
    if len(text) <= PREVIEW_CHARS:
        return text
    return text[: PREVIEW_CHARS - 1] + "…"


def append_step(**fields: Any) -> None:
    """Validate one step and append it. Existing rows stay."""
    for key in ("args", "result", "reply", "stopped"):
        value = fields.get(key)
        if value is not None and not isinstance(value, str):
            fields[key] = _preview(value)
    step = AuditStep(**fields)
    payload = step.model_dump()
    for key in ("args", "result", "reply"):
        if payload.get(key):
            payload[key] = _preview(payload[key])
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        rows: list[Any] = []
        if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size > 0:
            try:
                loaded = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
                rows = loaded if isinstance(loaded, list) else [loaded]
            except json.JSONDecodeError:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                AUDIT_PATH.replace(AUDIT_PATH.with_name(f"audit_trail.corrupt-{stamp}.json"))
                rows = []
        rows.append(payload)
        temporary = AUDIT_PATH.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(AUDIT_PATH)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
