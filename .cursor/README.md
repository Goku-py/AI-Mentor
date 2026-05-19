# Cursor MCP — TestSprite

## Install

1. **Node.js 22+** — `node --version` (required for the MCP server).
2. Copy `mcp.json.example` to **Cursor user settings** (recommended) or to `.cursor/mcp.json` locally (gitignored).
3. Replace `API_KEY` with your key from [TestSprite Dashboard → API Keys](https://www.testsprite.com/dashboard/settings/apikey).
4. **Revoke** any key that was ever pasted in chat or committed to git; create a new key.
5. Cursor → **Chat** → **Auto-Run** → set to **Ask Everytime** or **Run Everything** (sandbox blocks TestSprite).

## Verify

- Green dot on the TestSprite MCP server in Tools & Integration.
- Prompt: `Help me test this project with TestSprite.`

## Full-stack run (this repo)

1. Start backend: `python app.py` (port 5000).
2. Start frontend: `npm run dev` (port 5173).
3. Run `.\scripts\setup-testsprite-env.ps1` to register the test user.
4. Upload `docs/testsprite-prd.md` in the TestSprite config portal when bootstrap opens.
5. In Agent chat: run frontend pass (`type: frontend`, port `5173`), then backend pass (`type: backend`, port `5000`).

Test credentials (dev only): `testsprite@example.com` / `TestSprite1!`
