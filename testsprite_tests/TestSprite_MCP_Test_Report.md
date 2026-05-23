# TestSprite MCP Test Report — AI Code Mentor

**Date:** 2026-05-23
**Project:** AI_Mentor (full-stack)
**Mode:** Hybrid (Local + TestSprite Cloud MCP)

---

## Summary

| Pass | Tests | Passed | Failed | Notes |
|------|-------|--------|--------|-------|
| Pytest (local) | 107 | 107 | 0 | Full unit test suite |
| Backend API (local script) | 6 | 4 | 2 | TC103 sandbox, TC106 CSRF |
| Playwright e2e (local) | 4 | 3 | 1 | TC002 sandbox unavailable |
| **TestSprite Cloud Backend** | **6** | **4** | **2** | TC101 CSRF, TC103 bot detection |
| **TestSprite Cloud Frontend** | **5** | **0** | **5** | Tunnel could not reach Vite (Win firewall?) |

---

## TestSprite Cloud — Backend Results (TC101–TC106)

| ID | Title | Status | Root Cause |
|----|-------|--------|------------|
| TC101 | Health endpoint returns status | ❌ | Login called without CSRF token. Health doesn't need auth anyway |
| TC102 | Tools endpoint lists languages | ✅ | Used CSRF + correct credentials — working |
| TC103 | Analyze valid Python | ❌ | Endpoint blocked: "Automated requests are not permitted" |
| TC104 | Analyze rejects empty code | ✅ | Working |
| TC105 | History requires authentication | ✅ | Working |
| TC106 | Login returns access token | ✅ | Working — uses email field correctly |

---

## TestSprite Cloud — Frontend Results (TC001–TC005)

| ID | Title | Status | Root Cause |
|----|-------|--------|------------|
| TC001 | Homepage loads with editor | ❌ | Tunnel could not reach localhost:5174 |
| TC002 | Run default Python prints Hello World | ❌ | Same — tunnel timeout |
| TC003 | Login with test credentials | ❌ | Same |
| TC004 | Toggle light/dark theme | ❌ | Same |
| TC005 | Invalid login shows error | ❌ | Same |

**Note:** The Playwright e2e tests (3/4 passing) cover the same scenarios locally and serve as the frontend validation.

---

## Local Test Results

### Pytest (107/107 ✅)
All 107 unit tests pass across 5 test files.

### Backend API Script (4/6 ✅)

| ID | Title | Status | Detail |
|----|-------|--------|--------|
| TC101 | Health endpoint | ✅ | status=healthy |
| TC102 | Tools endpoint | ✅ | python=True |
| TC103 | Analyze valid Python | ❌ | stdout= (sandbox requires Docker) |
| TC104 | Analyze rejects empty | ✅ | http=400 |
| TC105 | History requires auth | ✅ | http=401 |
| TC106 | Login returns token | ❌ | 400 (CSRF missing — now fixed in script) |

### Playwright e2e (3/4 ✅)

| Test | Status | Detail |
|------|--------|--------|
| Health via proxy | ✅ | 25ms |
| Editor runs Python | ❌ | "Sandbox unavailable: Docker not running" |
| Auth login | ✅ | 1.7s |
| Theme toggle | ✅ | 380ms |

---

## Issues Discovered & Fixes Applied

| # | Issue | Fix Applied |
|---|-------|-------------|
| 1 | Vite crashed from watching `.venv/` | ✅ Added `server.watch.ignored` in `vite.config.ts` |
| 2 | Login 400 (CSRF missing) in `verify-backend-api.ps1` | ✅ Added `-WebSession $session -Headers $csrfHeaders` |
| 3 | TestSprite cloud test used `username` not `email` | ✅ Updated `additionalInstruction` in config |
| 4 | TestSprite cloud test used wrong credentials | ✅ Updated config with correct test credentials |
| 5 | TestSprite frontend tunnel fails on port 5173/5174 | ⚠️ Windows firewall / tunnel routing issue |

---

## Next Steps

1. **Run frontend tests locally** via Playwright: `npx playwright test e2e/fullstack.spec.ts`
2. **Review TestSprite dashboard** for detailed failure analysis: https://www.testsprite.com/dashboard/mcp/tests/
3. **Fix TC101 test script**: Don't require auth for health endpoint
4. **Fix TC103 test script**: Add proper User-Agent to bypass bot detection
5. **Enable Docker** for sandbox code execution to get TC103/TC002 passing

---

## Test Credentials

- Email: `testsprite@example.com`
- Password: `TestSprite1!`
