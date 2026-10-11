# Worklog

## 2026-05-15 — Initial scaffold

**Done**

- Defined the design with Matthew: shell-wrapper-based cd, all four nav
  sources, Textual TUI.
- Built the package skeleton (`pyproject.toml`, `src/root_cli/`,
  `tests/`).
- Implemented core modules:
  - `paths.py` — cross-platform config dir resolution via platformdirs,
    with `$ROOT_CONFIG_DIR` escape hatch for tests.
  - `config.py` — `Config` and `Bookmarks` TOML I/O. Default config is
    auto-seeded on first read so users have a discoverable file to edit.
  - `history.py` — frecency tracker with classic z-style decay
    (4x <1h, 2x <1d, 0.5x <1w, 0.25x older) × log(freq). Auto-prunes
    when MAX_ENTRIES is exceeded.
  - `matcher.py` — fzf-inspired subsequence scorer with consecutive,
    word-boundary, and basename-position bonuses. Smart case.
  - `candidates.py` — the heart of the "one list, four sources" design.
    Empty query → bookmarks → recents → tree children. Typed query →
    all sources scored and ranked together, deduplicated by absolute
    path (bookmark > recent > search > tree on ties).
  - `app.py` — Textual UI: Input + ListView, key bindings, inline
    bookmark-naming flow.
  - `cli.py` — argparse with subcommands (`add`, `rm`, `ls`, `recent`,
    `forget`, `init-shell`, `which`, `config`). Default invocation runs
    the TUI and writes the chosen path to a sentinel file.
- Wrote shell wrappers for bash/zsh, fish, PowerShell, and cmd.exe.
  All use `command root` (or the equivalent) to bypass the function
  during recursion. cmd.exe wrapper documents the AutoRun + doskey
  workaround for the `.exe` precedence issue.
- Tests: matcher, history (with frecency + pruning), config
  round-trip, candidate aggregation (dedupe, source priority, search
  root globbing).
- Docs: README with install + usage; this worklog.

**Open questions / future ideas**

See TODO.md.

## 2026-05-15 — UX iteration with Matthew

After the initial scaffold, several refinements based on real use:

**'..' parent navigation row.** Added a synthetic `..` entry to the
default view (hidden at filesystem roots). Enter on `..` *navigates*
the browse view to the parent rather than committing, so the user can
walk up the tree one Enter at a time. This sidesteps a Windows Textual
quirk where Enter would double-fire on the priority binding + Input
submission.

**'.' commit-current-dir row.** Symmetric to `..`. Added at the very
top of the default view. Enter on `.` commits the directory currently
being browsed. Smart default cursor: skip `.` and `..` in the *starting*
dir (so Enter takes you somewhere new), but land on `.` once the user
has navigated away (so Enter commits the new view).

**install-shell subcommand.** Realized that asking users to `eval` /
`Add-Content` the wrapper themselves had several rough edges — most
notably, brand-new PowerShell users have no `$PROFILE` file or even
parent dir, and the install steps were per-shell esoterica. Built
`root install-shell <bash|zsh|fish|powershell|cmd|auto>` that handles
file creation, idempotent marker-bounded snippet insertion, and prints
the next step.

**cmd.exe install: PATH won't work, doskey will.** Found out the hard
way that prepending our bindir to *user* PATH doesn't beat `root.exe`
from the Python Scripts dir, because Windows always evaluates system
PATH ahead of user PATH. Replaced PATH manipulation with a doskey
AutoRun macro — doskey aliases are resolved before any PATH lookup,
so they sidestep the system-vs-user ordering entirely. Preserves any
existing AutoRun by splicing inside a `::root-doskey::` sentinel.
Also broadcasts `WM_SETTINGCHANGE` so Explorer-spawned shells pick up
env changes without a logoff/reboot.

