# AI Code Mentor - Automated Setup Script (Windows PowerShell)
# Run: .\setup.ps1

Write-Host "
 ╔════════════════════════════════════════════════════════════════╗
 ║          AI Code Mentor - Setup Script                        ║
 ║          This script will set up the project for you.        ║
 ╚════════════════════════════════════════════════════════════════╝
" -ForegroundColor Cyan

# =============================================================================
# 1. CHECK PREREQUISITES
# =============================================================================

Write-Host "`n[1/6] Checking system prerequisites..." -ForegroundColor Yellow

$prerequisites = @{
    'Python' = @{ cmd = 'python'; arg = '--version' }
    'Node.js' = @{ cmd = 'node'; arg = '--version' }
    'npm' = @{ cmd = 'npm'; arg = '--version' }
}

$missing = @()
foreach ($tool in $prerequisites.GetEnumerator()) {
    try {
        $output = & $tool.Value.cmd $tool.Value.arg 2>&1
        Write-Host "  ✓ $($tool.Name) is installed" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ $($tool.Name) NOT FOUND" -ForegroundColor Red
        $missing += $tool.Name
    }
}

# Optional tools
Write-Host "`n  Optional tools (static analysis will work without these):" -ForegroundColor Gray
$optional = @{
    'GCC (C/C++)' = @{ cmd = 'gcc'; arg = '--version' }
    'Java (javac)' = @{ cmd = 'javac'; arg = '-version' }
}

foreach ($tool in $optional.GetEnumerator()) {
    try {
        $output = & $tool.Value.cmd $tool.Value.arg 2>&1
        Write-Host "  ✓ $($tool.Name) is installed" -ForegroundColor Green
    } catch {
        Write-Host "  ○ $($tool.Name) NOT FOUND (optional)" -ForegroundColor Gray
    }
}

if ($missing.Count -gt 0) {
    Write-Host "`n❌ Missing required tools: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "`nPlease install the missing tools and try again." -ForegroundColor Red
    Write-Host "See README.md for installation links." -ForegroundColor Gray
    exit 1
}

# =============================================================================
# 2. SETUP ENVIRONMENT FILE
# =============================================================================

Write-Host "`n[2/6] Setting up environment file..." -ForegroundColor Yellow

if (Test-Path '.env') {
    Write-Host "  ✓ .env file already exists (skipping)" -ForegroundColor Green
} else {
    if (Test-Path '.env.example') {
        Copy-Item '.env.example' '.env'
        Write-Host "  ✓ Created .env from .env.example" -ForegroundColor Green
        Write-Host "  ⚠ IMPORTANT: Edit .env and add your GEMINI_API_KEY" -ForegroundColor Yellow
        Write-Host "     Get key from: https://makersuite.google.com/app/apikey" -ForegroundColor Gray
    } else {
        Write-Host "  ✗ .env.example not found!" -ForegroundColor Red
        exit 1
    }
}

# =============================================================================
# 3. CREATE PYTHON VIRTUAL ENVIRONMENT
# =============================================================================

Write-Host "`n[3/6] Setting up Python virtual environment..." -ForegroundColor Yellow

if (Test-Path 'venv') {
    Write-Host "  ✓ Virtual environment already exists (skipping)" -ForegroundColor Green
} else {
    Write-Host "  Creating virtual environment..." -ForegroundColor Gray
    python -m venv venv
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Virtual environment created" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

# Activate venv
Write-Host "  Activating virtual environment..." -ForegroundColor Gray
& ".\venv\Scripts\Activate.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ⚠ Failed to activate venv. Try manually:" -ForegroundColor Yellow
    Write-Host "     .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
}

# =============================================================================
# 4. INSTALL PYTHON DEPENDENCIES
# =============================================================================

Write-Host "`n[4/6] Installing Python dependencies..." -ForegroundColor Yellow

if (Test-Path 'requirements.txt') {
    Write-Host "  Installing from requirements.txt..." -ForegroundColor Gray
    pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Python dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Failed to install Python dependencies" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  ✗ requirements.txt not found!" -ForegroundColor Red
    exit 1
}

# =============================================================================
# 5. INSTALL NODE DEPENDENCIES
# =============================================================================

Write-Host "`n[5/6] Installing Node.js dependencies..." -ForegroundColor Yellow

if (Test-Path 'package.json') {
    Write-Host "  Installing from package.json..." -ForegroundColor Gray
    npm install
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Node dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Failed to install Node dependencies" -ForegroundColor Red
        Write-Host "  Try: npm cache clean --force && npm install" -ForegroundColor Gray
        exit 1
    }
} else {
    Write-Host "  ✗ package.json not found!" -ForegroundColor Red
    exit 1
}

# =============================================================================
# 6. FINAL CHECKS & SUMMARY
# =============================================================================

Write-Host "`n[6/6] Final configuration check..." -ForegroundColor Yellow

$config = @{
    'Python virtual env' = if (Test-Path 'venv') { 'venv' } else { 'NOT FOUND' }
    'Python dependencies' = if (Test-Path 'venv\Lib\site-packages\flask') { 'Installed' } else { 'NOT FOUND' }
    'Node modules' = if (Test-Path 'node_modules') { 'Installed' } else { 'NOT FOUND' }
    '.env file' = if (Test-Path '.env') { 'Found' } else { 'NOT FOUND' }
}

foreach ($item in $config.GetEnumerator()) {
    $status = if ($item.Value -like 'NOT FOUND*') { 
        @{ color = 'Red'; symbol = '✗' } 
    } else { 
        @{ color = 'Green'; symbol = '✓' } 
    }
    Write-Host "  $($status.symbol) $($item.Name): $($item.Value)" -ForegroundColor $status.color
}

# =============================================================================
# SETUP COMPLETE
# =============================================================================

Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                 ✓ SETUP COMPLETE!                              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Green

Write-Host "`nNext steps:

  1. Edit .env file and add your GEMINI_API_KEY
     Get key from: https://makersuite.google.com/app/apikey

  2. Start the Flask backend (in this terminal):
     python app.py

  3. Start the Vite frontend (in a new terminal):
     npm run dev

  4. Open browser to: http://localhost:5173/

For help, see: README.md
" -ForegroundColor Cyan

Write-Host "Happy coding! 🚀" -ForegroundColor Green
