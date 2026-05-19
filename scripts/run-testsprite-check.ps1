# Verify TestSprite API key and Node version before MCP runs.
$ErrorActionPreference = "Stop"

$nodeVer = (node --version) -replace 'v', ''
$major = [int]($nodeVer.Split('.')[0])
if ($major -lt 22) {
    Write-Error "Node.js 22+ required for TestSprite MCP (found: node --version -> v$nodeVer)"
}

$key = $env:API_KEY
if (-not $key) { $key = $env:TESTSPRITE_API_KEY }
if (-not $key) {
    Write-Error @"
No TestSprite API key found. Set one of:
  `$env:API_KEY = 'your-key'
  `$env:TESTSPRITE_API_KEY = 'your-key'
Or configure API_KEY in Cursor MCP settings (see .cursor/README.md).
"@
}

Write-Host "Node OK (v$nodeVer). API_KEY is set (length $($key.Length))." -ForegroundColor Green
npx -y @testsprite/testsprite-mcp@latest -V
