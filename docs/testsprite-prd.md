# AI Code Mentor — Product Requirements (TestSprite)

## Product overview

AI Code Mentor is a web app where students write code in a browser editor, run it against local toolchains, and receive AI-powered hints (Google Gemini) without full solution spoilers.

## Core goals

- Provide a multi-language code editor (Python, JavaScript, Java, C, C++).
- Execute code safely and show stdout/stderr in an output panel.
- Offer optional AI mentorship feedback on code quality and errors.
- Support user accounts (register, login, logout, GitHub OAuth optional).
- Persist analyze history for authenticated users.

## Key features

| Feature | Description |
|---------|-------------|
| Code editor | Syntax-highlighted editor with language selector |
| Run Code | POST analyze → execution + static issues + AI feedback |
| Theme | Light/dark mode toggle |
| Auth | Email/password register & login; optional GitHub OAuth |
| History | Authenticated users can view/clear analyze history |
| Toolbar | Font size, fullscreen, share link, clear editor |

## User flows

1. **Guest** — Open app → select language → type code → Run Code → see output (rate-limited by IP).
2. **Register** — Sign In → Create account → submit → logged in with JWT.
3. **Login** — Sign In → credentials → modal closes → user badge visible.
4. **Run while logged in** — Analyze uses user-scoped rate limits; history recorded.
5. **Logout** — Sign out → session cleared.

## Validation criteria

- Editor and Run Code button visible on load.
- Valid Python `print('hello')` shows `hello` in output when backend is up.
- Invalid login shows error in auth modal (no silent success).
- Health endpoint returns `status` and `available_tools`.
- Analyze rejects empty code with 400.
- History endpoints require JWT (401 without token).
- Security: abuse patterns in code return 400.

## Technical context

- **Frontend:** React 18, Vite, port 5173; proxies `/api/v1` → Flask :5000.
- **Backend:** Flask, Python, port 5000, OpenAPI at `api-contract/openapi.v1.yaml`.
- **Test user:** `testsprite@example.com` / `TestSprite1!` (development only).
