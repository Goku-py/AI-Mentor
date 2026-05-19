# TestSprite MCP Test Report — AI Code Mentor

**Date:** 2026-05-19  
**Project:** AI_Mentor (full-stack)  
**Mode:** Local full-stack validation complete; cloud TestSprite MCP pending `API_KEY` in Cursor

## Summary

| Pass | Tests | Passed | Failed | Notes |
|------|-------|--------|--------|-------|
| Backend (API) | 6 | 6 | 0 | `scripts/verify-backend-api.ps1` |
| Frontend (UI) | 4 | 4 | 0 | Playwright `e2e/fullstack.spec.ts` |
| Pytest | 107 | 107 | 0 | `python -m pytest tests/` |

## Backend results (TC101–TC106)

| ID | Title | Status |
|----|-------|--------|
| TC101 | Health endpoint | Pass |
| TC102 | Tools endpoint | Pass |
| TC103 | Analyze valid Python | Pass |
| TC104 | Analyze rejects empty | Pass |
| TC105 | History requires auth | Pass |
| TC106 | Login returns token | Pass |

## Frontend results (TC001–TC004)

| ID | Title | Status |
|----|-------|--------|
| TC001 | Homepage loads | Pass |
| TC002 | Run Python output | Pass |
| TC003 | Auth login | Pass |
| TC004 | Theme toggle | Pass |

## Cloud TestSprite MCP (optional next step)

When `API_KEY` is set in Cursor MCP or shell:

```powershell
$env:API_KEY = "your-rotated-key"
.\scripts\testsprite-execute-pass.ps1 -Pass frontend
.\scripts\testsprite-execute-pass.ps1 -Pass backend
```

Upload `docs/testsprite-prd.md` in the TestSprite config portal on first bootstrap.

## Test credentials (dev only)

- Email: `testsprite@example.com`
- Password: `TestSprite1!`
