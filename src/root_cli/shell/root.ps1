# root function for PowerShell (5.1+ and PowerShell Core).
#
# Install: append to your $PROFILE
#     root init-shell powershell | Out-String | Invoke-Expression
# Or persistently:
#     root init-shell powershell >> $PROFILE
#
# After `root` (no args) we read `root which`; if it returns a real
# directory we Set-Location there. We don't gate on $LASTEXITCODE --
# if the sentinel file points somewhere valid, we cd.

function global:root {
    [CmdletBinding()]
    param([Parameter(ValueFromRemainingArguments = $true)]$Args)

    # Find the real CLI on PATH, bypassing this function.
    $real = Get-Command -Name root.exe -CommandType Application -ErrorAction SilentlyContinue
    if (-not $real) {
        $real = Get-Command -Name root -CommandType Application -ErrorAction SilentlyContinue
    }
    if (-not $real) {
        Write-Error "root: CLI not found on PATH. Install: pip install root-cli"
        return
    }

    if ($Args -and $Args.Count -gt 0) {
        & $real.Source @Args
        return
    }

    & $real.Source

    $target = (& $real.Source which 2>$null)
    if ($target) {
        $target = $target.Trim()
        if (Test-Path -LiteralPath $target -PathType Container) {
            Set-Location -LiteralPath $target
        }
    }
}
