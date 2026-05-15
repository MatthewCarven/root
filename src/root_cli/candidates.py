"""Aggregate candidates from all four sources into one ranked list.

Sources:
- BOOKMARK : user-defined named shortcuts
- RECENT   : frecency-tracked history
- TREE     : children of the current browse directory (plus '..' when applicable)
- SEARCH   : one-level-deep glob of the configured search_roots

When the query is empty we show a friendly default view (bookmarks +
recents + ".." (if not at filesystem root) + tree children). When the
user types, all sources are merged, scored, and ranked together.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from root_cli.config import Bookmarks, Config
from root_cli.history import History
from root_cli.matcher import score


class Source(enum.Enum):
    BOOKMARK = "bookmark"
    RECENT = "recent"
    TREE = "tree"
    SEARCH = "search"

    @property
    def icon(self):
        return {
            Source.BOOKMARK: "*",
            Source.RECENT: "~",
            Source.TREE: ">",
            Source.SEARCH: "?",
        }[self]


@dataclass
class Candidate:
    path: Path
    source: Source
    label: str
    score: float = 0.0
    match_fields: List[str] = field(default_factory=list)

    @property
    def fields(self):
        return [self.label, str(self.path)] + self.match_fields

    @property
    def is_parent_entry(self):
        """True when this Candidate is the synthetic '..' parent row."""
        return self.source is Source.TREE and self.label == ".."


def _tree_children(directory, show_hidden):
    try:
        for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if not show_hidden and child.name.startswith("."):
                continue
            try:
                if child.is_dir():
                    yield child
            except OSError:
                continue
    except (PermissionError, OSError, FileNotFoundError):
        return


def _glob_search_roots(roots):
    """One level deep: each configured pattern is expanded with Path.glob."""
    seen = set()
    for raw in roots:
        s = str(raw)
        if any(ch in s for ch in "*?["):
            parent = raw.parent
            pattern = raw.name
            try:
                matches = list(parent.glob(pattern))
            except OSError:
                matches = []
        else:
            matches = [raw] if raw.exists() else []
        for m in matches:
            try:
                if not m.is_dir():
                    continue
            except OSError:
                continue
            key = str(m.resolve())
            if key in seen:
                continue
            seen.add(key)
            yield m


@dataclass
class CandidateContext:
    config: Config
    bookmarks: Bookmarks
    history: History
    cwd: Path

    def collect(self, query):
        if not query:
            return self._default_view()
        return self._search(query)

    def _default_view(self):
        out = []
        for name, p in self.bookmarks.items():
            out.append(Candidate(
                path=Path(p),
                source=Source.BOOKMARK,
                label=name,
                match_fields=[str(p)],
            ))
        for p, _s in self.history.ranked(limit=self.config.recent_limit):
            if any(c.path == p for c in out):
                continue
            out.append(Candidate(path=p, source=Source.RECENT, label=str(p)))
        # ".." parent entry — shown only when we're not already at the
        # filesystem root of a drive. Path.parent returns the same path
        # for "/" and for "C:\\", which makes this check portable.
        parent = self.cwd.parent
        if parent != self.cwd:
            out.append(Candidate(path=parent, source=Source.TREE, label=".."))
        for child in _tree_children(self.cwd, self.config.show_hidden):
            out.append(Candidate(path=child, source=Source.TREE, label=child.name))
        return out

    def _search(self, query):
        pool = []
        for name, p in self.bookmarks.items():
            pool.append(Candidate(
                path=Path(p),
                source=Source.BOOKMARK,
                label=name,
                match_fields=[str(p)],
            ))
        for p, _s in self.history.ranked():
            pool.append(Candidate(path=p, source=Source.RECENT, label=str(p)))
        for child in _tree_children(self.cwd, self.config.show_hidden):
            pool.append(Candidate(path=child, source=Source.TREE, label=child.name))
        for m in _glob_search_roots(self.config.expanded_search_roots()):
            pool.append(Candidate(path=m, source=Source.SEARCH, label=m.name))

        priority = {
            Source.BOOKMARK: 4,
            Source.RECENT: 3,
            Source.SEARCH: 2,
            Source.TREE: 1,
        }
        by_path = {}
        for cand in pool:
            s = max((score(query, f) for f in cand.fields), default=float("-inf"))
            if s == float("-inf"):
                continue
            cand.score = s
            key = str(cand.path)
            existing = by_path.get(key)
            if existing is None:
                by_path[key] = cand
            else:
                if priority[cand.source] > priority[existing.source]:
                    cand.score = max(cand.score, existing.score)
                    by_path[key] = cand
                else:
                    existing.score = max(existing.score, cand.score)

        results = list(by_path.values())
        results.sort(
            key=lambda c: (c.score, priority[c.source]),
            reverse=True,
        )
        return results[: self.config.max_results]


def commit_path(history, path):
    history.visit(path)
    history.save()
