"""Tests for the multi-source candidate aggregator."""
from __future__ import annotations

from pathlib import Path

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


def test_empty_query_default_view_layout(tmp_path, isolated_config):
    """Default view order: '.', '..', bookmarks, recents, tree children."""
    dirs = _make_dirs(tmp_path, ["alpha", "beta", "gamma"])

    bookmarks = Bookmarks()
    bookmarks.add("alpha-bm", dirs["alpha"])

    history = History()
    history.visit(dirs["beta"])

    cfg = Config()
    ctx = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=tmp_path)
    result = ctx.collect("")

    # '.' first.
    assert result[0].is_self_entry
    # '..' second (we're below /).
    assert result[1].is_parent_entry
    # Then bookmarks, then recents, then tree children.
    sources_in_order = [c.source for c in result if not c.is_special]
    first_recent = sources_in_order.index(Source.RECENT)
    first_tree = sources_in_order.index(Source.TREE)
    assert sources_in_order[0] is Source.BOOKMARK
    assert first_recent < first_tree


def test_query_filters_across_all_sources(tmp_path, isolated_config):
    dirs = _make_dirs(tmp_path, ["one", "two", "three"])

    bookmarks = Bookmarks()
    bookmarks.add("apple", dirs["one"])

    history = History()
    history.visit(dirs["two"])

    cfg = Config()
    ctx = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=tmp_path)

    # Search hits across tree.
    out = ctx.collect("ree")
    assert any(c.path == dirs["three"] for c in out)
    # Search hits across bookmarks.
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
    paths = [c.path for c in out]
    if proj_b in paths:
        assert paths.index(proj_a) < paths.index(proj_b)


# ---- synthetic '.' and '..' rows ----


def test_self_entry_always_in_default_view(tmp_path, isolated_config):
    """'.' commits the current browse dir. It's always present in the
    default view, even at filesystem root."""
    cfg = Config()
    bookmarks = Bookmarks()
    history = History()

    sub = tmp_path / "deep"
    sub.mkdir()
    ctx = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=sub)
    out = ctx.collect("")
    selves = [c for c in out if c.is_self_entry]
    assert len(selves) == 1
    assert selves[0].path == sub
    assert selves[0].label == "."

    # Also present at filesystem root.
    ctx2 = CandidateContext(config=cfg, bookmarks=bookmarks, history=history, cwd=Path("/"))
    assert any(c.is_self_entry for c in ctx2.collect(""))


def test_parent_entry_shown_in_subfolder(tmp_path, isolated_config):
    sub = tmp_path / "child"
    sub.mkdir()
    cfg = Config()
    ctx = CandidateContext(
        config=cfg, bookmarks=Bookmarks(), history=History(), cwd=sub
    )
    out = ctx.collect("")
    parents = [c for c in out if c.is_parent_entry]
    assert len(parents) == 1
    assert parents[0].path == tmp_path
    assert parents[0].source is Source.TREE
    assert parents[0].label == ".."


def test_parent_entry_hidden_at_filesystem_root(isolated_config):
    """At '/', parent == self -> no '..' row, but '.' is still there."""
    cfg = Config()
    ctx = CandidateContext(
        config=cfg, bookmarks=Bookmarks(), history=History(), cwd=Path("/")
    )
    out = ctx.collect("")
    assert not any(c.is_parent_entry for c in out)
    assert any(c.is_self_entry for c in out)  # '.' is always shown


def test_synthetic_rows_absent_in_search_results(tmp_path, isolated_config):
    """Both '.' and '..' should disappear once the user starts typing."""
    sub = tmp_path / "child"
    sub.mkdir()
    (sub / "alpha").mkdir()
    cfg = Config()
    ctx = CandidateContext(
        config=cfg, bookmarks=Bookmarks(), history=History(), cwd=sub
    )
    out = ctx.collect("alpha")
    assert not any(c.is_self_entry for c in out)
    assert not any(c.is_parent_entry for c in out)


def test_parent_entry_path_points_at_parent(tmp_path, isolated_config):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    cfg = Config()
    ctx = CandidateContext(
        config=cfg, bookmarks=Bookmarks(), history=History(), cwd=deep
    )
    out = ctx.collect("")
    parents = [c for c in out if c.is_parent_entry]
    assert len(parents) == 1
    assert parents[0].path.resolve() == deep.parent.resolve()


def test_self_entry_path_is_browse_dir(tmp_path, isolated_config):
    """Enter on '.' commits the current browse dir, so its .path must
    match self.cwd. This is what action_commit then writes out."""
    deep = tmp_path / "x" / "y"
    deep.mkdir(parents=True)
    cfg = Config()
    ctx = CandidateContext(
        config=cfg, bookmarks=Bookmarks(), history=History(), cwd=deep
    )
    out = ctx.collect("")
    selves = [c for c in out if c.is_self_entry]
    assert len(selves) == 1
    assert selves[0].path.resolve() == deep.resolve()
