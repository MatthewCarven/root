# TODO

## Nice-to-haves

- [ ] Preview pane: show first-level contents of the highlighted dir on
      the right side of the UI (Textual makes this easy).
- [ ] `.gitignore`-aware tree browsing (skip vendored dirs).
- [ ] Multi-level glob: today search roots are one level deep
      (`~/code/*`); allow `~/code/**` with sensible depth limits and
      caching.
- [ ] Faster matcher: switch to a Rust-backed fuzzy lib (`rapidfuzz`?)
      if scoring becomes a bottleneck on large search roots.
- [ ] Theme support — read `theme = "dark"|"light"` from config and
      apply Textual themes.
- [ ] PowerShell auto-install: `root init-shell powershell --install`
      that appends the snippet to `$PROFILE` if not already present.

## Known limitations

- cmd.exe install is awkward because `pip install` puts `root.exe` on
  PATH and cmd's PATHEXT puts `.exe` before `.cmd`. Workaround
  documented but not pretty.
- The tree browser dereferences symlinks at display time, which may
  surprise users on macOS (`~/Documents` → `~/Library/...`). Consider
  a config flag to disable resolve().
- No tests yet for the Textual UI itself (Textual's pilot harness
  would let us add some).
