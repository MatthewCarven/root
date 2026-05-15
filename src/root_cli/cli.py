"""CLI entry point.

Run with no subcommand → launches the TUI, writes the chosen path to the
sentinel file (``last_target`` in the config dir), and exits.

Subcommands:
- ``root add NAME [PATH]``     Add a bookmark (path defaults to cwd).
- ``root rm NAME``             Remove a bookmark.
- ``root ls``                  List bookmarks.
- ``root recent``              List frecent dirs.
- ``root forget [PATH]``       Forget a recent (default: cwd).
- ``root init-shell SHELL``    Print the shell wrapper for SHELL.
- ``root which``               Print the last chosen path (for wrappers).
- ``root config``              Show the config file path.

The default invocation prints nothing to stdout on success — the wrapper
reads the sentinel file. Errors go to stderr.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from importlib import resources
from pathlib import Path
from typing import List, Optional

from root_cli import __version__
from root_cli.config import Bookmarks, Config
from root_cli.history import History
from root_cli.paths import (
    bookmarks_path,
    config_path,
    ensure_config_dir,
    history_path,
    target_path,
)


SUPPORTED_SHELLS = ("bash", "zsh", "fish", "powershell", "cmd")


def _print_shell_wrapper(shell: str) -> int:
    """Print the wrapper for the given shell to stdout."""
    shell = shell.lower()
    filename = {
        "bash": "root.sh",
        "zsh": "root.sh",
        "fish": "root.fish",
        "powershell": "root.ps1",
        "pwsh": "root.ps1",
        "cmd": "root.cmd",
    }.get(shell)
    if filename is None:
        print(
            f"unknown shell: {shell!r}. supported: {', '.join(SUPPORTED_SHELLS)}",
            file=sys.stderr,
        )
        return 2
    try:
        text = resources.files("root_cli.shell").joinpath(filename).read_text(
            encoding="utf-8"
        )
    except (FileNotFoundError, ModuleNotFoundError):
        print(f"wrapper file {filename!r} not found in package", file=sys.stderr)
        return 1
    sys.stdout.write(text)
    return 0


def _write_target(path: Path) -> None:
    ensure_config_dir()
    target_path().write_text(str(path), encoding="utf-8")


def _clear_target() -> None:
    p = target_path()
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


def _cmd_launch(_args: argparse.Namespace) -> int:
    # Defer import so `root --help` and subcommands don't import textual.
    from root_cli.app import run_app

    _clear_target()
    try:
        start = Path.cwd()
    except FileNotFoundError:
        start = Path.home()

    chosen: Optional[Path] = None
    try:
        chosen = run_app(start)
    except KeyboardInterrupt:
        chosen = None
    except Exception as e:  # pragma: no cover - defensive
        print(f"root: error running TUI: {e}", file=sys.stderr)
        return 1

    if chosen is None:
        # User cancelled — no target file written; wrapper stays put.
        return 130
    _write_target(chosen)
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    bookmarks = Bookmarks.load()
    target = Path(args.path).expanduser().resolve() if args.path else Path.cwd().resolve()
    if not target.is_dir():
        print(f"root: not a directory: {target}", file=sys.stderr)
        return 1
    bookmarks.add(args.name, target)
    bookmarks.save()
    print(f"bookmarked: {args.name} -> {target}")
    return 0


def _cmd_rm(args: argparse.Namespace) -> int:
    bookmarks = Bookmarks.load()
    if bookmarks.remove(args.name):
        bookmarks.save()
        print(f"removed bookmark: {args.name}")
        return 0
    print(f"root: no such bookmark: {args.name}", file=sys.stderr)
    return 1


def _cmd_ls(_args: argparse.Namespace) -> int:
    bookmarks = Bookmarks.load()
    items = bookmarks.items()
    if not items:
        print("(no bookmarks — use `root add NAME` to create one)")
        return 0
    width = max(len(name) for name, _ in items)
    for name, p in items:
        print(f"{name.ljust(width)}  {p}")
    return 0


def _cmd_recent(_args: argparse.Namespace) -> int:
    h = History.load()
    ranked = h.ranked(limit=50)
    if not ranked:
        print("(no recent directories yet — visit some with `root` first)")
        return 0
    for p, s in ranked:
        print(f"{s:6.2f}  {p}")
    return 0


def _cmd_forget(args: argparse.Namespace) -> int:
    h = History.load()
    target = Path(args.path).expanduser().resolve() if args.path else Path.cwd().resolve()
    if h.forget(target):
        h.save()
        print(f"forgot: {target}")
        return 0
    print(f"root: not in history: {target}", file=sys.stderr)
    return 1


def _cmd_init_shell(args: argparse.Namespace) -> int:
    return _print_shell_wrapper(args.shell)


def _cmd_which(_args: argparse.Namespace) -> int:
    p = target_path()
    if not p.exists():
        return 1
    sys.stdout.write(p.read_text(encoding="utf-8"))
    return 0


def _cmd_config(_args: argparse.Namespace) -> int:
    # Make sure the file exists so users have something to open.
    Config.load()
    print(f"config:    {config_path()}")
    print(f"bookmarks: {bookmarks_path()}")
    print(f"history:   {history_path()}")
    print(f"target:    {target_path()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="root",
        description="Terminal UI for jumping to the folder you want, fast.",
    )
    p.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = p.add_subparsers(dest="command")

    sp = sub.add_parser("add", help="add a bookmark")
    sp.add_argument("name", help="alias for the bookmark")
    sp.add_argument("path", nargs="?", help="path to bookmark (default: cwd)")
    sp.set_defaults(func=_cmd_add)

    sp = sub.add_parser("rm", help="remove a bookmark")
    sp.add_argument("name")
    sp.set_defaults(func=_cmd_rm)

    sp = sub.add_parser("ls", help="list bookmarks")
    sp.set_defaults(func=_cmd_ls)

    sp = sub.add_parser("recent", help="list frecent directories")
    sp.set_defaults(func=_cmd_recent)

    sp = sub.add_parser("forget", help="remove an entry from frecency history")
    sp.add_argument("path", nargs="?")
    sp.set_defaults(func=_cmd_forget)

    sp = sub.add_parser(
        "init-shell",
        help="print the shell wrapper for the given shell (bash|zsh|fish|powershell|cmd)",
    )
    sp.add_argument("shell", choices=SUPPORTED_SHELLS)
    sp.set_defaults(func=_cmd_init_shell)

    sp = sub.add_parser(
        "which",
        help="print the last chosen path (used by the shell wrapper)",
    )
    sp.set_defaults(func=_cmd_which)

    sp = sub.add_parser("config", help="show config file paths")
    sp.set_defaults(func=_cmd_config)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        return _cmd_launch(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
