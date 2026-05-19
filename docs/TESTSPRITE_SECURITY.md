# TestSprite API key security

If a TestSprite API key was ever pasted in chat, committed to git, or shared in a screenshot:

1. Open [TestSprite Dashboard → API Keys](https://www.testsprite.com/dashboard/settings/apikey).
2. **Revoke** the exposed key immediately.
3. Create a **new** key and set it only in:
   - Cursor → Settings → Tools & Integration → TestSprite MCP → `API_KEY`, or
   - Local shell: `$env:API_KEY = '...'` (never commit).

Do not store TestSprite keys in `.env` if that file is shared; prefer Cursor MCP env only.
