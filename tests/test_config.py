"""Tests for config + bookmarks round-tripping."""
from __future__ import annotations

from pathlib import Path

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


def test_preview_delay_default_and_roundtrip(isolated_config):
    assert Config.load().preview_delay_ms == 333
    cfg = Config.load()
    cfg.preview_delay_ms = 500
    cfg.save()
    assert Config.load().preview_delay_ms == 500


def test_preview_delay_missing_or_negative(isolated_config):
    # Configs written before the key existed get the default; a
    # negative value is clamped to 0 (instant) rather than crashing.
    path = isolated_config / "config.toml"
    path.write_text("show_hidden = false\n", encoding="utf-8")
    assert Config.load().preview_delay_ms == 333
    path.write_text("preview_delay_ms = -50\n", encoding="utf-8")
    assert Config.load().preview_delay_ms == 0


def test_suite_never_uses_the_real_config_dir():
    # Guards the autouse fixture in conftest.py: the TUI tests commit
    # directories, and a commit saves history.json to the live config dir.
    from platformdirs import user_config_dir

    from root_cli.paths import config_dir

    assert config_dir() != Path(user_config_dir("root", appauthor=False))
