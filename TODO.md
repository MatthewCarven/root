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