**Discovered Windows footgun:** `cmd` spawned as a child of PowerShell
inherits PowerShell's env block, not the registry. So even after
modifying the registry, a `cmd` started inside PowerShell still sees
PowerShell's stale env. Documented in the cmd installer's success
message so the next user isn't confused.

**Tests** grew from 31 to 53. New coverage:
- 5 tests for the `..` row (shown/hidden, path correctness, absent
  in search, default-view-only).
- 2 tests for the `.` row (path correctness, always shown).
- 11 tests for install-shell (idempotent replace, missing-rc
  creation, fish XDG honoring, unknown shell, auto-detect).
- 5 tests for the doskey AutoRun merge logic (empty / existing /
  in-place replace / preserve-prologue).

Both Matthew's PowerShell AND cmd setups confirmed working end-to-end.

## 2026-06-11 — Preview pane

**Preview pane shipped** (first item on the nice-to-have list). The TUI
now has a right-side panel showing the first-level contents of whatever
row is highlighted: directories first with trailing `/`, then files,
both case-insensitively sorted, capped at 40 entries with a `+N more`
marker. Synthetic rows preview their concrete path ('.' = browse dir,
'..' = parent). Empty dirs show `<empty>`; permission/OS errors come
back as one explanatory line instead of raising.

Implementation: pure `preview_entries()` helper in candidates.py (fully
unit-testable, no Textual import), wired into app.py via a Horizontal
container (ListView 2fr / preview 1fr) and `on_list_view_highlighted`.
Honors `show_hidden` the same way the tree browser does. Rich markup in
filenames is escaped.

**Sandbox footgun discovered:** editing candidates.py via the host-side
file tools produced a truncated view on the Linux mount (stale size,
mixed content) that wouldn't refresh — stale `__pycache__` first masked
it, then a SyntaxError exposed it. Rewriting the file from the sandbox
shell side resynced both views. If pytest ever reports a SyntaxError on
a file that looks fine, suspect the mount, not the code.

Tests 53 → 58 (5 new for preview_entries: ordering, hidden-file
handling, empty dir, truncation marker, unreadable dir). Verified the
pane live with Textual's pilot harness: highlight changes update the
panel correctly.

Not yet visually checked on Matthew's Windows terminal — worth one
quick look at proportions/border before calling it polished.

Session ended pending Matthew's field run of the preview pane. State
snapshot written to TODO.md ("State at 2026-06-11 session end").

## 2026-06-11 — Field test passed; uninstall-shell

**Preview pane field test: passed.** Matthew ran it on Windows
Terminal (PowerShell 7.6.2), proportions and feel approved with no
changes requested. Bonus: the pane immediately surfaced a mis-set
bookmark (`-=Ouroboros=-` pointing one level off) — exactly the kind
of thing it exists for. Fix is user-side: `root rm` + `root add`.

**`root uninstall-shell <shell|auto>` shipped** (Matthew reached for
it during the field test and it didn't exist — strongest possible
prioritization signal). Mirrors install-shell:

- bash/zsh: removes the BEGIN/END marker block from *all* rc
  candidates that contain it, preserving surrounding content and
  collapsing the blank line install adds (clean roundtrip).
- fish: deletes the autoloaded function file (XDG-aware).
- powershell: locates $PROFILE the same way install does, removes the
  block; missing profile or absent block are safe no-ops.
- cmd: `_unmerge_autorun()` strips the `(...) ::root-doskey::` block
  from the AutoRun registry value, tidies dangling ampersands,
  deletes the value outright if nothing else remains; removes
  root.cmd and the bin dir if empty; broadcasts WM_SETTINGCHANGE.
- Every path is idempotent and reports what it found/skipped.

Edits made from the sandbox shell side throughout (per the mount
footgun from earlier today) — no stale-view issues this time.

Tests 58 → 74 (16 new: marker-block roundtrip, bash/zsh removal and
no-ops, fish XDG handling, autorun unmerge prologue/epilogue/dangling-
ampersand cases, unknown-shell dispatch).

