"""
Writing results as JSON, for the web dashboard to read.

Every tool produces two things: a Markdown report (readable in GitHub's UI
and in an email) and a JSON file (read by the dashboard page). This module
handles the JSON half.

The files land in docs/data/, which is the folder GitHub Pages serves. The
workflow commits them back to the repository after each run, so the
dashboard always shows the most recent result without needing a server.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT

DATA_DIR = ROOT / "docs" / "data"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(name: str, payload: dict) -> Path:
    """
    Save a payload to docs/data/<name>.json.

    A 'generated_at' timestamp is always added, so the dashboard can tell you
    how stale the data is. That matters during a draft, where a board that is
    quietly ten minutes old is worse than no board at all.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": now_iso(), **payload}
    path = DATA_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path


def write_error(name: str, message: str, extra: dict | None = None) -> Path:
    """
    Record a failure in the same place a success would go.

    The dashboard reads this and shows the error on the relevant tab rather
    than displaying stale data as though it were current. Silently showing
    old numbers is the failure mode worth engineering against.
    """
    payload = {"ok": False, "error": message}
    if extra:
        payload.update(extra)
    return write_json(name, payload)
