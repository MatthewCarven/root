"""Open a file with the OS default handler, non-blocking.

Deliberately handler-based (Explorer/Finder/xdg associations) rather
than hardcoding application paths, so root stays portable — including
if it's ever embedded on a mounted disk image.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


def launch_path(path: Path) -> Optional[str]:
    """Launch *path* with the platform's default opener.

    Returns None on success, or a short error message. Never raises,
    never blocks on the launched program.
    """
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606 - the whole point
        elif sys.platform == "darwin":
            subprocess.Popen(
                ["open", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["xdg-open", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except OSError as exc:
        return str(exc)
    return None