Not runnable end-to-end here (winreg is Windows-only); flagged a
one-minute AutoRun roundtrip check for Matthew in TODO.

## 2026-06-12 — Push rejection: diverged remote, rebased

Matthew's push bounced: origin/main had `b2daaad` ("Update image in
README.md", made via the GitHub web UI on 2026-05-24) that local
history didn't include. Not the venv — a venv never affects git.

Resolution: rebased our 4 commits onto `b2daaad`. One expected
conflict (README.md whole-file, because the line-ending normalization
in the working-agreement commit collides with the image edit) —
resolved by taking the normalized LF version and re-applying the new
image line. New tip `8ced80c`; all 74 tests green post-rebase.

Sandbox notes: the mounted repo's git index corrupted repeatedly
("bad signature 0x00000000") during rebase attempts, plus a zeroed
ORIG_HEAD and a stale rebase-merge dir. Worked around by doing the
rebase in a local clone under /tmp and syncing the result back via
fetch + update-ref + index rebuild. Rule of thumb going forward:
commit on the mount is fine; anything index-churny (rebase, merge)
should be done in a /tmp clone.

## 2026-06-12 — Context-sensitive arrows

Matthew flagged that the left arrow "gets swallowed by the input box"
but didn't want to lose cursor movement — and concluded he was asking
for the impossible. He wasn't: the fzf-style resolution is to make the
arrows edge-sensitive. New `_SearchInput(Input)` subclass overrides
`action_cursor_left/right`: left at cursor position 0 → ascend; right
at end-of-text → descend; anywhere mid-text → normal cursor movement.
Shift+arrow (selection) is never hijacked. No keystroke changed
meaning — the hijacked positions were no-ops before.

Also the first committed Textual pilot tests (tests/test_app.py, 5 of
them), using plain `asyncio.run` so no pytest-asyncio dependency.
Tests 74 → 79.

## 2026-09-20 — Designed: Tab-able preview pane (files launchable)

Matthew wants the preview pane interactive: Tab to enter it, up/down
to pick an entry, Enter to act. Design settled together:

- Enter on a dir in the pane = commit (cd & exit). Root is "foremost
  a replacement for cd" — Enter always means "take me there".
- Shift+Enter = the same intent but *stay in the app* (descend the
  browser into that dir), consistent with the main list's Shift+Enter.
