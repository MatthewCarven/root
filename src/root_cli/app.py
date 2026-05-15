"""The Textual TUI.

UX:
- Top: an Input where you type to filter.
- Middle: a ListView of ranked candidates from all sources.
- Bottom: a footer of keybindings.

Keys:
- Enter         Commit highlighted candidate (writes to sentinel + exits).
- Right         Descend into highlighted directory (tree-browse).
- Left          Go up one directory in tree-browse.
- Ctrl+B        Bookmark the highlighted directory (asks for a name).
- Ctrl+D        Remove the highlighted bookmark (only if it IS a bookmark).
- Ctrl+H        Forget the highlighted recent.
- Esc           Quit without committing.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from root_cli.candidates import Candidate, CandidateContext, Source, commit_path
from root_cli.config import Bookmarks, Config
from root_cli.history import History


class _CandidateRow(ListItem):
    """A single candidate row. Carries the underlying Candidate."""

    def __init__(self, candidate: Candidate) -> None:
        self.candidate = candidate
        # Two-line layout: "* name   /full/path"
        label = f"[b]{candidate.source.icon}[/b]  {self._format_label(candidate)}"
        super().__init__(Label(label, markup=True))

    @staticmethod
    def _format_label(c: Candidate) -> str:
        if c.source is Source.BOOKMARK:
            return f"[b]{c.label}[/b]  [dim]{c.path}[/dim]"
        if c.is_parent_entry:
            # Synthetic ".." parent — show where it'll take you.
            return f"[b]..[/b]  [dim]up to {c.path}[/dim]"
        if c.source is Source.TREE:
            return f"{c.label}/  [dim]({c.path.parent})[/dim]"
        return str(c.path)


class RootApp(App):
    CSS = """
    Screen { layout: vertical; }
    #status { padding: 0 1; color: $text-muted; }
    Input { dock: top; }
    ListView { height: 1fr; }
    .prompt {
        padding: 1 1 0 1;
        color: $text-muted;
    }
    #namebar {
        dock: top;
        height: 3;
        padding: 1;
        background: $boost;
    }
    """

    BINDINGS = [
        Binding("enter", "commit", "go", priority=True),
        Binding("right", "descend", "into"),
        Binding("left", "ascend", "up"),
        Binding("ctrl+b", "bookmark", "+bm"),
        Binding("ctrl+d", "remove_bookmark", "-bm"),
        Binding("ctrl+h", "forget_recent", "-recent"),
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
    ):
        super().__init__()
        self.config = config
        self.bookmarks = bookmarks
        self.history = history
        self.browse_dir = start_dir
        self.context = CandidateContext(
            config=config, bookmarks=bookmarks, history=history, cwd=start_dir
        )
        self.committed_path: Optional[Path] = None
        self._candidates: List[Candidate] = []

    # ----- layout -----

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Input(placeholder="type to fuzzy-search — or arrow keys to browse")
        yield Static("", id="status", classes="prompt")
        yield ListView()
        yield Footer()

    def on_mount(self) -> None:
        self.title = "root"
        self.sub_title = str(self.browse_dir)
        self._refresh()
        # Focus input by default so typing starts filtering immediately.
        self.query_one(Input).focus()

    # ----- refresh -----

    def _refresh(self) -> None:
        self.context.cwd = self.browse_dir
        self._candidates = self.context.collect(self.query)
        lv = self.query_one(ListView)
        lv.clear()
        for c in self._candidates:
            lv.append(_CandidateRow(c))
        if self._candidates:
            lv.index = 0

        status = self.query_one("#status", Static)
        status.update(
            f"[dim]browsing[/dim] [b]{self.browse_dir}[/b]   "
            f"[dim]{len(self._candidates)} result(s)[/dim]"
        )
        self.sub_title = str(self.browse_dir)

    # ----- events -----

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._bookmark_mode:
            # Different input flow while naming a bookmark — ignore here.
            return
        self.query = event.value
        self._refresh()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        if self._bookmark_mode:
            self._finalize_bookmark()
        else:
            self.action_commit()

    # ----- helpers -----

    def _current(self) -> Optional[Candidate]:
        lv = self.query_one(ListView)
        idx = lv.index
        if idx is None or idx < 0 or idx >= len(self._candidates):
            return None
        return self._candidates[idx]

    # ----- actions -----

    def action_commit(self) -> None:
        # Guard against double-fire: on some platforms pressing Enter
        # while focused on Input triggers BOTH the priority key binding
        # and Input.Submitted, which would run this method twice.
        if self.committed_path is not None:
            return
        cand = self._current()
        if cand is None:
            return
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
        cand = self._current()
        if cand is None:
            return
        try:
            if cand.path.is_dir():
                self.browse_dir = cand.path.resolve()
                # Reset the query so the new dir's children show up.
                self.query_one(Input).value = ""
                self.query = ""
                self._refresh()
        except OSError:
            pass

    def action_ascend(self) -> None:
        parent = self.browse_dir.parent
        if parent != self.browse_dir:
            self.browse_dir = parent
            self.query_one(Input).value = ""
            self.query = ""
            self._refresh()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_bookmark(self) -> None:
        cand = self._current()
        if cand is None:
            return
        self._enter_bookmark_mode(cand.path.resolve())

    def action_remove_bookmark(self) -> None:
        cand = self._current()
        if cand is None or cand.source is not Source.BOOKMARK:
            return
        if self.bookmarks.remove(cand.label):
            self.bookmarks.save()
            self._refresh()

    def action_forget_recent(self) -> None:
        cand = self._current()
        if cand is None or cand.source is not Source.RECENT:
            return
        if self.history.forget(cand.path):
            self.history.save()
            self._refresh()

    # ----- bookmark naming flow -----

    def _enter_bookmark_mode(self, path: Path) -> None:
        self._bookmark_mode = True
        self._pending_bookmark_path = path
        inp = self.query_one(Input)
        inp.value = path.name
        inp.placeholder = f"name this bookmark for {path}  (Enter to save, Esc to cancel)"
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


def run_app(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Launch the TUI. Returns the chosen path, or None if cancelled."""
    config = Config.load()
    bookmarks = Bookmarks.load()
    history = History.load()
    app = RootApp(
        config=config,
        bookmarks=bookmarks,
        history=history,
        start_dir=(start_dir or Path.cwd()).resolve(),
    )
    app.run()
    return app.committed_path
