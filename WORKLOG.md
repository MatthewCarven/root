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
