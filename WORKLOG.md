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
