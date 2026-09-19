"""Frecency tracker for recently-visited directories.

We use the classic ``z`` / ``autojump`` formula: rank = freq * decay(age).
This rewards directories that are both frequent and recent without one
dominating the other.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from root_cli.paths import ensure_config_dir, history_path


# Soft cap so the file stays small.
MAX_ENTRIES = 500


@dataclass
class HistoryEntry:
    path: str
    freq: float
    last_seen: float  # unix timestamp


class History:
    def __init__(
        self,
        entries: Dict[str, HistoryEntry] | None = None,
        launches: Dict[str, HistoryEntry] | None = None,
    ):
        self.entries: Dict[str, HistoryEntry] = entries or {}
        # Files opened from the TUI preview pane. Kept separate from
        # `entries` so launched files never rank as cd targets.
        self.launches: Dict[str, HistoryEntry] = launches or {}

    # ----- persistence -----

    @staticmethod
    def _parse_entries(items) -> Dict[str, HistoryEntry]:
        return {
            str(item["path"]): HistoryEntry(
                path=str(item["path"]),
                freq=float(item.get("freq", 1.0)),
                last_seen=float(item.get("last_seen", time.time())),
            )
            for item in items
            if "path" in item
        }

    @classmethod
    def load(cls) -> "History":
        path = history_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls(
            entries=cls._parse_entries(data.get("entries", [])),
            # Absent in files written by older versions — that's fine.
            launches=cls._parse_entries(data.get("launches", [])),
        )

    def _prune(self, store: Dict[str, HistoryEntry]) -> Dict[str, HistoryEntry]:
        if len(store) <= MAX_ENTRIES:
            return store
        ranked = sorted(
            store.values(),
            key=lambda e: self._frecency(e, time.time()),
            reverse=True,
        )
        return {e.path: e for e in ranked[:MAX_ENTRIES]}

    def save(self) -> None:
        ensure_config_dir()
        # Prune to keep the file bounded.
        self.entries = self._prune(self.entries)
        self.launches = self._prune(self.launches)

        def dump(store: Dict[str, HistoryEntry]):
            return [
                {"path": e.path, "freq": e.freq, "last_seen": e.last_seen}
                for e in store.values()
            ]

        history_path().write_text(
            json.dumps(
                {"entries": dump(self.entries), "launches": dump(self.launches)},
                indent=2,
            ),
            encoding="utf-8",
        )

    # ----- updates -----

    @staticmethod
    def _bump(store: Dict[str, HistoryEntry], path: Path, now: float | None) -> None:
        key = str(Path(path).expanduser().resolve())
        ts = time.time() if now is None else now
        e = store.get(key)
        if e is None:
            store[key] = HistoryEntry(path=key, freq=1.0, last_seen=ts)
        else:
            e.freq += 1.0
            e.last_seen = ts

    def visit(self, path: Path, now: float | None = None) -> None:
        """Record a directory visit. Increments frequency, refreshes last-seen."""
        self._bump(self.entries, path, now)

    def record_launch(self, path: Path, now: float | None = None) -> None:
        """Record a file launched from the TUI (frecency, like visits)."""
        self._bump(self.launches, path, now)

    def forget(self, path: Path) -> bool:
        key = str(Path(path).expanduser().resolve())
        return self.entries.pop(key, None) is not None

    # ----- queries -----

    @staticmethod
    def _frecency(e: HistoryEntry, now: float) -> float:
        """Score = log1p(freq) * recency_decay.

        Decay is a piecewise function similar to z's:
        - <1h    : x4
        - <1d    : x2
        - <1w    : x0.5
        - older  : x0.25
        """
        age = max(0.0, now - e.last_seen)
        if age < 3600:
            decay = 4.0
        elif age < 86400:
            decay = 2.0
        elif age < 7 * 86400:
            decay = 0.5
        else:
            decay = 0.25
        return math.log1p(e.freq) * decay

    def ranked(self, limit: int | None = None) -> List[Tuple[Path, float]]:
        """Return (path, score) tuples sorted by frecency, descending.

        Paths that no longer exist on disk are filtered out lazily.
        """
        now = time.time()
        scored: List[Tuple[Path, float]] = []
        for e in self.entries.values():
            p = Path(e.path)
            if not p.exists() or not p.is_dir():
                continue
            scored.append((p, self._frecency(e, now)))
        scored.sort(key=lambda x: x[1], reverse=True)
        if limit is not None:
            scored = scored[:limit]
        return scored
