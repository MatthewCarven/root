# root

`root` is the command that gets you where you need to be without a lot of typing.

It pops up a small terminal UI listing all the directories you might want to
jump to — your bookmarks, your recent dirs (ranked by frecency), the children
of the folder you're in, and anything matching a fuzzy search across your
configured project roots. Hit Enter, and your shell `cd`s into the choice.

Works on Linux, macOS, and Windows. Bash, Zsh, Fish, PowerShell, and cmd.exe.

<img width="1115" height="628" alt="image" src="https://github.com/user-attachments/assets/c16ccf1d-23fb-4324-a579-ce794e276c9b" />

## How you will look to people not using root

<img width="543" height="369" alt="image" src="https://github.com/user-attachments/assets/61d12620-63b5-4da6-97d4-7634e23d9ef1" />


## Install

```sh
pip install root-cli
```

Then wire it into your shell so that `root` can actually change directories
(a Python child process can't, on its own, `cd` its parent shell — we need a
tiny wrapper function that does it).

### One-liner install (recommended)

```sh
root install-shell auto
```

This detects your shell from `$SHELL` / your platform and does the right
thing: creates the rc file or `$PROFILE` if missing, appends the wrapper
inside marker comments (so re-running is idempotent), and prints whatever
remaining step you need to take (usually one `source` command). You can
also be explicit:

```sh
root install-shell bash         # appends to ~/.bashrc
root install-shell zsh          # appends to ~/.zshrc
root install-shell fish         # writes ~/.config/fish/functions/root.fish
root install-shell powershell   # appends to $PROFILE of every installed PowerShell
                                # (5.1 and 7 each have their own; creates if missing)
root install-shell cmd          # drops root.cmd in %USERPROFILE%\.root\bin
                                # and prepends that dir to your user PATH
```

After install, load the wrapper in your *current* session:

```sh
source ~/.bashrc          # bash
source ~/.zshrc           # zsh
. $PROFILE                # PowerShell
# fish autoloads it — just open a new shell, or:
source ~/.config/fish/functions/root.fish
# cmd.exe: open a new cmd.exe window so the new PATH takes effect.
```

### If `install-shell` isn't an option (or you want to see what it does)

Use `root init-shell <shell>` to *print* the wrapper to stdout — useful
for inspection or piping into a custom location:

```sh
eval "$(root init-shell bash)"                        # bash/zsh, one-shot
root init-shell fish | source                          # fish, one-shot
root init-shell powershell | Out-String | Invoke-Expression  # PowerShell
```

### PowerShell execution policy

If `. $PROFILE` errors with "running scripts is disabled on this system,"
you need to allow signed local scripts once per user. Windows PowerShell
5.1 and PowerShell 7 keep separate policies, so run it in whichever one
complained (5.1 defaults to Restricted; 7 already allows it):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Uninstall

```sh
root uninstall-shell auto        # or bash / zsh / fish / powershell / cmd
pip uninstall root-cli
```

`uninstall-shell` removes what `install-shell` added: the marked block
in your rc files, the fish function file, or (for cmd.exe) the doskey
AutoRun entry and `root.cmd`. For PowerShell it checks every profile of
both editions (Windows PowerShell 5.1 and PowerShell 7, console, VS
Code and ISE), and also removes exact copies of the wrapper that were
appended by hand with `root init-shell powershell >> $PROFILE`. If it
finds a `root` function it didn't write, it leaves it alone and tells
you where it is.

It's safe to re-run and reports what it found. Open a new shell
afterwards; the current one still has the old function loaded. Until
you `pip uninstall root-cli`, typing `root` still opens the picker
(via `root.exe`), but it can't change directory any more.

## Use

Just type `root` from anywhere. A list appears:

```
> .          commit /Users/me/code/big-project   (commit current view)
> ..         up to /Users/me/code                (go up one level)
* work       /Users/me/code/big-project          (bookmarked)
~ /Users/me/code/api-service                     (recent)
~ /Users/me/Documents/notes
> tests/                                         (child of cwd)
> src/
? alpha-service  (matched from ~/code/*)
```

Two synthetic rows are special:

