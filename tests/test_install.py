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


# ----- uninstall -----

from root_cli.install import (
    _remove_marker_block,
    _unmerge_autorun,
    install_bash_zsh,
    uninstall,
    uninstall_bash_zsh,
    uninstall_fish,
)


class TestRemoveMarkerBlock:
    def test_not_found_returns_unchanged(self):
        out, found = _remove_marker_block("some content\n")
        assert not found
        assert out == "some content\n"

    def test_roundtrip_restores_original(self):
        original = "# my rc\nalias ll='ls -l'\n"
        installed = _idempotent_replace(original, "function root() { :; }")
        out, found = _remove_marker_block(installed)
        assert found
        assert "root shell wrapper" not in out
        assert "alias ll" in out
        assert "\n\n\n" not in out

    def test_block_only_file_becomes_empty(self):
        installed = _idempotent_replace("", "function root() { :; }")
        out, found = _remove_marker_block(installed)
        assert found
        assert out == ""


class TestUninstallBashZsh:
    def test_removes_block_preserving_content(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        rc = tmp_path / ".bashrc"
        rc.write_text("export FOO=bar\n", encoding="utf-8")
        install_bash_zsh("bash")
        assert MARKER_BEGIN in rc.read_text(encoding="utf-8")
        res = uninstall_bash_zsh("bash")
        assert res.success
        text = rc.read_text(encoding="utf-8")
        assert MARKER_BEGIN not in text
        assert "export FOO=bar" in text

    def test_nothing_installed_is_a_safe_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        rc = tmp_path / ".bashrc"
        rc.write_text("export FOO=bar\n", encoding="utf-8")
        res = uninstall_bash_zsh("bash")
        assert res.success
        assert "nothing to do" in res.message
        assert rc.read_text(encoding="utf-8") == "export FOO=bar\n"

    def test_missing_rc_files_is_a_safe_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        res = uninstall_bash_zsh("zsh")
        assert res.success
        assert "nothing to do" in res.message

    def test_removes_from_all_rc_files_that_have_it(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        for name in (".bashrc", ".profile"):
            f = tmp_path / name
            f.write_text(
                _idempotent_replace("# rc\n", "function root() { :; }"),
                encoding="utf-8",
            )
        res = uninstall_bash_zsh("bash")
        assert res.success
        for name in (".bashrc", ".profile"):
            assert MARKER_BEGIN not in (tmp_path / name).read_text(encoding="utf-8")


class TestUninstallFish:
    def test_removes_function_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        target = tmp_path / ".config" / "fish" / "functions" / "root.fish"
        target.parent.mkdir(parents=True)
        target.write_text("function root; end\n", encoding="utf-8")
        res = uninstall_fish()
        assert res.success
        assert not target.exists()

    def test_honors_xdg_config_home(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        xdg = tmp_path / "xdg"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        target = xdg / "fish" / "functions" / "root.fish"
        target.parent.mkdir(parents=True)
        target.write_text("function root; end\n", encoding="utf-8")
        res = uninstall_fish()
        assert res.success
        assert not target.exists()

    def test_missing_file_is_a_safe_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        res = uninstall_fish()
        assert res.success
        assert "nothing to do" in res.message


class TestUnmergeAutorun:
    def test_no_marker_reports_not_found(self):
        out, found = _unmerge_autorun("echo HELLO")
        assert not found
        assert out == "echo HELLO"

    def test_none_reports_not_found(self):
        out, found = _unmerge_autorun(None)
        assert not found
        assert out == ""

    def test_ours_only_becomes_empty(self):
        existing = _merge_autorun(None, 'doskey root="C:\\x" $*')
        out, found = _unmerge_autorun(existing)
        assert found
        assert out == ""

    def test_preserves_user_prologue_and_epilogue(self):
        existing = (
            "echo HELLO & "
            '(doskey root="C:\\x" $*) ' + DOSKEY_AUTORUN_MARKER
            + " & echo BYE"
        )
        out, found = _unmerge_autorun(existing)
        assert found
        assert "echo HELLO" in out
        assert "echo BYE" in out
        assert DOSKEY_AUTORUN_MARKER not in out
        assert not out.startswith("&")
        assert not out.endswith("&")
        assert "& &" not in out

    def test_removes_dangling_trailing_ampersand(self):
        existing = _merge_autorun("echo HELLO", 'doskey root="C:\\x" $*')
        out, found = _unmerge_autorun(existing)
        assert found
        assert out == "echo HELLO"


class TestUninstallDispatch:
    def test_unknown_shell_returns_failure(self):
        res = uninstall("tcsh")
        assert not res.success
        assert "Unknown shell" in res.message


# ---------------------------------------------------------------------------
# PowerShell: both editions, every host profile, legacy unmarked copies
# ---------------------------------------------------------------------------

import subprocess

from root_cli import install as install_mod
from root_cli.install import _wrapper_text, install_powershell, uninstall_powershell


def _legacy_wrapper() -> str:
    """What `root init-shell powershell >> $PROFILE` appended by hand."""
    return _wrapper_text("root.ps1")


def _marked_wrapper() -> str:
    return _idempotent_replace("", _wrapper_text("root.ps1"))


@pytest.fixture
def ps_home(tmp_path, monkeypatch):
    """Fake home with no PowerShell on PATH: uninstall falls back to the
    standard Documents\\PowerShell + Documents\\WindowsPowerShell dirs."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(install_mod.shutil, "which", lambda _name: None)
    return tmp_path


def _profile(home: Path, edition: str, name: str = "Microsoft.PowerShell_profile.ps1") -> Path:
    path = home / "Documents" / edition / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class TestUninstallPowerShell:
    def test_removes_from_both_editions(self, ps_home):
        # The reported bug: uninstall only looked at pwsh 7's $PROFILE,
        # so a wrapper in Windows PowerShell 5.1's profile survived.
        ps7 = _profile(ps_home, "PowerShell")
        ps51 = _profile(ps_home, "WindowsPowerShell")
        ps7.write_text(_marked_wrapper(), encoding="utf-8")
        ps51.write_text(_marked_wrapper(), encoding="utf-8")
        res = uninstall_powershell()
        assert res.success
        assert ps7.read_text(encoding="utf-8") == ""
        assert ps51.read_text(encoding="utf-8") == ""
        assert str(ps7) in res.message and str(ps51) in res.message

    def test_removes_legacy_copy_and_marked_block_together(self, ps_home):
        # Matthew's real 5.1 profile: a hand-appended copy, then the
        # marked block install-shell later added beneath it.
        ps51 = _profile(ps_home, "WindowsPowerShell")
        ps51.write_text(_legacy_wrapper() + "\n" + _marked_wrapper(), encoding="utf-8")
        uninstall_powershell()
        assert ps51.read_text(encoding="utf-8") == ""

    def test_preserves_user_content(self, ps_home):
        ps7 = _profile(ps_home, "PowerShell")
        ps7.write_text(
            "Set-Alias ll Get-ChildItem\n\n" + _legacy_wrapper()
            + "\n" + _marked_wrapper() + "\n$env:EDITOR = 'code'\n",
            encoding="utf-8",
        )
        uninstall_powershell()
        text = ps7.read_text(encoding="utf-8")
        assert "Set-Alias ll Get-ChildItem" in text
        assert "$env:EDITOR = 'code'" in text
        assert "function global:root" not in text
        assert MARKER_BEGIN not in text

    def test_edited_copy_is_left_alone_and_reported(self, ps_home):
        ps7 = _profile(ps_home, "PowerShell")
        edited = _legacy_wrapper().replace("Set-Location", "Push-Location")
        ps7.write_text(edited, encoding="utf-8")
        res = uninstall_powershell()
        assert ps7.read_text(encoding="utf-8") == edited  # untouched
        assert "still defines a `root` function" in res.message
        assert str(ps7) in res.message

    def test_sweeps_every_host_profile(self, ps_home):
        names = ["profile.ps1", "Microsoft.VSCode_profile.ps1",
                 "Microsoft.PowerShellISE_profile.ps1"]
        paths = [_profile(ps_home, "WindowsPowerShell", n) for n in names]
        for p in paths:
            p.write_text(_marked_wrapper(), encoding="utf-8")
        uninstall_powershell()
        for p in paths:
            assert p.read_text(encoding="utf-8") == ""

    def test_utf16_profile_stays_utf16(self, ps_home):
        # Windows PowerShell 5.1's `>>` writes UTF-16 LE with a BOM.
        ps51 = _profile(ps_home, "WindowsPowerShell")
        ps51.write_text("Set-Alias ll Get-ChildItem\n\n" + _legacy_wrapper(), encoding="utf-16")
        uninstall_powershell()
        raw = ps51.read_bytes()
        assert raw.startswith(b"\xff\xfe")
        text = raw.decode("utf-16")
        assert "Set-Alias ll Get-ChildItem" in text
        assert "function global:root" not in text

    def test_asks_powershell_where_profiles_live(self, tmp_path, monkeypatch):
        # A OneDrive-redirected Documents folder is only knowable by
        # asking PowerShell; the fallback ~/Documents would miss it.
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        onedrive = tmp_path / "OneDrive" / "Documents" / "PowerShell"
        onedrive.mkdir(parents=True)
        prof = onedrive / "Microsoft.PowerShell_profile.ps1"
        prof.write_text(_marked_wrapper(), encoding="utf-8")
        monkeypatch.setattr(
            install_mod.shutil, "which",
            lambda name: "pwsh.exe" if name == "pwsh" else None,
        )
        monkeypatch.setattr(
            install_mod.subprocess, "run",
            lambda *a, **k: subprocess.CompletedProcess(
                a[0], 0, stdout=str(onedrive / "profile.ps1") + "\n", stderr=""
            ),
        )
        res = uninstall_powershell()
        assert prof.read_text(encoding="utf-8") == ""
        assert str(prof) in res.message

    def test_nothing_installed_is_a_safe_noop(self, ps_home):
        ps7 = _profile(ps_home, "PowerShell")
        ps7.write_text("Set-Alias ll Get-ChildItem\n", encoding="utf-8")
        res = uninstall_powershell()
        assert res.success
        assert "nothing to do" in res.message
        assert ps7.read_text(encoding="utf-8") == "Set-Alias ll Get-ChildItem\n"


class TestInstallPowerShell:
    def test_replaces_legacy_copy_instead_of_duplicating(self, tmp_path, monkeypatch):
        prof = tmp_path / "Microsoft.PowerShell_profile.ps1"
        prof.write_text("Set-Alias ll Get-ChildItem\n\n" + _legacy_wrapper(), encoding="utf-8")
        monkeypatch.setattr(install_mod.shutil, "which", lambda _name: "pwsh.exe")
        monkeypatch.setattr(
            install_mod.subprocess, "run",
            lambda *a, **k: subprocess.CompletedProcess(
                a[0], 0, stdout=str(prof) + "\n", stderr=""
            ),
        )
        res = install_powershell()
        assert res.success
        text = prof.read_text(encoding="utf-8")
        assert text.count("function global:root") == 1
        assert MARKER_BEGIN in text
        assert "Set-Alias ll Get-ChildItem" in text


# ---------------------------------------------------------------------------
# PowerShell install: every installed edition gets the wrapper
# ---------------------------------------------------------------------------


def _fake_editions(monkeypatch, profiles):
    """Fake which editions are on PATH and what each says $PROFILE is.

    ``profiles`` maps exe name -> profile path, or None for an edition
    that is on PATH but fails the $PROFILE query.
    """
    monkeypatch.setattr(
        install_mod.shutil, "which",
        lambda name: f"{name}.exe" if name in profiles else None,
    )

    def run(args, **_kw):
        path = profiles[args[0][: -len(".exe")]]
        if path is None:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="boom")
        return subprocess.CompletedProcess(args, 0, stdout=f"{path}\n", stderr="")

    monkeypatch.setattr(install_mod.subprocess, "run", run)


def _both_editions(home: Path):
    docs = home / "Documents"
    return (
        docs / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
        docs / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
    )


class TestInstallPowerShellEditions:
    def test_installs_into_both_editions(self, tmp_path, monkeypatch):
        ps7, ps51 = _both_editions(tmp_path)  # neither dir exists yet
        _fake_editions(monkeypatch, {"pwsh": ps7, "powershell": ps51})
        res = install_powershell()
        assert res.success
        for p in (ps7, ps51):
            assert p.read_text(encoding="utf-8").count(MARKER_BEGIN) == 1
            assert str(p) in res.message

    def test_reinstall_does_not_duplicate_in_either(self, tmp_path, monkeypatch):
        ps7, ps51 = _both_editions(tmp_path)
        _fake_editions(monkeypatch, {"pwsh": ps7, "powershell": ps51})
        install_powershell()
        install_powershell()
        for p in (ps7, ps51):
            assert p.read_text(encoding="utf-8").count("function global:root") == 1

    def test_pwsh_only_installs_there(self, tmp_path, monkeypatch):
        # Linux / macOS: there is no Windows PowerShell.
        prof = tmp_path / ".config" / "powershell" / "Microsoft.PowerShell_profile.ps1"
        _fake_editions(monkeypatch, {"pwsh": prof})
        res = install_powershell()
        assert res.success
        assert MARKER_BEGIN in prof.read_text(encoding="utf-8")

    def test_one_edition_failing_still_installs_the_other(self, tmp_path, monkeypatch):
        ps7, _ = _both_editions(tmp_path)
        _fake_editions(monkeypatch, {"pwsh": ps7, "powershell": None})
        res = install_powershell()
        assert res.success
        assert MARKER_BEGIN in ps7.read_text(encoding="utf-8")
        assert "Skipped powershell" in res.message

    def test_every_edition_failing_is_a_failure(self, tmp_path, monkeypatch):
        _fake_editions(monkeypatch, {"pwsh": None, "powershell": None})
        res = install_powershell()
        assert not res.success
        assert "Could not determine $PROFILE" in res.message

    def test_no_powershell_is_a_failure(self, monkeypatch):
        _fake_editions(monkeypatch, {})
        res = install_powershell()
        assert not res.success
        assert "isn't on PATH" in res.message

    def test_roundtrip_with_uninstall(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        ps7, ps51 = _both_editions(tmp_path)
        ps51.parent.mkdir(parents=True)
        ps51.write_text("Set-Alias ll Get-ChildItem\n", encoding="utf-8")
        _fake_editions(monkeypatch, {"pwsh": ps7, "powershell": ps51})
        install_powershell()
        uninstall_powershell()
        assert ps7.read_text(encoding="utf-8") == ""
        text = ps51.read_text(encoding="utf-8")
        assert "Set-Alias ll Get-ChildItem" in text
        assert "function global:root" not in text

    def test_wrapper_is_ascii(self):
        # Install writes profiles without a BOM, and Windows PowerShell
        # 5.1 reads BOM-less files in the ANSI code page: any non-ASCII
        # character in the wrapper would load as mojibake there.
        assert _wrapper_text("root.ps1").isascii()
