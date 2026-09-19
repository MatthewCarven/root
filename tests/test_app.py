"""Textual pilot tests for the TUI -- arrow-key edge navigation.

Uses asyncio.run directly so no pytest-asyncio dependency is needed.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import Input

from root_cli.app import RootApp
from root_cli.config import Bookmarks, Config
from root_cli.history import History


def _make_app(start: Path) -> RootApp:
    return RootApp(
        config=Config(),
        bookmarks=Bookmarks(),
        history=History(),
        start_dir=start,
    )


def _run(coro) -> None:
    asyncio.run(coro)


def test_left_with_empty_input_ascends(tmp_path):
    start = tmp_path / "a" / "b"
    start.mkdir(parents=True)

    async def scenario():
        app = _make_app(start)
        async with app.run_test() as pilot:
            assert app.browse_dir == start
            await pilot.press("left")
            assert app.browse_dir == start.parent

    _run(scenario())


def test_left_mid_text_moves_cursor_not_view(tmp_path):
    start = tmp_path / "a" / "b"
    start.mkdir(parents=True)

    async def scenario():
        app = _make_app(start)
        async with app.run_test() as pilot:
            await pilot.press("x", "y")
            inp = app.query_one(Input)
            assert inp.cursor_position == 2
            await pilot.press("left")
            assert inp.cursor_position == 1
            assert app.browse_dir == start  # no ascend

    _run(scenario())


def test_left_at_position_zero_with_text_ascends(tmp_path):
    start = tmp_path / "a" / "b"
    start.mkdir(parents=True)

    async def scenario():
        app = _make_app(start)
        async with app.run_test() as pilot:
            await pilot.press("x", "y", "left", "left")
            inp = app.query_one(Input)
            assert inp.cursor_position == 0
            await pilot.press("left")
            assert app.browse_dir == start.parent
            # Navigation clears the query, matching descend behavior.
            assert inp.value == ""

    _run(scenario())


def test_right_at_end_of_text_descends(tmp_path):
    start = tmp_path / "proj"
    (start / "sub").mkdir(parents=True)
    (start / "other").mkdir()

    async def scenario():
        app = _make_app(start)
        async with app.run_test() as pilot:
            await pilot.press("s", "u", "b")
            await pilot.press("right")
            assert app.browse_dir == (start / "sub").resolve()
            assert app.query_one(Input).value == ""

    _run(scenario())


def test_right_mid_text_moves_cursor_not_view(tmp_path):
    start = tmp_path / "proj"
    (start / "sub").mkdir(parents=True)

    async def scenario():
        app = _make_app(start)
        async with app.run_test() as pilot:
            await pilot.press("s", "u", "left", "left")
            inp = app.query_one(Input)
            assert inp.cursor_position == 0
            await pilot.press("right")
            assert inp.cursor_position == 1
            assert app.browse_dir == start  # no descend

    _run(scenario())


# ---------------------------------------------------------------------------
# Preview pane: Tab to enter, up/down to pick, Enter/Shift+Enter to act
# ---------------------------------------------------------------------------


def _make_preview_tree(tmp_path: Path) -> Path:
    """start/sub/{inner/, file.txt} — default cursor lands on 'sub',
    so the preview pane shows inner/ (index 0) and file.txt (index 1)."""
    start = tmp_path / "start"
    (start / "sub" / "inner").mkdir(parents=True)
    (start / "sub" / "file.txt").write_text("x")
    return start


def test_tab_toggles_focus_into_preview(tmp_path):
    start = _make_preview_tree(tmp_path)

    async def scenario():
        app = _make_app(start)
        async with app.run_test() as pilot:
            assert isinstance(app.focused, Input)
            await pilot.press("tab")
            assert app.focused is not None and app.focused.id == "preview"
            await pilot.press("tab")  # toggles back
            assert isinstance(app.focused, Input)
            await pilot.press("tab", "shift+tab")  # shift+tab also returns
            assert isinstance(app.focused, Input)

    _run(scenario())


def test_left_in_preview_returns_to_search(tmp_path):
    start = _make_preview_tree(tmp_path)

    async def scenario():
        app = _make_app(start)
        async with app.run_test() as pilot:
            await pilot.press("tab", "left")
            assert isinstance(app.focused, Input)
            assert app.browse_dir == start  # no ascend happened

    _run(scenario())


def test_enter_on_preview_dir_commits(tmp_path):
    start = _make_preview_tree(tmp_path)

    async def scenario():
        app = _make_app(start)
        async with app.run_test() as pilot:
            await pilot.press("tab")  # preview cursor starts on inner/
            await pilot.press("enter")
        assert app.committed_path == (start / "sub" / "inner").resolve()

    _run(scenario())


def test_shift_enter_on_preview_dir_descends_and_stays(tmp_path):
    start = _make_preview_tree(tmp_path)

    async def scenario():
        app = _make_app(start)
        async with app.run_test() as pilot:
            await pilot.press("tab")
            await pilot.press("shift+enter")
            assert app.committed_path is None  # still running
            assert app.browse_dir == (start / "sub" / "inner").resolve()

    _run(scenario())


def test_enter_on_preview_file_launches_and_stays(tmp_path, monkeypatch):
    monkeypatch.setenv("ROOT_CONFIG_DIR", str(tmp_path / "config"))
    start = _make_preview_tree(tmp_path)
    launched: list[Path] = []
    monkeypatch.setattr(
        "root_cli.app.launch_path", lambda p: launched.append(p) or None
    )

    async def scenario():
        app = _make_app(start)
        async with app.run_test() as pilot:
            await pilot.press("tab", "down")  # inner/ -> file.txt
            await pilot.press("enter")
            assert app.committed_path is None  # TUI stays open
            assert launched == [start / "sub" / "file.txt"]
            # The launch is remembered: file in launch history, parent
            # dir as a normal visit.
            key = str((start / "sub" / "file.txt").resolve())
            assert key in app.history.launches
            assert str((start / "sub").resolve()) in app.history.entries

    _run(scenario())


def test_enter_on_preview_marker_row_is_noop(tmp_path):
    """An empty dir previews as a single '<empty>' marker — Enter on it
    must neither commit nor crash."""
    start = tmp_path / "start"
    (start / "hollow").mkdir(parents=True)

    async def scenario():
        app = _make_app(start)
        async with app.run_test() as pilot:
            await pilot.press("tab", "enter")
            assert app.committed_path is None
            assert app.browse_dir == start

    _run(scenario())
