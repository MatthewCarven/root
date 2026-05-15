"""Tests for the install-shell logic."""
from __future__ import annotations

from pathlib import Path

import pytest

from root_cli.install import (
    MARKER_BEGIN,
    MARKER_END,
    _idempotent_replace,
    detect_shell,
    install,
    install_bash_zsh,
    install_fish,
)


class TestIdempotentReplace:
    def test_inserts_when_file_is_empty(self):
        out = _idempotent_replace("", "echo hello")
        assert MARKER_BEGIN in out
        assert MARKER_END in out
        assert "echo hello" in out

    def test_appends_to_existing_content(self):
        existing = "# my zshrc\nalias ll='ls -la'\n"
        out = _idempotent_replace(existing, "echo hello")
        assert out.startswith(existing)
        assert "echo hello" in out
        assert MARKER_BEGIN in out

    def test_replaces_in_place_when_already_installed(self):
        # First run installs.
        v1 = _idempotent_replace("# header\n", "OLD WRAPPER")
        # Second run with a new snippet must REPLACE, not duplicate.
        v2 = _idempotent_replace(v1, "NEW WRAPPER")
        assert v2.count(MARKER_BEGIN) == 1
        assert v2.count(MARKER_END) == 1
        assert "NEW WRAPPER" in v2
        assert "OLD WRAPPER" not in v2

    def test_preserves_surrounding_content_on_replace(self):
        existing = (
            "# preamble\nexport FOO=bar\n"
            f"{MARKER_BEGIN}\nOLD\n{MARKER_END}\n"
            "# postamble\nexport BAZ=qux\n"
        )
        out = _idempotent_replace(existing, "NEW")
        assert "export FOO=bar" in out
        assert "export BAZ=qux" in out
        assert "NEW" in out
        assert "OLD" not in out


class TestBashZshInstall:
    def test_installs_into_existing_rc(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        rc = tmp_path / ".zshrc"
        rc.write_text("# existing content\n", encoding="utf-8")
        result = install_bash_zsh("zsh")
        assert result.success
        assert result.target == rc
        content = rc.read_text(encoding="utf-8")
        assert "# existing content" in content
        assert MARKER_BEGIN in content
        assert "command root" in content  # the wrapper body

    def test_creates_rc_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = install_bash_zsh("bash")
        assert result.success
        assert result.target == tmp_path / ".bashrc"
        assert result.target.exists()

    def test_re_install_does_not_duplicate(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        install_bash_zsh("bash")
        install_bash_zsh("bash")
        rc = tmp_path / ".bashrc"
        text = rc.read_text(encoding="utf-8")
        assert text.count(MARKER_BEGIN) == 1
        assert text.count(MARKER_END) == 1


class TestFishInstall:
    def test_writes_function_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = install_fish()
        assert result.success
        funcdir = tmp_path / ".config" / "fish" / "functions"
        assert result.target == funcdir / "root.fish"
        assert result.target.exists()
        # Fish wrappers don't use markers (whole file is ours).
        assert "function root" in result.target.read_text(encoding="utf-8")

    def test_honors_xdg_config_home(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        xdg = tmp_path / "xdg"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        result = install_fish()
        assert result.target == xdg / "fish" / "functions" / "root.fish"
        assert result.target.exists()


class TestDispatch:
    def test_unknown_shell_returns_failure(self):
        result = install("plan9-rc")
        assert not result.success
        assert "Unknown shell" in result.message

    def test_auto_returns_some_known_shell(self):
        # detect_shell always returns one of the supported names.
        s = detect_shell()
        assert s in {"bash", "zsh", "fish", "powershell", "cmd"}


# ---- doskey AutoRun merging (cmd.exe) ----

from root_cli.install import _merge_autorun, DOSKEY_AUTORUN_MARKER


class TestAutoRunMerge:
    def test_inserts_when_no_existing_autorun(self):
        out = _merge_autorun(None, 'doskey root="C:\\foo" $*')
        assert "doskey root=" in out
        assert DOSKEY_AUTORUN_MARKER in out

    def test_inserts_when_empty_autorun(self):
        out = _merge_autorun("", 'doskey root="C:\\foo" $*')
        assert DOSKEY_AUTORUN_MARKER in out

    def test_appends_when_user_already_has_autorun(self):
        existing = "@echo Some user prologue"
        out = _merge_autorun(existing, 'doskey root="C:\\foo" $*')
        assert existing in out
        assert DOSKEY_AUTORUN_MARKER in out
        # The two should be joined by `&`, cmd.exe's command separator.
        assert "&" in out

    def test_idempotent_replace_when_already_installed(self):
        first = _merge_autorun(None, 'doskey root="C:\\old" $*')
        second = _merge_autorun(first, 'doskey root="C:\\new" $*')
        # Marker appears exactly once -- no duplication.
        assert second.count(DOSKEY_AUTORUN_MARKER) == 1
        assert "C:\\new" in second
        assert "C:\\old" not in second

    def test_preserves_user_prologue_on_replace(self):
        existing = (
            'echo HELLO & '
            '(doskey root="C:\\old" $*) ' + DOSKEY_AUTORUN_MARKER
            + " & echo BYE"
        )
        out = _merge_autorun(existing, 'doskey root="C:\\new" $*')
        assert "echo HELLO" in out
        assert "echo BYE" in out
        assert "C:\\new" in out
        assert "C:\\old" not in out
