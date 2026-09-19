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
- [ ] Matthew: field-test the pane on Windows Terminal (Tab in, launch
      a file, Shift+Enter drill-down) — pilot tests can't see rendering.

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

- [ ] `uninstall-shell powershell` may miss the wrapper. Matthew reported
      it not taking effect (2026-06-15). Two suspects: (1) benign — the
      function was removed but bare `root.exe` on PATH still launches the
      TUI, so it *looks* un-removed; (2) real — `$PROFILE` is per-edition
      / per-host, so install and uninstall can target different files
      (pwsh ConsoleHost vs Windows PowerShell 5.1 `WindowsPowerShell\` vs
      VS Code host). Fix: sweep all known PS profile paths on uninstall,
      the way bash/zsh already sweep multiple rc files. cmd uninstall
      confirmed working.

## Known limitations

- cmd.exe install is awkward because `pip install` puts `root.exe` on
  PATH and cmd's PATHEXT puts `.exe` before `.cmd`. Workaround
  documented but not pretty.
- The tree browser dereferences symlinks at display time, which may
  surprise users on macOS (`~/Documents` → `~/Library/...`). Consider
  a config flag to disable resolve().
- ~~No tests yet for the Textual UI itself~~ First pilot-harness tests
  landed (arrow-key edge navigation); coverage of the UI is still thin.

## State at 2026-06-11 (second session)

- Preview pane field-tested by Matthew on Windows Terminal: approved
  as-is, no polish requested. It already caught one mis-set bookmark.
- `root uninstall-shell` implemented and committed. 74/74 tests green.
- **Matthew: push** -- unpushed commits on main (housekeeping, preview
  pane, uninstall-shell).
- **Matthew: optional field check** -- run `root uninstall-shell cmd`
  then `root install-shell cmd` to confirm the AutoRun roundtrip on
  real Windows (sandbox tests mock winreg paths only at the merge/
  unmerge string level).
- Likely next: pip post-install hint (needs investigation -- wheels
  lack post-install hooks) or `.gitignore`-aware tree browsing.
