"""Tests for the multi-source candidate aggregator."""
from __future__ import annotations

import pytest

from root_cli.candidates import CandidateContext, Source
from root_cli.config import Bookmarks, Config
from root_cli.history import History


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ROOT_CONFIG_DIR", str(tmp_path / "config"))
    yield tmp_path


def _make_dirs(root, names):
    out = {}
    for n in names:
        d = root / n
        d.mkdir(parents=True, exist_ok=True)
        out[n] = d
    return out


def test_empty_query_shows_bookmarks_then_recents_then_tree(tmp_path, isolated_config):
    dirs = _make_dirs(tmp_path, ["alpha", "beta", "gamma"])

    bookmarks = Bookmarks()
    bookmarks.add("alpha-bm", dirs["alpha"])

    history = History()
    history.visit(dirs["beta"])

    cfg = Config()
    ctx = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=tmp_path)
    result = ctx.collect("")

    sources_in_order = [c.source for c in result]
    # Bookmarks first.
    assert sources_in_order[0] is Source.BOOKMARK
    # Recents appear before tree children.
    first_recent = sources_in_order.index(Source.RECENT)
    first_tree = sources_in_order.index(Source.TREE)
    assert first_recent < first_tree


def test_query_filters_across_all_sources(tmp_path, isolated_config):
    dirs = _make_dirs(tmp_path, ["one", "two", "three"])

    bookmarks = Bookmarks()
    bookmarks.add("apple", dirs["one"])

    history = History()
    history.visit(dirs["two"])

    cfg = Config()
    ctx = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=tmp_path)

    # Query "ree" should match the tree child "three" but not bookmarks/recents.
    out = ctx.collect("ree")
    assert any(c.path == dirs["three"] for c in out)

    # Query "app" should match the bookmark alias.
    out = ctx.collect("app")
    assert any(c.source is Source.BOOKMARK and c.label == "apple" for c in out)


def test_dedupes_paths_across_sources(tmp_path, isolated_config):
    dirs = _make_dirs(tmp_path, ["shared"])
    bookmarks = Bookmarks()
    bookmarks.add("shared-bm", dirs["shared"])
    history = History()
    history.visit(dirs["shared"])

    cfg = Config()
    ctx = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=tmp_path)

    out = ctx.collect("shared")
    matches = [c for c in out if c.path == dirs["shared"]]
    assert len(matches) == 1
    # The bookmark wins on dedupe priority.
    assert matches[0].source is Source.BOOKMARK


def test_search_roots_globbed_when_query_present(tmp_path, isolated_config):
    code = tmp_path / "code"
    code.mkdir()
    proj_a = code / "alpha-service"
    proj_a.mkdir()
    proj_b = code / "beta-service"
    proj_b.mkdir()

    cfg = Config(search_roots=[str(code / "*")])
    bookmarks = Bookmarks()
    history = History()
    ctx = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=tmp_path)

    out = ctx.collect("alpha")
    assert any(c.path == proj_a and c.source is Source.SEARCH for c in out)
    # beta-service is also a match but should rank below alpha-service.
    paths = [c.path for c in out]
    if proj_b in paths:
        assert paths.index(proj_a) < paths.index(proj_b)


def test_parent_entry_shown_in_subfolder(tmp_path, isolated_config):
    """`..` should appear in default view when we're below the root."""
    sub = tmp_path / "child"
    sub.mkdir()
    cfg = Config()
    bookmarks = Bookmarks()
    history = History()
    ctx = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=sub)

    out = ctx.collect("")
    parents = [c for c in out if c.is_parent_entry]
    assert len(parents) == 1
    assert parents[0].path == tmp_path
    assert parents[0].source is Source.TREE
    assert parents[0].label == ".."


def test_parent_entry_hidden_at_filesystem_root(tmp_path, isolated_config):
    """At a filesystem root (parent == self), no `..` should appear."""
    from pathlib import Path

    # On POSIX, Path("/").parent == Path("/"), so use that as the cwd.
    # We can't realistically test from a Windows drive root in a Linux
    # CI box, but the same check (parent != self) covers both.
    root = Path("/")
    cfg = Config()
    bookmarks = Bookmarks()
    history = History()
    ctx = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=root)

    out = ctx.collect("")
    assert not any(c.is_parent_entry for c in out)


def test_parent_entry_absent_in_search_results(tmp_path, isolated_config):
    """Typing a query suppresses the synthetic `..` row (it'd be confusing)."""
    sub = tmp_path / "child"
    sub.mkdir()
    (sub / "alpha").mkdir()

    cfg = Config()
    bookmarks = Bookmarks()
    history = History()
    ctx = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=sub)

    out = ctx.collect("alpha")
    assert not any(c.is_parent_entry for c in out)


def test_parent_entry_path_points_at_parent(tmp_path, isolated_config):
    """The synthetic '..' candidate must carry the parent path, so that
    pressing Enter on it commits to the parent directory (which the
    shell wrapper then cds into)."""
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)

    cfg = Config()
    bookmarks = Bookmarks()
    history = History()
    ctx = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=deep)

    out = ctx.collect("")
    parents = [c for c in out if c.is_parent_entry]
    assert len(parents) == 1
    # The candidate's .path is the parent — that's what the TUI commits
    # via .resolve() in action_commit, and what the wrapper cds into.
    assert parents[0].path.resolve() == deep.parent.resolve()
