# root

`root` is the command that gets you where you need to be without a lot of typing.

It pops up a small terminal UI listing all the directories you might want to
jump to — your bookmarks, your recent dirs (ranked by frecency), the children
of the folder you're in, and anything matching a fuzzy search across your
configured project roots. Hit Enter, and your shell `cd`s into the choice.

Works on Linux, macOS, and Windows. Bash, Zsh, Fish, PowerShell, and cmd.exe.

## Install

```sh
pip install root-cli
```

Then wire it into your shell so that `root` can actually change directories
(a Python child process can't, on its own, `cd` its parent shell — we need a
tiny wrapper function that does it).

### bash / zsh
Add this to your `~/.bashrc` or `~/.zshrc`:
```sh
eval "$(root init-shell bash)"   # or  zsh
```

### fish
```fish
root init-shell fish | source
# or persistently:
root init-shell fish > ~/.config/fish/functions/root.fish
```

### PowerShell
Append to your `$PROFILE`:
```powershell
root init-shell powershell | Out-String | Invoke-Expression
```
Or persistently:
```powershell
root init-shell powershell >> $PROFILE
```

### cmd.exe
The trickiest of the bunch. The wrapper is a batch file you need to put on
your PATH *before* the directory where pip installs `root.exe`. Run:
```cmd
root init-shell cmd
```
and save the output as `root.cmd` somewhere on your PATH ahead of your
Python Scripts dir. Or use a `doskey` macro from cmd.exe AutoRun — see the
comments in the printed output for the registry one-liner.

## Use

Just type `root` from anywhere. A list appears:

```
* work       /Users/me/code/big-project       (bookmarked)
~ /Users/me/code/api-service                  (recent)
~ /Users/me/Documents/notes
> ..         up to /Users/me                  (jump to parent)
> tests/                                      (child of cwd)
> src/
? alpha-service  (matched from ~/code/*)
```

The `..` row is only shown when you're not at the filesystem root of a
drive (so on `/` or `C:\`, it disappears).

- Type to fuzzy-filter. All four sources merge into one ranked list.
- ↑/↓ to move. **Enter** to commit and `cd` (works on `..` too —
  cds into the parent).
- **→** to descend into the highlighted directory without committing
  (tree-browse mode); **←** goes up one level.
- **Ctrl+B** bookmarks the highlighted dir (asks for a name).
- **Ctrl+D** removes the highlighted bookmark.
- **Ctrl+H** forgets the highlighted recent.
- **Esc** quits without changing dir.

### Subcommands (no TUI)

```sh
root add work ~/code/big-project   # add a bookmark (default: cwd)
root rm work                       # remove a bookmark
root ls                            # list bookmarks
root recent                        # list frecent directories
root forget                        # remove cwd from history
root config                        # show config / bookmark / history paths
```

## Configuration

Run `root config` to see where your files live. The defaults:

- Linux:   `~/.config/root/`
- macOS:   `~/Library/Application Support/root/`
- Windows: `%APPDATA%\root\`

Override with `$ROOT_CONFIG_DIR`.

`config.toml` looks like:
```toml
# Globbed one level deep when you type a query.
search_roots = ["~/code/*", "~/projects/*"]

# Maximum results displayed at once.
max_results = 50

# How many recents to show on the empty-query default view.
recent_limit = 10

# Include dot-directories in the tree browser.
show_hidden = false
```

`bookmarks.toml`:
```toml
[bookmarks]
work = "/Users/me/code/big-project"
dot  = "/Users/me/.dotfiles"
```

`history.json` is managed automatically — every `cd` via `root` updates it.

## How it works

The wrapper function calls the Python CLI. The CLI runs the Textual UI,
writes the chosen path to a sentinel file in the config dir, then exits.
The wrapper reads that file via `root which` and `cd`s. Cancelling (Esc)
clears the sentinel so the wrapper stays put.

## License

MIT.
