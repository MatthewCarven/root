"""Config and bookmarks — TOML on disk, dicts in memory."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - py3.10 fallback
    import tomli as tomllib

from root_cli.paths import bookmarks_path, config_path, ensure_config_dir


DEFAULT_CONFIG_TOML = """\
# root config file

# Directories that get glob-expanded one level deep and offered as
# candidates when you type a search query. Tilde and env vars are expanded.
# Examples:
#   search_roots = ["~/code/*", "~/Documents/*", "~/projects/*"]
search_roots = []

# Maximum number of results to show in the UI at once.
max_results = 50

# How many recents to surface in the unfiltered view.
recent_limit = 10

# Whether to show hidden (dot) directories in the tree browser.
show_hidden = false

# Folders your git repo ignores (build/, dist/, __pycache__/ ...):
#   "dim"  = show them dimmed, after everything else (default)
#   "hide" = leave them out of the tree and preview entirely
#   "show" = treat them like any other folder
gitignored = "dim"

# Milliseconds the cursor must rest on a row before the preview pane
# lists it. Keeps holding up/down smooth. 0 = update instantly.
preview_delay_ms = 333
"""


GITIGNORED_MODES = ("dim", "hide", "show")


def _gitignored_mode(raw: object) -> str:
    """Unknown values fall back to the default rather than crashing."""
    mode = str(raw).strip().lower()
    return mode if mode in GITIGNORED_MODES else "dim"


@dataclass
class Config:
    search_roots: List[str] = field(default_factory=list)
    max_results: int = 50
    recent_limit: int = 10
    show_hidden: bool = False
    preview_delay_ms: int = 333
    gitignored: str = "dim"

    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        if not path.exists():
            # Seed a default config so users have a discoverable file to edit.
            ensure_config_dir()
            path.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
            return cls()
        with path.open("rb") as f:
            data = tomllib.load(f)
        return cls(
            search_roots=list(data.get("search_roots", [])),
            max_results=int(data.get("max_results", 50)),
            recent_limit=int(data.get("recent_limit", 10)),
            show_hidden=bool(data.get("show_hidden", False)),
            preview_delay_ms=max(0, int(data.get("preview_delay_ms", 333))),
            gitignored=_gitignored_mode(data.get("gitignored", "dim")),
        )

    def save(self) -> None:
        ensure_config_dir()
        config_path().write_bytes(
            tomli_w.dumps(
                {
                    "search_roots": self.search_roots,
                    "max_results": self.max_results,
                    "recent_limit": self.recent_limit,
                    "show_hidden": self.show_hidden,
                    "preview_delay_ms": self.preview_delay_ms,
                    "gitignored": self.gitignored,
                }
            ).encode("utf-8")
        )

    def expanded_search_roots(self) -> List[Path]:
        """Resolve each configured root once (tilde + env vars)."""
        out: List[Path] = []
        for raw in self.search_roots:
            expanded = Path(raw).expanduser()
            out.append(expanded)
        return out


@dataclass
class Bookmarks:
    """Named shortcuts: alias -> absolute path."""

    entries: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Bookmarks":
        path = bookmarks_path()
        if not path.exists():
            return cls()
        with path.open("rb") as f:
            data = tomllib.load(f)
        raw = data.get("bookmarks", {}) or {}
        return cls(entries={str(k): str(v) for k, v in raw.items()})

    def save(self) -> None:
        ensure_config_dir()
        bookmarks_path().write_bytes(
            tomli_w.dumps({"bookmarks": self.entries}).encode("utf-8")
        )

    def add(self, name: str, path: Path) -> None:
        self.entries[name] = str(Path(path).expanduser().resolve())

    def remove(self, name: str) -> bool:
        return self.entries.pop(name, None) is not None

    def get(self, name: str) -> Path | None:
        raw = self.entries.get(name)
        return Path(raw) if raw else None

    def items(self) -> List[tuple[str, Path]]:
        return [(name, Path(p)) for name, p in sorted(self.entries.items())]
