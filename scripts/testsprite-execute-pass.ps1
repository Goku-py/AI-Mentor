# Run TestSprite cloud test execution for frontend or backend pass.
# Requires: API_KEY or TESTSPRITE_API_KEY, servers running, committed config.
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("frontend", "backend")]
    [string]$Pass
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& "$PSScriptRoot\run-testsprite-check.ps1"

$key = if ($env:API_KEY) { $env:API_KEY } else { $env:TESTSPRITE_API_KEY }
$env:API_KEY = $key

$example = Join-Path $Root "testsprite_tests\tmp\config.$Pass.example.json"
$config = Join-Path $Root "testsprite_tests\tmp\config.json"
if (-not (Test-Path $example)) {
    Write-Error "Missing $example"
}
Copy-Item -Force $example $config
Write-Host "Using config for $Pass pass -> testsprite_tests/tmp/config.json" -ForegroundColor Cyan

Write-Host "Running TestSprite generateCodeAndExecute (cloud)..." -ForegroundColor Cyan
npx -y @testsprite/testsprite-mcp@latest generateCodeAndExecute
