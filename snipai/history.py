"""Keep the last few answers so a toast or clipboard overwrite is not the only copy."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

log = logging.getLogger("snipai")

MAX_ANSWERS = 10


@dataclass
class HistoryEntry:
    id: str
    created_at: str
    headline: str
    full: str

    def when(self) -> datetime:
        try:
            return datetime.fromisoformat(self.created_at)
        except ValueError:
            return datetime.now()

    def when_label(self) -> str:
        dt = self.when()
        now = datetime.now()
        stamp = dt.strftime("%I:%M %p").lstrip("0")
        if dt.date() != now.date():
            return f"{dt.strftime('%b')} {dt.day} {stamp}"
        return stamp


class AnswerHistory:
    def __init__(self, path: Path | None = None, *, max_items: int = MAX_ANSWERS) -> None:
        self.path = path
        self.max_items = max(1, int(max_items))
        self.entries: list[HistoryEntry] = []
        self.load()

    def add(self, headline: str, full: str) -> HistoryEntry:
        entry = HistoryEntry(
            id=uuid4().hex[:12],
            created_at=datetime.now().isoformat(timespec="seconds"),
            headline=(headline or "Answer").strip() or "Answer",
            full=(full or "").strip(),
        )
        self.entries.insert(0, entry)
        del self.entries[self.max_items :]
        self.save()
        return entry

    def get(self, entry_id: str) -> HistoryEntry | None:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def load(self) -> None:
        if self.path is None or not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Could not read answer history: %s", exc)
            return
        items = raw.get("answers") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            return
        loaded: list[HistoryEntry] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            loaded.append(
                HistoryEntry(
                    id=str(item.get("id") or uuid4().hex[:12]),
                    created_at=str(item.get("created_at") or datetime.now().isoformat(timespec="seconds")),
                    headline=str(item.get("headline") or "Answer"),
                    full=str(item.get("full") or ""),
                )
            )
        self.entries = loaded[: self.max_items]

    def save(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"answers": [asdict(entry) for entry in self.entries]}
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        except OSError as exc:
            log.warning("Could not save answer history: %s", exc)
