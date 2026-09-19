"""Tests for the frecency tracker."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from root_cli.history import History, HistoryEntry


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ROOT_CONFIG_DIR", str(tmp_path))
    yield tmp_path


def test_visit_creates_entry(tmp_path, isolated_config):
    h = History()
    target = tmp_path  # tmp_path exists and is a dir
    h.visit(target)
    assert len(h.entries) == 1
    entry = next(iter(h.entries.values()))
    assert entry.freq == 1.0


def test_visit_increments_existing(tmp_path, isolated_config):
    h = History()
    h.visit(tmp_path)
    h.visit(tmp_path)
    h.visit(tmp_path)
    entry = next(iter(h.entries.values()))
    assert entry.freq == 3.0


def test_forget_removes_entry(tmp_path, isolated_config):
    h = History()
    h.visit(tmp_path)
    assert h.forget(tmp_path) is True
    assert len(h.entries) == 0
    assert h.forget(tmp_path) is False  # already gone


def test_round_trip_load_save(tmp_path, isolated_config):
    h = History()
    a = tmp_path / "a"
    a.mkdir()
    b = tmp_path / "b"
    b.mkdir()
    h.visit(a)
    h.visit(a)
    h.visit(b)
    h.save()

    h2 = History.load()
    assert len(h2.entries) == 2
    # Both paths should resolve back.
    paths = {Path(e.path) for e in h2.entries.values()}
    assert a.resolve() in paths
    assert b.resolve() in paths


def test_ranked_filters_nonexistent_paths(tmp_path, isolated_config):
    h = History()
    real = tmp_path / "real"
    real.mkdir()
    fake = tmp_path / "ghost"  # never created

    h.visit(real)
    # Inject a phantom entry directly.
    h.entries[str(fake.resolve())] = HistoryEntry(
        path=str(fake.resolve()), freq=99.0, last_seen=time.time()
    )

    ranked = h.ranked()
    paths = [p for p, _ in ranked]
    assert real.resolve() in paths
    assert fake.resolve() not in paths


def test_frecency_prefers_recent(tmp_path, isolated_config):
    h = History()
    older = tmp_path / "old"
    older.mkdir()
    newer = tmp_path / "new"
    newer.mkdir()

    now = time.time()
    h.entries[str(older.resolve())] = HistoryEntry(
        path=str(older.resolve()), freq=5.0, last_seen=now - 10 * 86400
    )
    h.entries[str(newer.resolve())] = HistoryEntry(
        path=str(newer.resolve()), freq=2.0, last_seen=now - 60  # 1 minute ago
    )

    ranked = h.ranked()
    # Newer should rank higher despite lower frequency (recency multiplier).
    assert ranked[0][0] == newer.resolve()


def test_record_launch_separate_from_visits(tmp_path, isolated_config):
    h = History()
    exe = tmp_path / "tool.exe"
    exe.write_text("x")
    h.record_launch(exe)
    h.record_launch(exe)
    assert len(h.entries) == 0  # launches never pollute cd candidates
    assert len(h.launches) == 1
    entry = next(iter(h.launches.values()))
    assert entry.freq == 2.0


def test_launches_round_trip(tmp_path, isolated_config):
    h = History()
    exe = tmp_path / "tool.exe"
    exe.write_text("x")
    h.visit(tmp_path)
    h.record_launch(exe)
    h.save()

    h2 = History.load()
    assert len(h2.entries) == 1
    assert len(h2.launches) == 1
    assert Path(next(iter(h2.launches.values())).path) == exe.resolve()


def test_load_old_format_without_launches_key(tmp_path, isolated_config):
    """History files written before launch memory existed load cleanly."""
    (tmp_path / "history.json").write_text(
        json.dumps(
            {"entries": [{"path": str(tmp_path), "freq": 2.0, "last_seen": 0.0}]}
        )
    )
    h = History.load()
    assert len(h.entries) == 1
    assert h.launches == {}


def test_pruning_keeps_top_entries(tmp_path, isolated_config, monkeypatch):
    from root_cli import history as history_mod

    # Lower the cap to make the test small.
    monkeypatch.setattr(history_mod, "MAX_ENTRIES", 3)

    h = History()
    paths = []
    for i in range(5):
        p = tmp_path / f"d{i}"
        p.mkdir()
        paths.append(p)
        h.entries[str(p.resolve())] = HistoryEntry(
            path=str(p.resolve()),
            freq=float(i + 1),  # higher index = more frequent
            last_seen=time.time(),
        )

    h.save()
    on_disk = json.loads((tmp_path / "history.json").read_text())
    assert len(on_disk["entries"]) == 3
    # The most-frequent ones (d4, d3, d2) should survive.
    survivors = {Path(e["path"]).name for e in on_disk["entries"]}
    assert "d4" in survivors
    assert "d3" in survivors
    assert "d0" not in survivors
