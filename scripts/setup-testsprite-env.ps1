# Prepare local dev for TestSprite full-stack testing.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$TestEmail = "testsprite@example.com"
$TestPassword = "TestSprite1!"

Write-Host "=== AI Mentor - TestSprite environment setup ===" -ForegroundColor Cyan

# Copy PRD into TestSprite upload folder
$prdSrc = Join-Path $Root "docs\testsprite-prd.md"
$prdDstDir = Join-Path $Root "testsprite_tests\tmp\prd_files"
New-Item -ItemType Directory -Force -Path $prdDstDir | Out-Null
Copy-Item -Force $prdSrc (Join-Path $prdDstDir "testsprite-prd.md")
Write-Host "PRD copied to testsprite_tests/tmp/prd_files/" -ForegroundColor Green

# Health checks
function Test-Url($url) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

$backendOk = Test-Url "http://127.0.0.1:5000/api/v1/health"
$frontendOk = Test-Url "http://127.0.0.1:5173/"

if (-not $backendOk) {
    Write-Host "Backend not reachable at :5000 - start: python app.py" -ForegroundColor Yellow
}
if (-not $frontendOk) {
    Write-Host "Frontend not reachable at :5173 - start: npm run dev" -ForegroundColor Yellow
}

if ($backendOk) {
    $body = @{ email = $TestEmail; password = $TestPassword } | ConvertTo-Json
    try {
        $reg = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/auth/register" `
            -ContentType "application/json" -Body $body
        Write-Host "Registered test user: $TestEmail" -ForegroundColor Green
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 409) {
            Write-Host "Test user already exists: $TestEmail" -ForegroundColor Green
        } else {
            Write-Host "Register failed (may need login only): $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "TestSprite portal credentials:" -ForegroundColor Cyan
Write-Host "  Email:    $TestEmail"
Write-Host "  Password: $TestPassword"
Write-Host ""
Write-Host "Next: Enable TestSprite MCP in Cursor, set API_KEY, then prompt:" -ForegroundColor Cyan
Write-Host '  Help me test this project with TestSprite full-stack.'