- Enter on a file = launch via OS default handler; TUI stays open
  (Matthew's explicit choice) so several files can be opened in a row.
- Launched executables get *remembered*: parent dir as a normal
  history visit + the file itself in a new `launches` history section,
  feeding a future LAUNCH fuzzy-search source (phase 2).
- Matthew mentioned root may one day be embedded on a RAM-based disk
  image — keep the launcher OS-handler-based (no hardcoded app paths)
  and noted the absolute-paths-in-history portability question in TODO.

Implementation notes from source inspection: #preview is a Static
(not focusable); preview_entries returns bare strings; up/down are
app-level bindings that query_one(ListView) — assumes exactly one
ListView, so the second list needs ids and pane-aware routing.
Full step list in TODO.md under "Planned — Tab-able preview pane".
Not implemented yet — plan only this session.

## 2026-09-20 — Implemented: interactive preview pane (phase 1)

The preview pane is now a real ListView you can Tab into. As designed:
Tab toggles search<->preview (Shift+Tab or left always returns; left-
as-return because ascending the browse dir while inspecting a
*different* dir's contents would be disorienting). Enter on a dir
commits (cd & exit); Enter on a file launches via the OS default
handler and the TUI stays open; Shift+Enter / right on a dir descends
the browser into it, keeping focus in the pane so you can drill
repeatedly. Launches are remembered: file -> new `launches` section in
history.json (frecency, pruned, never ranked as cd targets), parent
dir -> normal visit. New module launch.py (os.startfile / open /
xdg-open, non-blocking, error string back to the status line).

Structural: preview_entries now returns PreviewEntry records
(name/path/is_dir; marker rows carry no path and no-op on Enter); the
two ListViews got ids (#results / #preview) and every
query_one(ListView) call site was fixed; highlight events are filtered
by list id so preview-internal cursor moves don't rebuild the pane;
ctrl+b now refocuses the input (it can fire from the pane). Focus cue:
thick accent border-left on the pane via :focus-within.

Surprise find: the dev machine's env drifted to py3.14 + textual
0.71.0, where Input.action_cursor_left/right take no `select` param —
mid-text arrows CRASHED on current HEAD (3 pre-existing test failures,
confirmed on a clean stash). Added a signature-sniffing compat shim in
_SearchInput. Deviation from plan, noted per working agreement: fixing
it was load-bearing for the suite, not scope creep.

Tests 79 -> 88 (7 new pilot tests incl. marker-row no-op; 3 new
history tests incl. old-format load). All green. Docs: README preview
section, CHANGELOG, app.py key table, TODO phase-1 ticked. Flagged a
field-test for Matthew in TODO. Phase 2 (LAUNCH fuzzy source) still
queued.

## 2026-09-20 — "History not recording" report: false alarm, display dedupe

Matthew field-tested the pane (00:22) and reported main-view Enter no
longer adds to history. Investigated: history.json HAS all three of
his 00:22 test visits, written by the NEW code (the `launches` key is
present), timestamps matching his Enters 10s apart. Harness sweep of
every commit flow (default enter, arrows+enter, typed query+enter,
descend+'.', preview-dir enter, bookmark row) all record correctly.

Root cause of the perception: `_default_view`'s dedupe (unchanged
since 0.1.x) hides exactly the rows he was watching for — the dir you
just cd'd into is the one you're standing in when you reopen root, so
it's covered by the '.' row; and -=Programming=- is bookmarked, so it
shows as '*' not '~'. Net effect: after a test cd, the recents strip
looks identical. Nothing regressed; `root recent` shows the truth.

Repro-script blooper: the flow sweep called the real launcher once and
popped Notepad on Matthew's desktop (he closed it). Mock launch_path
in any future scratch repros. On the plus side: real-machine proof
that os.startfile launching works.

## 2026-10-11 — Preview pane delay (333ms debounce on cursor moves)

Matthew asked for the preview pane to wait 333ms before updating, so
holding up/down keeps the main list responsive. Done as a true
debounce: every results-list highlight restarts a Textual timer
(`RootApp.PREVIEW_DELAY = 0.333`); the pane rebuilds once, at the row
the cursor stops on, and skips the rebuild if it came back to the row
already shown (also kills the redundant second build every _refresh
used to do via the Highlighted event).

Deliberately NOT delayed: typing, descend/ascend, Ctrl+D — _refresh
still previews immediately (any direct _update_preview cancels the
pending timer). Tab with an update pending flushes it first, so you
never Tab into the previous row's listing. Known edge: a mouse click
into the pane within the 333ms window sees the old listing until the
timer fires; not worth handling.

Tests 88 -> 91: delay holds then fires; Tab mid-delay flushes and
Enter commits the right dir; navigation stays instant. Verified the
delay test fails against the old app.py.

## 2026-10-11 — preview_delay_ms config setting

Matthew asked for the delay to be a setting. `preview_delay_ms`
(default 333) in config.toml replaces the RootApp.PREVIEW_DELAY class
constant; negative values clamp to 0, and 0 skips the timer entirely
(instant preview, the pre-debounce behaviour). Older config files
without the key get the default. Added the commented key to the seeded
default config and to Matthew's live config at
%LOCALAPPDATA%/root/config.toml so he can find it.

Doc drift fixed in passing: README and paths.py said the Windows config
dir is %APPDATA%; platformdirs (non-roaming) actually puts it under
%LOCALAPPDATA%, which is where Matthew's file is.

Tests 91 -> 94: zero-delay instant preview, config default/roundtrip,
missing-key default and negative clamp.
