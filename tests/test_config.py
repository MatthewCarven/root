"""Tests for config + bookmarks round-tripping."""
from __future__ import annotations

import pytest

from root_cli.config import Bookmarks, Config


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ROOT_CONFIG_DIR", str(tmp_path))
    yield tmp_path


def test_config_defaults_on_first_load(isolated_config):
    cfg = Config.load()
    assert cfg.search_roots == []
    assert cfg.max_results == 50
    assert cfg.recent_limit == 10
    assert cfg.show_hidden is False


def test_config_roundtrip(isolated_config):
    cfg = Config.load()
    cfg.search_roots = ["~/code/*", "~/projects/*"]
    cfg.max_results = 25
    cfg.show_hidden = True
    cfg.save()

    cfg2 = Config.load()
    assert cfg2.search_roots == ["~/code/*", "~/projects/*"]
    assert cfg2.max_results == 25
    assert cfg2.show_hidden is True


def test_bookmarks_add_and_remove(tmp_path, isolated_config):
    bm = Bookmarks()
    target = tmp_path / "work"
    target.mkdir()

    bm.add("work", target)
    bm.save()

    bm2 = Bookmarks.load()
    assert "work" in bm2.entries
    assert bm2.get("work") == target.resolve()

    assert bm2.remove("work") is True
    bm2.save()
    assert Bookmarks.load().entries == {}


def test_bookmarks_items_sorted(tmp_path, isolated_config):
    bm = Bookmarks()
    for name in ["zoo", "apple", "mango"]:
        d = tmp_path / name
        d.mkdir()
        bm.add(name, d)
    names = [n for n, _ in bm.items()]
    assert names == sorted(names)
