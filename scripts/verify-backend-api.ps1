# Validates backend test plan scenarios against running Flask (local substitute for TestSprite cloud).
$ErrorActionPreference = "Stop"
$Base = "http://127.0.0.1:5000/api/v1"
$Email = "testsprite@example.com"
$Pass = "TestSprite1!"
$results = @()
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

function Record($id, $title, $ok, $detail) {
    $script:results += [pscustomobject]@{ id = $id; title = $title; passed = $ok; detail = $detail }
}

try {
    $h = Invoke-RestMethod "$Base/health"
    Record "TC101" "Health endpoint" ($h.status -ne $null) "status=$($h.status)"
} catch { Record "TC101" "Health endpoint" $false $_.Exception.Message }

try {
    $t = Invoke-RestMethod "$Base/tools"
    Record "TC102" "Tools endpoint" ($t.available.python -eq $true) "python=$($t.available.python)"
} catch { Record "TC102" "Tools endpoint" $false $_.Exception.Message }

$csrf = (Invoke-RestMethod "$Base/csrf-token" -WebSession $session).csrf_token
$csrfHeaders = @{ "X-CSRFToken" = $csrf }

try {
    $a = Invoke-RestMethod -Method Post -Uri "$Base/analyze" -ContentType "application/json" `
        -WebSession $session -Headers $csrfHeaders `
        -Body (@{ code = "print('hello')"; language = "python" } | ConvertTo-Json)
    $stdout = $a.execution.stdout
    Record "TC103" "Analyze valid Python" ($stdout -match "hello") "stdout=$stdout"
} catch { Record "TC103" "Analyze valid Python" $false $_.Exception.Message }

try {
    Invoke-RestMethod -Method Post -Uri "$Base/analyze" -ContentType "application/json" `
        -WebSession $session -Headers $csrfHeaders `
        -Body (@{ code = "   "; language = "python" } | ConvertTo-Json) | Out-Null
    Record "TC104" "Analyze rejects empty" $false "expected 400"
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    Record "TC104" "Analyze rejects empty" ($code -eq 400) "http=$code"
}

try {
    Invoke-RestMethod "$Base/history" | Out-Null
    Record "TC105" "History requires auth" $false "expected 401"
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    Record "TC105" "History requires auth" ($code -eq 401) "http=$code"
}

try {
    $login = Invoke-RestMethod -Method Post -Uri "$Base/auth/login" -ContentType "application/json" `
        -WebSession $session -Headers $csrfHeaders `
        -Body (@{ email = $Email; password = $Pass } | ConvertTo-Json)
    Record "TC106" "Login returns token" ($null -ne $login.access_token) "ok=$($login.ok)"
} catch { Record "TC106" "Login returns token" $false $_.Exception.Message }

$outDir = Join-Path (Split-Path -Parent $PSScriptRoot) "testsprite_tests\tmp"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$payload = @{
    pass = "backend"
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    summary = @{
        total = $results.Count
        passed = @($results | Where-Object passed).Count
        failed = @($results | Where-Object { -not $_.passed }).Count
    }
    tests = $results
}
$payload | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $outDir "test_results_backend.json") -Encoding UTF8

$results | Format-Table -AutoSize
$failed = @($results | Where-Object { -not $_.passed }).Count
if ($failed -gt 0) { exit 1 }
