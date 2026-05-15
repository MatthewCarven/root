"""Cross-platform config directory resolution.

We use platformdirs so the right place is chosen on each OS:

- Linux:   ~/.config/root/
- macOS:   ~/Library/Application Support/root/
- Windows: %APPDATA%\\root\\
"""
from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "root"


def config_dir() -> Path:
    """Return the directory where root keeps its config, bookmarks, history.

    Honors ``$ROOT_CONFIG_DIR`` for tests and power users.
    """
    override = os.environ.get("ROOT_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path(user_config_dir(APP_NAME, appauthor=False))


def ensure_config_dir() -> Path:
    path = config_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.toml"


def bookmarks_path() -> Path:
    return config_dir() / "bookmarks.toml"


def history_path() -> Path:
    return config_dir() / "history.json"


def target_path() -> Path:
    """Sentinel file the shell wrapper reads to know where to cd.

    Lives next to config so the wrapper can find it without env vars.
    """
    return config_dir() / "last_target"
