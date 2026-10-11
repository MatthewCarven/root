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
- Context-sensitive arrow keys in the search box: left at cursor
  position 0 ascends, right at end-of-text descends; mid-text they
  move the cursor as a normal Input. Shift+arrow selection untouched.
- Interactive preview pane: Tab focuses it (Shift+Tab / ← back),
  ↑/↓ pick an entry. Enter on a directory commits (cd & exit); Enter
  on a file launches it via the OS default handler and the TUI stays
  open. Shift+Enter / → on a directory descends the browser into it.
- Launch memory: files opened from the preview pane are recorded in a
  new `launches` section of history.json (frecency-tracked, kept
  separate so they never rank as cd targets), and the file's folder
  gets a normal history visit. Groundwork for a future launch-history
  fuzzy-search source.
- Compat fix: `Input.action_cursor_left/right` signature differs
  across Textual releases (no `select` parameter before ~0.76); the
  search box now checks the installed signature, fixing mid-text
  arrow keys crashing on textual 0.71.0 (found when the dev machine's
  environment drifted to py3.14 + textual 0.71.0).
- Preview pane is debounced on cursor moves: it rebuilds once the
  results cursor has rested for 333ms, so a held ↑/↓ no longer lists
  every directory on the way past. Typing and navigating still update
  it at once; Tab flushes a pending update so you never step into a
  stale listing.
- New `preview_delay_ms` config setting (default 333) for that delay;
  `0` restores instant updates. Config files without it get the default.
- Docs: the Windows config directory is `%LOCALAPPDATA%\root\`, not
  `%APPDATA%`; README now covers `uninstall-shell`, `forget [PATH]`, and
  the edge-only behaviour of ←/→ while typing.
- Fix: `uninstall-shell powershell` only looked at PowerShell 7's
  `$PROFILE`, so a wrapper in Windows PowerShell 5.1's profile (or a
  VS Code / ISE host profile) survived. It now sweeps every per-user
  profile of both editions, asking each installed edition where they
  live (so a OneDrive-redirected Documents folder is found), and also
  removes exact hand-appended copies from `init-shell >> $PROFILE`. A
  `root` function it didn't write is reported, never touched. Works
  without PowerShell on PATH.
- `install-shell powershell` replaces a hand-appended copy instead of
  adding a second definition beneath it.
- `install-shell powershell` installs into every installed edition's
  `$PROFILE` (Windows PowerShell 5.1 and PowerShell 7), not just the
  first one found on PATH, so `root` can change directory in both. If
  one edition can't be queried, the other is still installed and the
  message says which was skipped.
- Warns when `root` is used without its shell wrapper. The picker opens
  either way, but only the wrapper can `cd`. A pick that no wrapper read
  (via `root which`) gets a yellow notice at the top of the next launch,
  pointing at `root install-shell auto`. It works with every existing
  wrapper, so no reinstall is needed, and it warns once per missed pick.
- Tests: every test now gets a throwaway config dir (autouse fixture).
  Two TUI tests had been overwriting the real history.json on each run.
- PowerShell profiles are read and written in their own encoding
  (UTF-16 from Windows PowerShell 5.1's `>>`, UTF-8 with or without
  BOM) instead of assuming UTF-8.
