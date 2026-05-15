"""Shell wrapper installers.

Each `install_*` function is *idempotent*: running it twice replaces
the snippet in place rather than duplicating it. The snippet is wrapped
in sentinel markers so we can find and replace it later cleanly.

Each installer returns ``InstallResult(success, target, message)`` so
the CLI can render a friendly success/failure block.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import List, Optional


MARKER_BEGIN = "# >>> root shell wrapper >>>"
MARKER_END = "# <<< root shell wrapper <<<"


@dataclass
class InstallResult:
    success: bool
    target: Optional[Path]
    message: str


def _wrapper_text(filename: str) -> str:
    return resources.files("root_cli.shell").joinpath(filename).read_text(
        encoding="utf-8"
    )


def _idempotent_replace(
    content: str,
    snippet: str,
    begin: str = MARKER_BEGIN,
    end: str = MARKER_END,
) -> str:
    """Insert or replace ``snippet`` between BEGIN/END markers in ``content``."""
    block = f"{begin}\n{snippet.rstrip()}\n{end}\n"
    pattern = re.compile(
        re.escape(begin) + r".*?" + re.escape(end) + r"\n?",
        re.DOTALL,
    )
    if pattern.search(content):
        return pattern.sub(block, content)
    if content and not content.endswith("\n"):
        content += "\n"
    if content:
        content += "\n"
    return content + block


# ----- bash / zsh -----

def install_bash_zsh(shell: str) -> InstallResult:
    home = Path.home()
    candidates: List[Path] = {
        "bash": [home / ".bashrc", home / ".bash_profile", home / ".profile"],
        "zsh":  [home / ".zshrc", home / ".zprofile"],
    }[shell]
    target = next((p for p in candidates if p.exists()), candidates[0])
    snippet = _wrapper_text("root.sh")
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(_idempotent_replace(existing, snippet), encoding="utf-8")
    msg = (
        f"Wrapper installed into {target}.\n"
        f"Load it in this session:  source {target}\n"
        f"(or simply open a new {shell} shell.)"
    )
    return InstallResult(True, target, msg)


# ----- fish -----

def install_fish() -> InstallResult:
    home = Path.home()
    base = Path(os.environ.get("XDG_CONFIG_HOME") or (home / ".config"))
    funcdir = base / "fish" / "functions"
    funcdir.mkdir(parents=True, exist_ok=True)
    target = funcdir / "root.fish"
    target.write_text(_wrapper_text("root.fish"), encoding="utf-8")
    msg = (
        f"Wrapper installed as {target}.\n"
        f"Fish autoloads it. To load in this session:  source {target}\n"
        "(or open a new fish shell.)"
    )
    return InstallResult(True, target, msg)


# ----- PowerShell -----

def install_powershell() -> InstallResult:
    ps_cmd = shutil.which("pwsh") or shutil.which("powershell")
    if ps_cmd is None:
        return InstallResult(
            False, None,
            "PowerShell isn't on PATH. Install PowerShell, then try again.",
        )
    res = subprocess.run(
        [ps_cmd, "-NoProfile", "-Command", "Write-Output $PROFILE"],
        capture_output=True, text=True, check=False,
    )
    if res.returncode != 0 or not res.stdout.strip():
        return InstallResult(
            False, None,
            f"Could not determine $PROFILE: {res.stderr.strip() or 'no output'}",
        )
    profile = Path(res.stdout.strip())
    profile.parent.mkdir(parents=True, exist_ok=True)
    existing = profile.read_text(encoding="utf-8") if profile.exists() else ""
    snippet = _wrapper_text("root.ps1")
    profile.write_text(_idempotent_replace(existing, snippet), encoding="utf-8")
    msg = (
        f"Wrapper installed into {profile}.\n"
        "Load it in this session:  . $PROFILE\n"
        "Then verify:  Get-Command root | Format-List Name, CommandType\n"
        "(should show CommandType : Function)\n\n"
        "If `. $PROFILE` errors with execution-policy, run once:\n"
        "  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned"
    )
    return InstallResult(True, profile, msg)


# ----- cmd.exe -----
#
# IMPORTANT: prepending our dir to *user* PATH is not enough on Windows --
# system PATH is always evaluated before user PATH, so the `root.exe`
# installed by pip (in C:\Program Files\Python*\Scripts) always wins
# the name lookup. We work around this by setting a doskey macro via
# cmd.exe's AutoRun. Doskey aliases are resolved BEFORE any PATH lookup,
# so they sidestep the system-vs-user-PATH ordering entirely.

DOSKEY_AUTORUN_MARKER = "::root-doskey::"


def _read_autorun() -> Optional[str]:
    """Read the current AutoRun value (or None if absent)."""
    try:
        import winreg  # type: ignore[import-not-found]
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Command Processor",
            0, winreg.KEY_READ,
        ) as k:
            try:
                val, _ = winreg.QueryValueEx(k, "AutoRun")
                return val
            except FileNotFoundError:
                return None
    except (ImportError, OSError):
        return None


def _write_autorun(value: str) -> None:
    import winreg  # type: ignore[import-not-found]
    # Ensure the Command Processor key exists.
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Command Processor"
    ) as k:
        winreg.SetValueEx(k, "AutoRun", 0, winreg.REG_SZ, value)


def _merge_autorun(existing: Optional[str], our_command: str) -> str:
    """Splice our doskey command into an existing AutoRun, idempotently.

    Our command is sandwiched between sentinel comments so a re-install
    can find and replace it. Anything else the user had stays put.

    NB: we deliberately use slice-based replacement instead of re.sub
    here because our replacement contains Windows-style backslash
    paths, and re.sub interprets sequences like \\n as newlines.
    """
    block = f"({our_command}) {DOSKEY_AUTORUN_MARKER}"
    if not existing:
        return block
    if DOSKEY_AUTORUN_MARKER in existing:
        pattern = re.compile(r"\([^)]*\)\s*" + re.escape(DOSKEY_AUTORUN_MARKER))
        m = pattern.search(existing)
        if m:
            return existing[:m.start()] + block + existing[m.end():]
        # Marker present but in unexpected form -- fall through to
        # append to keep things from getting weirder.
    return f"{existing.rstrip().rstrip('&').rstrip()} & {block}"


def install_cmd() -> InstallResult:
    home = Path.home()
    bin_dir = home / ".root" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    target = bin_dir / "root.cmd"
    target.write_text(_wrapper_text("root.cmd"), encoding="utf-8")

    doskey_cmd = f'doskey root="{target}" $*'
    try:
        existing = _read_autorun()
        merged = _merge_autorun(existing, doskey_cmd)
        _write_autorun(merged)
    except (ImportError, OSError) as e:
        return InstallResult(
            True, target,
            f"Wrote {target}.\n"
            f"Could not configure cmd.exe AutoRun automatically ({e}).\n"
            f"Run this in a cmd window as a one-shot fallback:\n"
            f'  reg add "HKCU\\Software\\Microsoft\\Command Processor" '
            f'/v AutoRun /t REG_SZ /d "{doskey_cmd}" /f',
        )

    _broadcast_settings_change()

    lines = [
        f"Wrote {target}.",
        "Registered a doskey AutoRun:  " + doskey_cmd,
        "",
        "Open a NEW cmd.exe window (Win+R -> cmd, or Start menu).",
        "Verify:  doskey /macros        (should show: root=...root.cmd $*)",
        "Then `root` will work in cmd.exe.",
    ]
    return InstallResult(True, target, "\n".join(lines))


# ----- WM_SETTINGCHANGE broadcast (best-effort) -----

def _broadcast_settings_change() -> None:
    """Tell Explorer to re-read env vars / registry-driven settings.

    Best-effort: swallows everything that goes wrong, since the worst
    case is the user just opens a new shell themselves.
    """
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        from ctypes import wintypes

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002

        SendMessageTimeoutW = ctypes.windll.user32.SendMessageTimeoutW
        SendMessageTimeoutW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
            wintypes.LPCWSTR, wintypes.UINT, wintypes.UINT,
            ctypes.POINTER(wintypes.DWORD),
        ]
        result = wintypes.DWORD()
        SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0,
            "Environment", SMTO_ABORTIFHUNG, 5000, ctypes.byref(result),
        )
    except Exception:
        pass


# ----- auto-detect -----

def detect_shell() -> str:
    """Best-effort guess at the user's current shell."""
    if os.environ.get("FISH_VERSION"):
        return "fish"
    if os.environ.get("PSModulePath") and platform.system() == "Windows":
        return "powershell"
    sh = os.environ.get("SHELL", "")
    if "zsh" in sh:
        return "zsh"
    if "bash" in sh:
        return "bash"
    if "fish" in sh:
        return "fish"
    if platform.system() == "Windows":
        return "powershell"
    return "bash"


def install(shell: str) -> InstallResult:
    """Dispatch by shell name."""
    s = shell.lower()
    if s == "auto":
        s = detect_shell()
    if s in ("bash", "zsh"):
        return install_bash_zsh(s)
    if s == "fish":
        return install_fish()
    if s in ("powershell", "pwsh"):
        return install_powershell()
    if s == "cmd":
        return install_cmd()
    return InstallResult(
        False, None,
        f"Unknown shell: {shell!r}. Try one of: bash, zsh, fish, powershell, cmd, auto.",
    )
