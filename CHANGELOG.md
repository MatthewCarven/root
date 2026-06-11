# Changelog

## 0.1.0 — 2026-05-15

Initial release.

- Cross-platform terminal UI for jumping to directories (Linux, macOS, Windows).
- Four navigation sources merged into one ranked list: bookmarks,
  frecency-ranked recents, the tree of the current directory, and
  one-level-deep glob expansion of configured search roots.
- Smart-case fuzzy subsequence matcher with consecutive, word-boundary,
  basename-position, and gap-penalty heuristics.
- Synthetic `..` parent entry on subfolders; hidden at filesystem roots.
- Shell wrappers for bash, zsh, fish, PowerShell, and cmd.exe.
- `root add / rm / ls / recent / forget / init-shell / which / config`
  headless subcommands for scripting and setup.
- 35 unit tests across matcher, frecency, config, and candidate
  aggregation.

## 0.1.1 — 2026-05-15

Polish pass after first real use:

- Added synthetic `..` parent-navigation row (Enter ascends the view
  instead of committing) and `.` commit-current-dir row.
- Default cursor position is now context-aware: skips synthetic rows
  in the starting dir, lands on `.` once you've navigated.
- New `root install-shell <shell>` subcommand: idempotent, marker-
  bounded snippet insertion. Handles `bash`, `zsh`, `fish`,
  `powershell`, `cmd`, and `auto` for shell autodetect.
- cmd.exe install reworked: uses doskey AutoRun (resolved before any
  PATH lookup) instead of trying to win the user-vs-system PATH race.
  Preserves any prior AutoRun the user had.
- Broadcasts `WM_SETTINGCHANGE` after registry edits so new shells
  pick up changes without a reboot.
- Better Windows error handling around `Path.resolve()`.

## Unreleased

- Preview pane: right-side panel showing first-level contents of the
  highlighted row (dirs first, 40-entry cap, hidden-file aware).
- New `root uninstall-shell <shell|auto>` subcommand: removes the
  marker-bounded wrapper from rc/profile files (bash/zsh/powershell),
  deletes the fish function file, and for cmd.exe strips the doskey
  entry from AutoRun (deleting the value if nothing else remains) and
  removes `~/.root/bin/root.cmd`. Safe to re-run; reports what it found.
