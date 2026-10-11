"""Git-ignore awareness: the cache, tree ordering, preview, and config."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from root_cli import gitignore
from root_cli.candidates import CandidateContext, preview_entries
from root_cli.config import Bookmarks, Config
from root_cli.gitignore import GitIgnoreCache
from root_cli.history import History

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A fresh repo: src/ and docs/ normal, build/ and dist/ ignored,
    plus files a.log (ignored) and readme.txt. The user's global and
    system git config are shut out so their excludes can't leak in."""
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("build/\ndist/\n*.log\n", encoding="utf-8")
    for d in ("src", "docs", "build", "dist"):
        (root / d).mkdir()
    (root / "a.log").write_text("x", encoding="utf-8")
    (root / "readme.txt").write_text("x", encoding="utf-8")
    return root


def _context(cwd: Path, mode: str = "dim") -> CandidateContext:
    return CandidateContext(
        config=Config(gitignored=mode), bookmarks=Bookmarks(), history=History(), cwd=cwd,
    )


def _tree_rows(ctx: CandidateContext):
    return [(c.label, c.ignored) for c in ctx.collect("") if not c.is_special]


# ----- the cache -----

@needs_git
def test_reports_ignored_children(repo):
    assert GitIgnoreCache().ignored(repo) == {"build", "dist", "a.log"}


@needs_git
def test_dir_only_pattern_needs_no_file_lookalike(repo):
    # `build/` is dir-only: a *file* called build must not count.
    (repo / "docs" / "build").write_text("x", encoding="utf-8")
    assert GitIgnoreCache().ignored(repo / "docs") == frozenset()


@needs_git
def test_tracked_files_are_never_ignored(repo):
    (repo / "keep.log").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "keep.log"], check=True)
    assert "keep.log" not in GitIgnoreCache().ignored(repo)


def test_outside_a_repo_never_spawns_git(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(gitignore.subprocess, "run", lambda *a, **k: calls.append(a))
    (tmp_path / "build").mkdir()
    assert GitIgnoreCache().ignored(tmp_path) == frozenset()
    assert calls == []


@needs_git
def test_one_git_call_per_directory(repo, monkeypatch):
    real_run = subprocess.run
    calls = []
    monkeypatch.setattr(
        gitignore.subprocess, "run", lambda *a, **k: calls.append(a) or real_run(*a, **k)
    )
    cache = GitIgnoreCache()
    cache.ignored(repo)
    cache.ignored(repo)
    assert len(calls) == 1


def test_missing_git_is_harmless_and_not_retried(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "build").mkdir()
    (tmp_path / "other").mkdir()
    calls = []

    def no_git(*a, **k):
        calls.append(a)
        raise FileNotFoundError("git")

    monkeypatch.setattr(gitignore.subprocess, "run", no_git)
    cache = GitIgnoreCache()
    assert cache.ignored(tmp_path) == frozenset()
    assert cache.ignored(tmp_path / "other") == frozenset()
    assert len(calls) == 1


# ----- tree and preview -----

@needs_git
def test_dim_mode_sinks_ignored_dirs_and_flags_them(repo):
    assert _tree_rows(_context(repo, "dim")) == [
        ("docs", False), ("src", False), ("build", True), ("dist", True),
    ]


@needs_git
def test_hide_mode_drops_ignored_dirs(repo):
    assert _tree_rows(_context(repo, "hide")) == [("docs", False), ("src", False)]


def test_show_mode_never_asks_git(repo, monkeypatch):
    calls = []
    monkeypatch.setattr(gitignore.subprocess, "run", lambda *a, **k: calls.append(a))
    rows = _tree_rows(_context(repo, "show"))
    assert [label for label, _ in rows] == ["build", "dist", "docs", "src"]
    assert calls == []


@needs_git
def test_search_still_finds_ignored_dirs_in_dim_mode(repo):
    hits = _context(repo, "dim").collect("dist")
    assert hits and hits[0].label == "dist" and hits[0].ignored


@needs_git
def test_preview_sinks_ignored_within_each_group(repo):
    ignored = GitIgnoreCache().ignored(repo)
    rows = [(e.name, e.ignored) for e in preview_entries(repo, False, ignored=ignored)]
    assert rows == [
        ("docs/", False), ("src/", False), ("build/", True), ("dist/", True),
        ("readme.txt", False), ("a.log", True),
    ]


@needs_git
def test_preview_hide_drops_ignored(repo):
    ignored = GitIgnoreCache().ignored(repo)
    names = [e.name for e in preview_entries(repo, False, ignored=ignored, hide_ignored=True)]
    assert names == ["docs/", "src/", "readme.txt"]


# ----- config -----

def test_gitignored_config_default_roundtrip_and_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("ROOT_CONFIG_DIR", str(tmp_path))
    assert Config.load().gitignored == "dim"
    cfg = Config.load()
    cfg.gitignored = "hide"
    cfg.save()
    assert Config.load().gitignored == "hide"
    (tmp_path / "config.toml").write_text('gitignored = "Banana"\n', encoding="utf-8")
    assert Config.load().gitignored == "dim"
