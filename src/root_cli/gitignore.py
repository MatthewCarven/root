"""Which children of a directory does git ignore?

Asks git itself (``git check-ignore``) rather than parsing .gitignore
files: git knows about nested .gitignores, .git/info/exclude, the
global excludes file, negations, and that tracked files are never
"ignored". One call per directory, cached for the session; directories
outside any repo never spawn git at all.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, FrozenSet, List


def _inside_work_tree(directory: Path) -> bool:
    """Cheap pre-check: is there a .git (dir, or file for worktrees and
    submodules) here or in any parent? Saves a git spawn per directory
    outside repos, which is most of the filesystem."""
    for d in (directory, *directory.parents):
        if (d / ".git").exists():
            return True
    return False


class GitIgnoreCache:
    """Per-session cache of ignored child names, one entry per directory."""

    def __init__(self) -> None:
        self._by_dir: Dict[str, FrozenSet[str]] = {}
        self._git_missing = False

    def ignored(self, directory: Path) -> FrozenSet[str]:
        """Names of *directory*'s children that git ignores (no slashes)."""
        key = os.path.normcase(str(directory))
        if key not in self._by_dir:
            self._by_dir[key] = self._query(directory)
        return self._by_dir[key]

    def _query(self, directory: Path) -> FrozenSet[str]:
        if self._git_missing or not _inside_work_tree(directory):
            return frozenset()
        names: List[str] = []
        try:
            for child in directory.iterdir():
                if child.name == ".git":
                    continue
                try:
                    is_dir = child.is_dir()
                except OSError:
                    is_dir = False
                # Dirs need the trailing slash, or dir-only patterns
                # like `build/` don't match.
                names.append(child.name + "/" if is_dir else child.name)
        except OSError:
            return frozenset()
        if not names:
            return frozenset()
        try:
            res = subprocess.run(
                ["git", "-C", str(directory), "check-ignore", "-z", "--stdin"],
                input="\0".join(names),
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=5, check=False,
            )
        except FileNotFoundError:  # no git on PATH: stop asking
            self._git_missing = True
            return frozenset()
        except (OSError, subprocess.TimeoutExpired):
            return frozenset()
        # 0 = some ignored, 1 = none, 128 = not a repo / other trouble.
        if res.returncode not in (0, 1):
            return frozenset()
        return frozenset(n.rstrip("/") for n in res.stdout.split("\0") if n)
