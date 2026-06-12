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
