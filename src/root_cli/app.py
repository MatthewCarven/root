"""The Textual TUI.

UX:
- Top: an Input where you type to filter.
- Middle-left: a ListView of ranked candidates from all sources.
- Middle-right: a preview pane listing the highlighted dir's contents.
  Cursor moves update it once the cursor rests (config
  preview_delay_ms, default 333), so holding up/down stays smooth;
  typing and navigating update it at once, and Tab never makes you
  wait.
- Bottom: a footer of keybindings.

Keys:
- Enter         Commit highlighted candidate (and cd there). On the
                ".." row, ascend the browse view instead of committing.
- Right         With the cursor at the end of the search text (or the
                box empty): descend into the highlighted directory
                (browse w/o commit). Mid-text: moves the cursor.
- Shift+Enter   Always descend, regardless of cursor position.
- Left          With the cursor at the start of the search text (or the
                box empty): go up one directory. Mid-text: moves the
                cursor.
- Tab           Toggle focus into / out of the preview pane.
- Ctrl+B        Bookmark the highlighted directory (asks for a name).
- Ctrl+D        Delete the highlighted entry: removes a bookmark (*) or
                forgets a recent (~), depending on the row.
- Ctrl+H        Alias for Ctrl+D (legacy / muscle-memory).
- Esc           Quit without committing.

Inside the preview pane (after Tab):
- Up/Down       Move between entries.
- Enter         On a directory: commit (cd there and exit) — root is
                foremost a cd replacement, so Enter always means "take
                me there". On a file: launch it with the OS default
                handler; the TUI stays open so you can launch several.
                The launch is remembered (parent dir gets a history
                visit; the file itself lands in launch history).
- Shift+Enter   Same intent, but stay in the app: on a directory,
                descend the browser into it (mirrors the main list's
                Shift+Enter). On a file: launch (already stays open).
- Right         Descend into the highlighted directory.
- Left / S+Tab  Back to the search box.

Default cursor positioning, when the input is blank:
- If you haven't navigated yet (browse_dir == start_dir), the cursor
  skips the synthetic '.' and '..' rows and lands on the first real
  entry -- so Enter takes you somewhere new, not back where you are.
- Once you've navigated (via '..' or arrow-right), the cursor defaults
  to '.', so just hitting Enter commits the folder you're viewing.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import List, Optional

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from root_cli.candidates import (
    Candidate,
    CandidateContext,
    PreviewEntry,
    Source,
    commit_path,
    preview_entries,
)
from root_cli.config import Bookmarks, Config
from root_cli.history import History
from root_cli.launch import launch_path


# Older Textual releases (< ~0.76) have Input.action_cursor_left/right
# with no `select` parameter; newer ones require passing it through.
_INPUT_CURSOR_TAKES_SELECT = (
    "select" in inspect.signature(Input.action_cursor_left).parameters
)


class _SearchInput(Input):
    """Search box whose arrow keys fall through to navigation at the edges.

    A plain Input swallows left/right unconditionally, which makes the
    footer's "<- up" hint a lie whenever the box has text. Instead:
    pressing left with the cursor already at position 0 ascends, and
    pressing right with the cursor already at the end of the text
    descends. Anywhere mid-text they move the cursor as usual, so no
    editing ability is lost. Shift+arrow (selection) is never hijacked.
    """

    def action_cursor_left(self, select: bool = False) -> None:
        if not select and self.cursor_position == 0:
            self.app.action_ascend()  # type: ignore[attr-defined]
            return
        if _INPUT_CURSOR_TAKES_SELECT:
            super().action_cursor_left(select)
        else:
            super().action_cursor_left()

    def action_cursor_right(self, select: bool = False) -> None:
        if not select and self.cursor_position >= len(self.value):
            self.app.action_descend()  # type: ignore[attr-defined]
            return
        if _INPUT_CURSOR_TAKES_SELECT:
            super().action_cursor_right(select)
        else:
            super().action_cursor_right()


class _CandidateRow(ListItem):
    """A single candidate row. Carries the underlying Candidate."""

    def __init__(self, candidate: Candidate) -> None:
        self.candidate = candidate
        label = f"[b]{candidate.source.icon}[/b]  {self._format_label(candidate)}"
        super().__init__(Label(label, markup=True))

    @staticmethod
    def _format_label(c: Candidate) -> str:
        if c.source is Source.BOOKMARK:
            return f"[b]{c.label}[/b]  [dim]{c.path}[/dim]"
        if c.is_self_entry:
            return f"[b].[/b]   [dim]commit {c.path}[/dim]"
        if c.is_parent_entry:
            return f"[b]..[/b]  [dim]up to {c.path}[/dim]"
        if c.source is Source.TREE:
            return f"{c.label}/  [dim]({c.path.parent})[/dim]"
        return str(c.path)


class _PreviewRow(ListItem):
    """A single preview-pane row. Carries the underlying PreviewEntry."""

    def __init__(self, entry: PreviewEntry) -> None:
        self.entry = entry
        if entry.is_marker:
            label = f"[dim]{escape(entry.name)}[/dim]"
        else:
            label = escape(entry.name)
        super().__init__(Label(label, markup=True))


class RootApp(App):
    CSS = """
    Screen { layout: vertical; }
    #status { padding: 0 1; color: $text-muted; }
    Input { dock: top; }
    #main { height: 1fr; }
    #results { width: 2fr; height: 100%; }
    #previewpane {
        width: 1fr;
        height: 100%;
        border-left: solid $panel;
        color: $text-muted;
    }
    #previewpane:focus-within {
        border-left: thick $accent;
        color: $text;
    }
    #preview-title { padding: 0 1; }
    #preview { height: 1fr; padding: 0 1; }
    .prompt {
        padding: 1 1 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("right", "descend", "into"),
        Binding("shift+enter", "descend", "into", show=False, priority=True),
        Binding("left", "ascend", "up"),
        Binding("tab", "focus_preview", "preview", priority=True),
        Binding("shift+tab", "focus_search", show=False, priority=True),
        Binding("ctrl+b", "bookmark", "+bm", priority=True),
        Binding("ctrl+d", "remove_bookmark", "del", priority=True),
        Binding("ctrl+h", "forget_recent", "del", show=False, priority=True),
        Binding("escape", "cancel", "quit"),
        Binding("up", "cursor_up", show=False),
        Binding("down", "cursor_down", show=False),
    ]

    query: reactive[str] = reactive("")
    browse_dir: reactive[Path] = reactive(Path.cwd())
    _bookmark_mode: bool = False
    _pending_bookmark_path: Optional[Path] = None

    def __init__(
        self,
        config: Config,
        bookmarks: Bookmarks,
        history: History,
        start_dir: Path,
        notice: Optional[str] = None,
    ):
        super().__init__()
        # Shown above the key hints all session (e.g. "your shell
        # wrapper isn't loaded"), since it applies to every pick.
        self._notice = notice
        self.config = config
        self.bookmarks = bookmarks
        self.history = history
        self.browse_dir = start_dir
        self._start_dir = start_dir  # for "have I navigated?" default-cursor logic
        self.context = CandidateContext(
            config=config, bookmarks=bookmarks, history=history, cwd=start_dir
        )
        self.committed_path: Optional[Path] = None
        self._candidates: List[Candidate] = []
        self._preview_entries: List[PreviewEntry] = []
        self._previewed: Optional[Path] = None  # candidate path the pane shows
        self._preview_timer: Optional[Timer] = None
        # Seconds the results cursor must rest before the preview pane
        # rebuilds. Holding up/down would otherwise list every dir on
        # the way past, which makes the main list stutter.
        self._preview_delay = config.preview_delay_ms / 1000

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield _SearchInput(placeholder="type to fuzzy-search — or arrow keys to browse")
        yield Static("", id="status", classes="prompt")
        with Horizontal(id="main"):
            yield ListView(id="results")
            with Vertical(id="previewpane"):
                yield Static("", id="preview-title")
                yield ListView(id="preview")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "root"
        self.sub_title = str(self.browse_dir)
        self._refresh()
        self.query_one(Input).focus()

    def _refresh(self) -> None:
        self.context.cwd = self.browse_dir
        self._candidates = self.context.collect(self.query)
        lv = self.query_one("#results", ListView)
        lv.clear()
        for c in self._candidates:
            lv.append(_CandidateRow(c))
        lv.index = self._default_cursor_index()

        status = self.query_one("#status", Static)
        notice = f"[yellow]{escape(self._notice)}[/yellow]\n" if self._notice else ""
        status.update(
            notice +
            f"[dim]browsing[/dim] [b]{self.browse_dir}[/b]   "
            f"[dim]{len(self._candidates)} result(s)[/dim]\n"
            f"[dim]Enter[/dim] go    "
            f"[dim]→ or Shift+Enter[/dim] descend (no exit)    "
            f"[dim]←[/dim] up    "
            f"[dim]Tab[/dim] preview    "
            f"[dim]Esc[/dim] quit"
        )
        self.sub_title = str(self.browse_dir)
        self._update_preview()

    def _update_preview(self) -> None:
        """Refresh the right-side pane with the highlighted dir's contents.

        Synthetic rows preview their concrete .path (the browse dir for
        '.', its parent for '..'), which is what the user expects: "what
        will I find if I go here?"

        Runs immediately; any pending debounced update is superseded.
        """
        self._cancel_preview_timer()
        title = self.query_one("#preview-title", Static)
        pane = self.query_one("#preview", ListView)
        cand = self._current()
        path = cand.path if cand is not None else None
        self._previewed = path
        try:
            if path is not None and not path.is_dir():
                path = None
        except OSError:
            path = None
        if path is None:
            self._preview_entries = []
            title.update("")
            pane.clear()
            return
        self._preview_entries = preview_entries(path, self.config.show_hidden)
        title.update(f"[b]{escape(path.name or str(path))}[/b]")
        pane.clear()
        for entry in self._preview_entries:
            pane.append(_PreviewRow(entry))
        pane.index = 0

    def _cancel_preview_timer(self) -> None:
        if self._preview_timer is not None:
            self._preview_timer.stop()
            self._preview_timer = None

    def _preview_settled(self) -> None:
        """Debounce timer fired: the cursor has rested, so preview now --
        unless it came back to the row the pane already shows."""
        self._preview_timer = None
        cand = self._current()
        if (cand.path if cand is not None else None) != self._previewed:
            self._update_preview()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        # Only the main results list drives the preview; highlight
        # changes *inside* the preview must not rebuild it. Each move
        # restarts the delay, so a held arrow key previews once, at the
        # row it stops on.
        if event.list_view.id == "results" and not self._bookmark_mode:
            if self._preview_delay <= 0:
                self._update_preview()
                return
            self._cancel_preview_timer()
            self._preview_timer = self.set_timer(
                self._preview_delay, self._preview_settled
            )

    def _default_cursor_index(self) -> Optional[int]:
        """Pick a sensible starting selection.

        - Filtered (non-blank query): row 0, the highest-scoring match.
        - Default view, navigated (browse_dir != start_dir): row 0,
          which is '.', so Enter commits the current view.
        - Default view, still in the starting dir: skip '.' and '..'
          so Enter takes the user to a *new* destination.
        """
        if not self._candidates:
            return None
        if self.query:
            return 0
        if self.browse_dir != self._start_dir:
            return 0
        for i, cand in enumerate(self._candidates):
            if not cand.is_special:
                return i
        return 0  # fallback (shouldn't happen)

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._bookmark_mode:
            return
        self.query = event.value
        self._refresh()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # ListView raises Selected on Enter / click. Treat that as a
        # commit, *but only when the user is on our main screen* --
        # Textual's built-in command palette has its own list and
        # raises its own events on a different screen, which won't
        # reach this handler.
        if self._bookmark_mode:
            return
        if event.list_view.id == "preview":
            self._preview_commit()
        else:
            self.action_commit()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        if self._bookmark_mode:
            self._finalize_bookmark()
        else:
            self.action_commit()

    def _current(self) -> Optional[Candidate]:
        lv = self.query_one("#results", ListView)
        idx = lv.index
        if idx is None or idx < 0 or idx >= len(self._candidates):
            return None
        return self._candidates[idx]

    # ----- preview pane -----

    def _preview_focused(self) -> bool:
        focused = self.focused
        return focused is not None and focused.id == "preview"

    def _current_preview(self) -> Optional[PreviewEntry]:
        lv = self.query_one("#preview", ListView)
        idx = lv.index
        if idx is None or idx < 0 or idx >= len(self._preview_entries):
            return None
        return self._preview_entries[idx]

    def action_focus_preview(self) -> None:
        """Tab: toggle focus between the search box and the preview pane."""
        if self._bookmark_mode:
            return
        if self._preview_focused():
            self.query_one(Input).focus()
            return
        # Tab straight after a cursor move: don't make the user wait out
        # the delay, or step into the previous row's stale listing.
        if self._preview_timer is not None:
            self._update_preview()
        if self._preview_entries:
            self.query_one("#preview", ListView).focus()

    def action_focus_search(self) -> None:
        """Shift+Tab: always back to the search box."""
        if not self._bookmark_mode:
            self.query_one(Input).focus()

    def _preview_commit(self) -> None:
        """Enter inside the preview pane.

        Directory -> commit (cd there and exit): root is foremost a cd
        replacement, so Enter always means "take me there". File ->
        launch with the OS default handler and *stay open*, remembering
        the launch.
        """
        entry = self._current_preview()
        if entry is None or entry.is_marker:
            return
        if entry.is_dir:
            if self.committed_path is not None:
                return
            try:
                resolved = entry.path.resolve()
            except OSError:
                resolved = entry.path
            self.committed_path = resolved
            commit_path(self.history, self.committed_path)
            self.exit()
            return
        self._launch_file(entry.path)

    def _launch_file(self, path: Path) -> None:
        err = launch_path(path)
        status = self.query_one("#status", Static)
        if err is not None:
            status.update(f"[red]launch failed:[/red] {escape(err)}")
            return
        # Remember the launch: parent dir counts as a visit (you were
        # effectively working there), the file itself goes to launch
        # history for the future LAUNCH fuzzy-search source.
        self.history.visit(path.parent)
        self.history.record_launch(path)
        self.history.save()
        status.update(f"[green]launched[/green] {escape(path.name)}  [dim]TUI stays open — Esc to quit[/dim]")

    def _preview_descend(self) -> None:
        """Shift+Enter / right-arrow inside the preview pane.

        Directory -> descend the browser into it and stay open (same
        meaning Shift+Enter has in the main list). File -> launch
        (launching already stays open).
        """
        entry = self._current_preview()
        if entry is None or entry.is_marker:
            return
        if not entry.is_dir:
            self._launch_file(entry.path)
            return
        try:
            self.browse_dir = entry.path.resolve()
        except OSError:
            return
        self.query_one(Input).value = ""
        self.query = ""
        self._refresh()

    def action_commit(self) -> None:
        if self.committed_path is not None:
            return
        cand = self._current()
        if cand is None:
            return

        # Enter on '..' is a *navigation*, not a commit. Ascend the
        # browse view; the user can then pick a child or hit '.' to
        # commit where they've landed.
        if cand.is_parent_entry:
            self.action_ascend()
            return

        # Enter on '.' commits the current browse directory. For all
        # other rows, commit the candidate's path.
        try:
            resolved = cand.path.resolve()
        except OSError:
            resolved = cand.path
        self.committed_path = resolved
        commit_path(self.history, self.committed_path)
        self.exit()

    def action_cancel(self) -> None:
        self.committed_path = None
        self.exit()

    def action_descend(self) -> None:
        # Pane-aware: with the preview focused, Shift+Enter / right
        # act on the preview's highlighted entry instead.
        if self._preview_focused():
            self._preview_descend()
            return
        cand = self._current()
        if cand is None:
            return
        # Right-arrow on '..' ascends (its .path *is* the parent).
        # Right-arrow on '.' is a no-op (descend into self == stay).
        if cand.is_self_entry:
            return
        try:
            if cand.path.is_dir():
                self.browse_dir = cand.path.resolve()
                self.query_one(Input).value = ""
                self.query = ""
                self._refresh()
        except OSError:
            pass

    def action_ascend(self) -> None:
        # In the preview pane, left means "back to the search box" --
        # ascending the browse dir while inspecting a *different* dir's
        # contents would be disorienting.
        if self._preview_focused():
            self.query_one(Input).focus()
            return
        parent = self.browse_dir.parent
        if parent != self.browse_dir:
            self.browse_dir = parent
            self.query_one(Input).value = ""
            self.query = ""
            self._refresh()

    def action_cursor_up(self) -> None:
        self.query_one("#results", ListView).action_cursor_up()

    def action_cursor_down(self) -> None:
        self.query_one("#results", ListView).action_cursor_down()

    def action_bookmark(self) -> None:
        cand = self._current()
        if cand is None:
            return
        # If the highlighted row is already a bookmark, don't open
        # the "name this" prompt -- that just creates a duplicate
        # under a new alias. Point the user at Ctrl+D instead.
        if cand.source is Source.BOOKMARK:
            self.query_one("#status", Static).update(
                f"[yellow]'{cand.label}' is already bookmarked.[/yellow]  "
                f"[dim]Ctrl+D to remove it.[/dim]"
            )
            return
        # '.' and '..' are bookmarkable -- their .path is concrete (the
        # browse dir or its parent), and _enter_bookmark_mode prefills
        # path.name as the suggested alias, which is exactly what the
        # user wants ("bookmark this folder I'm looking at by its name").
        self._enter_bookmark_mode(cand.path.resolve())

    def action_remove_bookmark(self) -> None:
        """Ctrl+D: delete the highlighted entry.

        Polymorphic by row type:
        - bookmark (*) row -> remove from bookmarks.toml
        - recent   (~) row -> forget from history.json
        - anything else    -> status hint (so the keypress isn't silent)
        """
        cand = self._current()
        if cand is None:
            return
        if cand.source is Source.BOOKMARK:
            if self.bookmarks.remove(cand.label):
                self.bookmarks.save()
                self._refresh()
            return
        if cand.source is Source.RECENT:
            if self.history.forget(cand.path):
                self.history.save()
                self._refresh()
            return
        self.query_one("#status", Static).update(
            "[dim]Ctrl+D removes bookmarks ([b]*[/b]) and recents "
            "([b]~[/b]) -- nothing to remove on this row.[/dim]"
        )

    def action_forget_recent(self) -> None:
        """Ctrl+H: alias for Ctrl+D on a recent row.

        Kept for muscle-memory / discoverability. Same dispatcher as
        action_remove_bookmark, so it Just Works on bookmark rows too.
        """
        self.action_remove_bookmark()

    def _enter_bookmark_mode(self, path: Path) -> None:
        self._bookmark_mode = True
        self._pending_bookmark_path = path
        inp = self.query_one(Input)
        # path.name is empty at filesystem roots (e.g. Path("C:\\").name
        # == ""). Fall back to a sanitised drive/path stub so the field
        # isn't blank -- the user can still overwrite it.
        default = path.name or path.anchor.rstrip("\\/:") or str(path)
        inp.value = default
        inp.placeholder = f"name this bookmark for {path}  (Enter to save, Esc to cancel)"
        inp.focus()  # ctrl+b can fire while the preview pane has focus
        self.query_one("#status", Static).update(
            f"[yellow]bookmarking[/yellow] {path} — enter a name"
        )

    def _finalize_bookmark(self) -> None:
        inp = self.query_one(Input)
        name = inp.value.strip()
        if name and self._pending_bookmark_path is not None:
            self.bookmarks.add(name, self._pending_bookmark_path)
            self.bookmarks.save()
        self._bookmark_mode = False
        self._pending_bookmark_path = None
        inp.value = ""
        inp.placeholder = "type to fuzzy-search — or arrow keys to browse"
        self.query = ""
        self._refresh()


def run_app(
    start_dir: Optional[Path] = None, notice: Optional[str] = None
) -> Optional[Path]:
    """Launch the TUI. Returns the chosen path, or None if cancelled."""
    config = Config.load()
    bookmarks = Bookmarks.load()
    history = History.load()
    app = RootApp(
        config=config,
        bookmarks=bookmarks,
        history=history,
        start_dir=(start_dir or Path.cwd()).resolve(),
        notice=notice,
    )
    app.run()
    return app.committed_path
