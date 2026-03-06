#!/bin/bash

# AI Code Mentor - Automated Setup Script (macOS/Linux Bash)
# Run: bash setup.sh

cat << 'EOF'

 ╔════════════════════════════════════════════════════════════════╗
 ║          AI Code Mentor - Setup Script                        ║
 ║          This script will set up the project for you.        ║
 ╚════════════════════════════════════════════════════════════════╝

EOF

# =============================================================================
# 1. CHECK PREREQUISITES
# =============================================================================

echo ""
echo -e "\033[33m[1/6] Checking system prerequisites...\033[0m"

missing=()

for cmd in python3 node npm; do
    if command -v $cmd &> /dev/null; then
        version=$($cmd --version 2>&1)
        echo -e "  \033[32m✓\033[0m $cmd is installed"
    else
        echo -e "  \033[31m✗\033[0m $cmd NOT FOUND"
        missing+=($cmd)
    fi
done

# Optional tools
echo ""
echo -e "\033[90m  Optional tools (static analysis will work without these):\033[0m"

for cmd in gcc g++ javac java; do
    if command -v $cmd &> /dev/null; then
        version=$($cmd --version 2>&1 | head -n1)
        echo -e "  \033[32m✓\033[0m $cmd is installed"
    else
        echo -e "  \033[90m○\033[0m $cmd NOT FOUND (optional)\033[0m"
    fi
done

if [ ${#missing[@]} -gt 0 ]; then
    echo ""
    echo -e "\033[31m❌ Missing required tools: ${missing[*]}\033[0m"
    echo -e "\033[31mPlease install the missing tools and try again.\033[0m"
    echo -e "\033[90mSee README.md for installation instructions.\033[0m"
    exit 1
fi

# =============================================================================
# 2. SETUP ENVIRONMENT FILE
# =============================================================================

echo ""
echo -e "\033[33m[2/6] Setting up environment file...\033[0m"

if [ -f '.env' ]; then
    echo -e "  \033[32m✓\033[0m .env file already exists (skipping)"
else
    if [ -f '.env.example' ]; then
        cp .env.example .env
        echo -e "  \033[32m✓\033[0m Created .env from .env.example"
        echo -e "  \033[33m⚠ IMPORTANT: Edit .env and add your GEMINI_API_KEY\033[0m"
        echo -e "     Get key from: https://makersuite.google.com/app/apikey"
    else
        echo -e "  \033[31m✗\033[0m .env.example not found!"
        exit 1
    fi
fi

# =============================================================================
# 3. CREATE PYTHON VIRTUAL ENVIRONMENT
# =============================================================================

echo ""
echo -e "\033[33m[3/6] Setting up Python virtual environment...\033[0m"

if [ -d 'venv' ]; then
    echo -e "  \033[32m✓\033[0m Virtual environment already exists (skipping)"
else
    echo -e "  \033[90mCreating virtual environment...\033[0m"
    python3 -m venv venv
    if [ $? -eq 0 ]; then
        echo -e "  \033[32m✓\033[0m Virtual environment created"
    else
        echo -e "  \033[31m✗\033[0m Failed to create virtual environment"
        exit 1
    fi
fi

# Activate venv
echo -e "  \033[90mActivating virtual environment...\033[0m"
source venv/bin/activate

# =============================================================================
# 4. INSTALL PYTHON DEPENDENCIES
# =============================================================================

echo ""
echo -e "\033[33m[4/6] Installing Python dependencies...\033[0m"

if [ -f 'requirements.txt' ]; then
    echo -e "  \033[90mInstalling from requirements.txt...\033[0m"
    pip install -r requirements.txt
    if [ $? -eq 0 ]; then
        echo -e "  \033[32m✓\033[0m Python dependencies installed"
    else
        echo -e "  \033[31m✗\033[0m Failed to install Python dependencies"
        exit 1
    fi
else
    echo -e "  \033[31m✗\033[0m requirements.txt not found!"
    exit 1
fi

# =============================================================================
# 5. INSTALL NODE DEPENDENCIES
# =============================================================================

echo ""
echo -e "\033[33m[5/6] Installing Node.js dependencies...\033[0m"

if [ -f 'package.json' ]; then
    echo -e "  \033[90mInstalling from package.json...\033[0m"
    npm install
    if [ $? -eq 0 ]; then
        echo -e "  \033[32m✓\033[0m Node dependencies installed"
    else
        echo -e "  \033[31m✗\033[0m Failed to install Node dependencies"
        echo -e "  \033[90mTry: npm cache clean --force && npm install\033[0m"
        exit 1
    fi
else
    echo -e "  \033[31m✗\033[0m package.json not found!"
    exit 1
fi

# =============================================================================
# 6. FINAL CHECKS & SUMMARY
# =============================================================================

echo ""
echo -e "\033[33m[6/6] Final configuration check...\033[0m"

checks=(
    "venv:Python virtual env"
    "venv/lib/python*/site-packages/flask:Python dependencies"
    "node_modules:Node modules"
    ".env:.env file"
)

for check in "${checks[@]}"; do
    IFS=':' read -r path name <<< "$check"
    if [ -e "$path" ] 2>/dev/null || ls $path 2>/dev/null | grep -q .; then
        echo -e "  \033[32m✓\033[0m $name: Found"
    else
        echo -e "  \033[31m✗\033[0m $name: NOT FOUND"
    fi
done

# =============================================================================
# SETUP COMPLETE
# =============================================================================

cat << 'EOF'

╔════════════════════════════════════════════════════════════════╗
║                 ✓ SETUP COMPLETE!                              ║
╚════════════════════════════════════════════════════════════════╝

Next steps:

  1. Edit .env file and add your GEMINI_API_KEY
     Get key from: https://makersuite.google.com/app/apikey

  2. Start the Flask backend (in this terminal):
     python app.py

  3. Start the Vite frontend (in a new terminal):
     npm run dev

  4. Open browser to: http://localhost:5173/

For help, see: README.md

Happy coding! 🚀

EOF
