# TestSprite artifacts

Generated for the TestSprite MCP full-stack testing workflow.

| Path | Purpose |
|------|---------|
| `standard_prd.json` | Normalized PRD for TestSprite |
| `testsprite_frontend_test_plan.json` | Frontend test cases |
| `testsprite_backend_test_plan.json` | Backend API test cases |
| `tmp/code_summary.yaml` | Codebase summary |
| `tmp/prd_files/` | PRD upload copy for config portal |
| `tmp/config.*.example.json` | Example committed configs per pass |
| `TestSprite_MCP_Test_Report.md` | Combined results report |

Run local validation:

```powershell
.\scripts\setup-testsprite-env.ps1
.\scripts\verify-backend-api.ps1
npm run test:e2e
```

`tmp/` is gitignored (except committed examples); do not commit API keys or cloud session data.
