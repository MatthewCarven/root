# TODO

## Nice-to-haves

- [x] Preview pane: show first-level contents of the highlighted dir on
      the right side of the UI (Textual makes this easy).
- [ ] `.gitignore`-aware tree browsing (skip vendored dirs).
- [ ] Multi-level glob: today search roots are one level deep
      (`~/code/*`); allow `~/code/**` with sensible depth limits and
      caching.
- [ ] Faster matcher: switch to a Rust-backed fuzzy lib (`rapidfuzz`?)
      if scoring becomes a bottleneck on large search roots.
- [ ] Theme support — read `theme = "dark"|"light"` from config and
      apply Textual themes.
- [x] Rough edge: brand new PowerShell users have no `$PROFILE` file
      (or even its parent dir). Naively running `Add-Content -Path
      $PROFILE` then fails with `DirectoryNotFoundException`.
- [x] `root install-shell <bash|zsh|fish|powershell|cmd|auto>` — does
      what `init-shell` did, plus: creates the target rc/profile file
      (and its parent dir) if missing, wraps the snippet in BEGIN/END
      markers so re-running replaces in place (no duplication), prints
      the next-step instructions per shell. cmd.exe variant writes
      `%USERPROFILE%\.root\bin\root.cmd` and prepends that dir to the
      user PATH via winreg.
- [ ] Print a one-line post-install hint after `pip install root-cli`
      pointing at `root install-shell auto`.
- [x] `root uninstall-shell` for symmetry (find marker block, delete
      it; for cmd, strip the doskey AutoRun entry and root.cmd).
- [ ] Source the rc/profile automatically when possible (currently we
      print the `source` command for the user to run — there's no
      portable way to mutate the parent shell from Python).
- [x] Preview pane waits for the cursor to rest before listing (333ms
      debounce), so holding up/down stays smooth. Tunable via
      `preview_delay_ms` in config.toml; 0 = instant. (2026-10-11)

## Planned — Tab-able preview pane (designed with Matthew, 2026-09-20)

Goal: Tab focuses the right-hand preview pane; up/down pick an entry;
Enter acts on it. Enter on a dir commits (cd & exit — root is foremost
a cd replacement); Shift+Enter on a dir descends the browser into it
and stays open (mirrors the main list's Shift+Enter). Enter on a file
launches it via the OS default handler and the TUI **stays open**;
launched files are remembered for a future launch-history source.

Phase 1 (the pane itself) — DONE 2026-09-20:

- [x] `preview_entries` → structured records (name, path, is_dir)
      instead of bare strings; keep `<empty>` / `<permission denied>` /
      `+N more` as non-interactive rows. Update tests.
- [x] Replace the `#preview` Static with a ListView; give the main
      list an id (`#results`) and fix every `query_one(ListView)` call
      site (they assume exactly one ListView today).
- [x] Tab toggles focus search↔preview (visible focus cue on the
      pane); Shift+Tab returns; Esc keeps meaning quit everywhere.
- [x] Route up/down + Enter/Shift+Enter by which pane is focused
      (`ListView.Selected` carries `event.list_view`; `action_descend`
      becomes pane-aware).
- [x] Cross-platform launcher helper: `os.startfile` (win) /
      `open` (mac) / `xdg-open` (linux), non-blocking, errors to the
      status line.
- [x] On file launch: record the file's parent dir as a normal
      history visit, and the file itself in a new `launches` section
      of history.json (schema-compatible: unknown keys ignored by old
      versions).
- [x] Docstring key table, status/footer hints, README key list.
- [x] Pilot-harness tests: tab focus, enter-on-dir commit,
      shift+enter descend, file-launch stays open (launcher mocked).
- [x] Matthew: field-test the pane on Windows Terminal (Tab in, launch
      a file, Shift+Enter drill-down). Done 2026-09-20; the one report
      that came out of it was a false alarm (see worklog).

Phase 2 (launch memory, later session):

- [ ] LAUNCH candidate source: frecent launched files surface in
      fuzzy search (icon `!`?); Enter launches them from the main
      list. Keeps cd candidates clean — files never rank as cd
      targets.
- [ ] RAM-disk / portable-image consideration: history stores
      absolute paths; if root ever ships embedded on a mounted image,
      paths may shift per mount. Investigate storing paths relative
      to a configurable anchor.

## Bugs / to investigate

- [x] `uninstall-shell powershell` may miss the wrapper. Matthew reported
      it not taking effect (2026-06-15). Fixed 2026-10-11: suspect (2)
      was real, plus a third cause. Uninstall now sweeps every profile
      of both editions and removes hand-appended (unmarked) copies too;
      the message also explains suspect (1). See worklog.
- [x] `install-shell powershell` installed into one edition only
      (PowerShell 7 if `pwsh` was on PATH, else 5.1), so someone using
      both got no wrapper in 5.1. Fixed 2026-10-11: installs into the
      console profile of every installed edition.

## Known limitations

- cmd.exe install is awkward because `pip install` puts `root.exe` on
  PATH and cmd's PATHEXT puts `.exe` before `.cmd`. Workaround
  documented but not pretty.
- The tree browser dereferences symlinks at display time, which may
  surprise users on macOS (`~/Documents` → `~/Library/...`). Consider
  a config flag to disable resolve().
- UI tests (Textual pilot harness, 15 of them) cover arrow-key edge
  navigation, the interactive preview pane, and the preview delay.
  They can't see rendering, so layout and focus styling still need a
  look by eye after UI changes.

## State at 2026-10-11

- Preview delay shipped (333ms debounce + `preview_delay_ms` setting).
- PowerShell uninstall bug fixed (both editions, every host, legacy
  unmarked copies), and install now covers both editions too.
  111/111 tests green.
- **Matthew: try the delay by feel.** Holding up/down should keep the
  list smooth and the pane should catch up once you stop. If 333 feels
  off, change `preview_delay_ms` in
  `%LOCALAPPDATA%/root/config.toml`.
- Matthew re-ran `install-shell powershell`: both profiles now define
  `root` once.
- **The test suite was overwriting Matthew's real history.json**
  (2026-09-20 to 2026-10-11). Fixed with an autouse fixture in
  tests/conftest.py; his frecency history is lost and will rebuild
  with use. 112/112 tests green. See worklog.
- **Matthew: optional, low odds** -- if File History or System
  Restore is on, `%LOCALAPPDATA%/root/history.json` -> Properties ->
  Previous Versions may hold a pre-wipe copy.
- Likely next: Phase 2 (LAUNCH fuzzy-search source), or the pip
  post-install hint (needs investigation -- wheels lack post-install
  hooks).
