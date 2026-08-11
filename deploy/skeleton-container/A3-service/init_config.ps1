# init_config.ps1 - text-cli service configuration initialization
# Copies *.example.json to *.json (does not overwrite existing files)
#
# Usage:
#   .\init_config.ps1                 # auto-scan candidate dirs
#   $env:CONFIG_DIR = "D:\path"       # only process specified dir

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($env:CONFIG_DIR) {
    $Candidates = @($env:CONFIG_DIR)
} else {
    $Candidates = @(
        (Join-Path $ScriptDir "config"),
        (Join-Path $ScriptDir "service\config"),
        (Join-Path $ScriptDir "copilot\config")
    )
}

Write-Host "Initializing text-cli config..."

$found = $false
foreach ($D in $Candidates) {
    if (-not (Test-Path $D)) { continue }
    Get-ChildItem -Path $D -Filter "*.example.json" | ForEach-Object {
        $target = Join-Path $D ($_.Name -replace '\.example\.json$', '.json')
        if (-not (Test-Path $target)) {
            Copy-Item $_.FullName $target
            Write-Host "  [OK] $(Split-Path -Leaf $target)"
        } else {
            Write-Host "  - $(Split-Path -Leaf $target) (exists)"
        }
        $found = $true
    }
}

if (-not $found) {
    Write-Host "[WARN] no *.example.json found (config dirs may not be generated yet; run build.py first)"
}

Write-Host ""
Write-Host "Config initialization done. Edit config files before starting."
