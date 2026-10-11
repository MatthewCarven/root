"""CLI tests: the launch / `root which` handoff and the no-wrapper warning.

The TUI itself is replaced by a fake run_app, so these exercise only the
CLI around it. conftest.py gives every test its own config dir.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from root_cli import cli
from root_cli.paths import target_path


@pytest.fixture
def fake_tui(monkeypatch):
    """Replace the TUI. Set .pick to what the next launch "chooses"
    (None = Esc); .notices records the notice each launch was given."""

    class Fake:
        pick = None
        notices = []

        def run_app(self, start_dir=None, notice=None):
            self.notices.append(notice)
            return self.pick

    fake = Fake()
    fake.notices = []
    monkeypatch.setattr("root_cli.app.run_app", fake.run_app)
    return fake


def test_pick_writes_target_for_the_wrapper(tmp_path, fake_tui, capsys):
    fake_tui.pick = tmp_path
    assert cli.main([]) == 0
    assert target_path().read_text(encoding="utf-8") == str(tmp_path)
    assert cli.main(["which"]) == 0
    assert capsys.readouterr().out == str(tmp_path)


def test_wrapper_reading_the_pick_means_no_warning(tmp_path, fake_tui):
    fake_tui.pick = tmp_path
    cli.main([])
    cli.main(["which"])  # what every shell wrapper does after a pick
    cli.main([])
    assert fake_tui.notices == [None, None]


def test_unread_pick_warns_on_next_launch(tmp_path, fake_tui):
    # Bare root.exe, no wrapper: nothing calls `root which`, so the
    # shell never moved.
    fake_tui.pick = tmp_path
    cli.main([])
    cli.main([])
    assert fake_tui.notices[0] is None
    assert "install-shell" in fake_tui.notices[1]


def test_warns_once_per_unread_pick(tmp_path, fake_tui):
    fake_tui.pick = tmp_path
    cli.main([])          # pick, unread
    fake_tui.pick = None
    cli.main([])          # warned; Esc this time
    cli.main([])          # nothing new went unread
    assert fake_tui.notices[1] is not None
    assert fake_tui.notices[2] is None


def test_cancel_never_warns(fake_tui):
    fake_tui.pick = None
    assert cli.main([]) == 130
    cli.main([])
    assert fake_tui.notices == [None, None]
    assert not target_path().exists()


def test_notice_shows_in_the_tui(tmp_path):
    import asyncio

    from textual.widgets import Static

    from root_cli.app import RootApp
    from root_cli.config import Bookmarks, Config
    from root_cli.history import History

    async def scenario():
        app = RootApp(
            config=Config(), bookmarks=Bookmarks(), history=History(),
            start_dir=tmp_path, notice="wrapper missing here",
        )
        async with app.run_test() as pilot:
            status = str(app.query_one("#status", Static).renderable)
            assert "wrapper missing here" in status
            await pilot.press("x")  # a refresh keeps it
            status = str(app.query_one("#status", Static).renderable)
            assert "wrapper missing here" in status

    asyncio.run(scenario())