- **`.`** commits the directory you're currently *viewing*. Useful
  after navigating up via `..` — once you've landed on the folder you
  want, hit Enter on `.` to cd there.
- **`..`** ascends the view to the parent. Enter on `..` does *not*
  exit — it just changes the visible folder. (Use it like a "go up"
  button. To actually land at a parent, navigate up then Enter on `.`,
  or arrow-down to a sibling and Enter on that.) Hidden at filesystem
  roots, where there is no parent.

The default cursor position is smart:

- In your starting directory, the cursor skips `.` and `..` and lands
  on the first real entry (first bookmark / recent / child), so hitting
  Enter takes you somewhere new — not a no-op cd to where you already
  are.
- Once you've navigated away (via `..` or →), the cursor defaults to
  `.`, so just pressing Enter commits the folder you're now viewing.

- Type to fuzzy-filter. All four sources merge into one ranked list.
  (The synthetic `.` and `..` rows disappear while you're filtering.)
- Inside a git repo, folders the repo ignores (`build/`, `dist/`,
  `__pycache__/` ...) are dimmed, marked `(gitignored)`, and listed
  after everything else, so the clutter sinks without disappearing
  (plenty of ignored folders are ones you visit: data, saves, an
  editor install). Set `gitignored = "hide"` to drop them instead.
- ↑/↓ to move. **Enter** commits the highlighted entry and `cd`s there.
- **→** (or **Shift+Enter**) descends into the highlighted directory
  (browse without committing); **←** goes up one level (same as Enter
  on `..`). While you're typing, ← and → edit the search text as usual
  and only navigate from the edges: ← with the cursor at the start of
  the box, → with it at the end. Shift+Enter always descends.
- **Ctrl+B** bookmarks the highlighted dir (asks for a name).
- **Ctrl+D** deletes the highlighted entry — removes a bookmark (`*` row)
  or forgets a recent (`~` row), depending on what's highlighted.
- **Ctrl+H** is an alias for **Ctrl+D** (kept for muscle-memory).
- **Esc** quits without changing dir.

### The preview pane

The right-hand pane shows the first-level contents of whatever
directory is highlighted: folders first, up to 40 entries, then a
`… +N more` row.

When you move the cursor, the pane waits until it has rested for a
third of a second before listing the new folder, so holding ↑/↓ stays
smooth. Typing and navigating update it straight away, and Tab never
makes you wait. Set `preview_delay_ms` in `config.toml` to change the
delay (`0` updates instantly).

It's interactive:

- **Tab** moves focus into the pane (Tab again, **Shift+Tab**, or **←**
  goes back to the search box).
- ↑/↓ to pick an entry.
- **Enter** on a directory `cd`s there and exits — same meaning Enter
  has everywhere. **Enter** on a *file* opens it with your OS's default
  handler and the TUI **stays open**, so you can open several in a row.
  Launched files are remembered (the file in launch history, its folder
  as a normal visit).
- **Shift+Enter** (or **→**) on a directory descends the browser into
  it without exiting — the same "stay in the app" meaning it has in the
  main list.

### Subcommands (no TUI)

```sh
root add work ~/code/big-project   # add a bookmark (default: cwd)
root rm work                       # remove a bookmark
root ls                            # list bookmarks
root recent                        # list frecent directories
root forget [PATH]                 # remove a dir from history (default: cwd)
root config                        # show config / bookmark / history paths
root install-shell SHELL           # wire the cd wrapper into your shell
root uninstall-shell SHELL         # remove it again
root init-shell SHELL              # print the wrapper instead of installing
root --version
```

## Configuration

Run `root config` to see where your files live. The defaults:

- Linux:   `~/.config/root/`
- macOS:   `~/Library/Application Support/root/`
- Windows: `%LOCALAPPDATA%\root\`

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

# How long (ms) the cursor must rest before the preview pane updates.
# 0 = update instantly.
preview_delay_ms = 333

# Folders a git repo ignores: "dim" (sink + dim, default), "hide", or "show".
gitignored = "dim"
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

Without the wrapper, `root` still opens the picker, but your shell can't
move. root notices: a pick that no wrapper read with `root which` gets
a yellow warning at the top of the next launch, telling you to run
`root install-shell auto`.

## License

MIT.
