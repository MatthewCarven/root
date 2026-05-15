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
