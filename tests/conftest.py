"""Shared fixtures for the whole suite."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_config_dir(tmp_path_factory, monkeypatch):
    """Every test gets a throwaway config dir.

    The TUI saves history.json on every commit, so a pilot test that
    presses Enter on a directory writes to whatever config dir is live.
    Before this fixture, two such tests overwrote the real history.json
    on every run (2026-09-20 to 2026-10-11). Tests that set
    ROOT_CONFIG_DIR themselves still win: their setenv runs later.

    tmp_path_factory, not tmp_path, so the config dir never appears as
    a child in a test's own directory tree.
    """
    monkeypatch.setenv("ROOT_CONFIG_DIR", str(tmp_path_factory.mktemp("config")))
