@echo off
REM root wrapper for cmd.exe.
REM
REM Save as `root.cmd` somewhere on your PATH that appears BEFORE your
REM Python Scripts directory (otherwise `root.exe` shadows this).
REM Alternative: use a doskey macro via cmd.exe AutoRun.

REM Pass any subcommand straight through.
if not "%~1"=="" (
    python -m root_cli %*
    exit /b %ERRORLEVEL%
)

REM Launch the TUI. Whatever it returns, we then look at the target
REM file -- if it points to a real directory, we cd. This is more
REM forgiving than checking %ERRORLEVEL%, which has bitten us on Windows.
python -m root_cli

set "_target="
for /f "usebackq delims=" %%i in (`python -m root_cli which 2^>nul`) do set "_target=%%i"

if not defined _target exit /b 0
if exist "%_target%\" cd /d "%_target%"
