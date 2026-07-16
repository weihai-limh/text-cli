# init_config.ps1 - text-cli service configuration initialization
# Copies *.example.json to *.json (does not overwrite existing files)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigDir = Join-Path $ScriptDir "config"

Write-Host "Initializing text-cli service config..."

if (-not (Test-Path $ConfigDir)) {
    Write-Host "[WARN] config directory not found: $ConfigDir"
    exit 0
}

Get-ChildItem -Path $ConfigDir -Filter "*.example.json" | ForEach-Object {
    $target = Join-Path $ConfigDir ($_.Name -replace '\.example\.json$', '.json')
    if (-not (Test-Path $target)) {
        Copy-Item $_.FullName $target
        Write-Host "  [OK] $(Split-Path -Leaf $target)"
    } else {
        Write-Host "  - $(Split-Path -Leaf $target) (exists)"
    }
}

Write-Host ""
Write-Host "Config initialization done. Edit config files before starting."
