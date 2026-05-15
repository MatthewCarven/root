# reinstall.ps1 -- rebuild & reinstall `root` from this checkout.
#
# Editable mode (-e): pip drops a tiny shim in Scripts/, and every time
# you run `root` it imports straight from src/root_cli/. So after this
# script runs once, any future edit to the .py files takes effect on
# the next `root` invocation -- no reinstall needed.
#
# Run with:    powershell -ExecutionPolicy Bypass -File .\reinstall.ps1
# or just:     .\reinstall.ps1
#
# Safe to run repeatedly.

$ErrorActionPreference = "Stop"

# Move to the script's directory so this works no matter where you call it from.
Set-Location -Path $PSScriptRoot

Write-Host "[reinstall] Uninstalling any previous root-cli ..." -ForegroundColor Cyan
pip uninstall -y root-cli 2>&1 | Out-Null

Write-Host "[reinstall] Installing editable from $PSScriptRoot ..." -ForegroundColor Cyan
pip install -e . 2>&1 | ForEach-Object { Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Host "[reinstall] pip install failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "[reinstall] Smoke-checking import ..." -ForegroundColor Cyan
python -c "from root_cli import install; assert callable(install.install_cmd); print('  install_cmd OK ->', install.install_cmd)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[reinstall] Import smoke check failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[reinstall] Done. Now run:" -ForegroundColor Green
Write-Host "    root install-shell cmd"
Write-Host ""
Write-Host "From here on, editing the .py files takes effect immediately -- no"
Write-Host "need to re-run this script unless dependencies change in pyproject.toml."
