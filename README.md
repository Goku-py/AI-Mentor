# AI Code Mentor

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-AI%20Powered-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-ai--mentor--three--cyan.vercel.app-brightgreen?style=for-the-badge)](https://ai-mentor-tech.vercel.app)

> **AI Code Mentor** is a coding practice tool for students. You write code, run it, and if something goes wrong â€” the AI explains *what* went wrong and gives you a **hint** to fix it yourself. It never just hands you the answer.

<img width="1919" height="995" alt="image" src="https://github.com/user-attachments/assets/27f1a775-bc57-4d80-9479-45dcc33a6f25" />


---

## ðŸ¤” What does it do?

Imagine you're learning to code and your program crashes. Instead of staring at a confusing error message, AI Code Mentor:

1. **Runs your code** in the language you chose (Python, JavaScript, Java, C, or C++)
2. **Reads the output** â€” whether it crashed, printed the wrong result, or had a logic mistake
3. **Gives you a one-sentence explanation** of what went wrong
4. **Gives you one hint** pointing to the exact line â€” not the solution, just enough to get you thinking

It's like having a tutor sitting next to you who refuses to do your homework for you. ðŸ˜„

---

## âœ¨ What can you do with it?

| | |
|---|---|
| ðŸŒ **5 languages** | Write and run Python, JavaScript, Java, C, or C++ â€” all in the browser |
| ðŸ¤– **AI hints** | Google's AI reads your code and tells you what's wrong, without spoiling the fix |
| ðŸ’¡ **Catches hidden mistakes** | Even if your code *runs* but gives the wrong answer, the AI notices |
| ðŸŒ™ **Light & dark mode** | Switch themes with one click |
| ðŸŽ¨ **Color-coded editor** | Code automatically gets colored by language so it's easier to read |
| ðŸ” **User accounts** | Sign in with email + password to save your progress |
| ðŸ›¡ï¸ **Safe execution** | Code runs in an isolated Docker container â€” or, where Docker is unavailable (e.g. Render's free tier), in a hardened OS-level host sandbox |

---

## ðŸš€ How to run it on your computer

You'll need two free tools installed first:
- **Python** â€” download from https://www.python.org/ (3.11 or newer; CI and the deployed backend both run 3.11)
- **Node.js** â€” download from https://nodejs.org/ (pick the "LTS" version)

You'll also need a **free AI key** from Google:
- Go to https://aistudio.google.com/app/apikey â†’ click **"Create API key"** â†’ copy it

Then open a terminal and run these commands:

**Step 1 â€” Download the project**
```bash
git clone https://github.com/Goku-py/AI-Mentor.git
cd AI-Mentor
```

**Step 2 â€” Add your AI key**
```bash
copy .env.example .env
```
Open the `.env` file that was just created, find the line that says `GEMINI_API_KEY=`, and paste your key after the `=`.

**Step 3 â€” Install dependencies**
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm install
```

**Step 4 â€” Start everything with one command**
```bash
npm run dev:full
```

**Step 5 â€” Open it in your browser**
```
http://localhost:5173
```

Select a language, type some code, and click **Run**. That's it!

> [!NOTE]
> Want to run Java or C/C++ as well? You'll need to install a Java or C compiler separately â€” but Python and JavaScript work right away without anything extra.

> [!TIP]
> On Windows, if you see a red error about "execution policy" in the terminal, run this once and try again:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

---

## ðŸ”¥ Something not working?

| What you see | What to try |
|---|---|
| "Connection refused" or blank page | Make sure `npm run dev:full` is still running in your terminal |
| `pip install` gives an error | Run `python -m pip install --upgrade pip` first, then try again |
| `npm install` gives an error | Delete the `node_modules` folder, run `npm cache clean --force`, then `npm install` again |
| Java or C/C++ says "compiler not found" | You need to install the Java or C compiler separately and add it to your system PATH |
| No AI hint appears after running code | Double-check your `.env` file has the correct API key with no extra spaces |

Still stuck? [Open an issue on GitHub](https://github.com/Goku-py/AI-Mentor/issues) and describe what happened.

---

## ðŸ”® What's coming next?

- **Smarter AI hints** â€” training the AI specifically on common student mistakes for even better feedback
- **Teacher analytics** â€” so professors can see which topics their students struggle with most
- **Deeper AI training** â€” fine-tuning the model to recognize more logic errors and edge cases

---

## ðŸ› ï¸ For developers

<details>
<summary>Click to expand â€” project structure & how it's built</summary>

The app has two parts that run at the same time:
- **Backend** (`app.py`, `app_pkg/`, `analyzer/`, `models_pkg/`) â€” runs code, handles auth, calls Google's AI
- **Frontend** (`src/`) â€” the editor, output panel, and auth modal you see in the browser

```
AI-Mentor/
â”œâ”€â”€ app.py                # Entry point
â”œâ”€â”€ analyzer/             # Code execution & AI analysis (package)
â”‚   â”œâ”€â”€ core.py           # Sandbox execution + orchestrator
â”‚   â”œâ”€â”€ errors.py         # Typed error hierarchy
â”‚   â””â”€â”€ mentorship.py     # Gemini hint/mentorship prompts
â”œâ”€â”€ app_pkg/              # Flask application package
â”‚   â”œâ”€â”€ blueprints/       # Route handlers (api, auth, debug_bp, static_files)
â”‚   â”œâ”€â”€ security/         # Security middleware
â”‚   â”œâ”€â”€ cli.py            # `flask` CLI entry
â”‚   â”œâ”€â”€ config.py         # App configuration
â”‚   â”œâ”€â”€ extensions.py     # Flask extensions (SQLAlchemy, etc.)
â”‚   â”œâ”€â”€ observability.py  # Logging & metrics
â”‚   â””â”€â”€ utils.py          # Shared helpers
â”œâ”€â”€ models_pkg/           # Database models (user, audit log)
â”œâ”€â”€ migrations/           # Alembic/Flask-Migrate revisions
â”œâ”€â”€ src/                  # React frontend (TypeScript)
â”‚   â”œâ”€â”€ App.tsx           # Main app layout
â”‚   â”œâ”€â”€ components/       # UI components (Auth, Editor, Output, Toolbar, Icons)
â”‚   â”œâ”€â”€ hooks/            # React hooks (useAuth, useCode, useSettings)
â”‚   â”œâ”€â”€ services/         # API client
â”‚   â””â”€â”€ types/            # TypeScript type definitions
â”œâ”€â”€ e2e/                  # Playwright end-to-end specs
â”œâ”€â”€ tests/                # pytest suite
â”œâ”€â”€ public/               # Static assets (favicon, OG image, robots.txt, sitemap.xml, webmanifest)
â”œâ”€â”€ docs/                 # Audit reports & remediation plan
â”œâ”€â”€ .github/workflows/    # CI (lint, pytest, Playwright, migrations, builds)
â”œâ”€â”€ pyproject.toml        # Python tool config (ruff)
â”œâ”€â”€ pytest.ini            # pytest config (includes the --cov gate)
â”œâ”€â”€ requirements.txt      # Direct Python dependencies
â”œâ”€â”€ requirements.lock     # Fully pinned Python dependencies (used by CI)
â”œâ”€â”€ vercel.json           # Frontend hosting + /api proxy + security headers
â”œâ”€â”€ render.yaml           # Backend service definition
â”œâ”€â”€ vite.config.ts        # Vite bundler config
â””â”€â”€ tsconfig.json         # TypeScript config
```

| Part | Built with |
|---|---|
| Website | React + TypeScript + Vite |
| AI server | Python + Flask |
| AI hints | Google Gemini (via API) |
| Database | SQLite (dev) / PostgreSQL (production) |
| Execution | Docker container sandbox; hardened host sandbox when Docker is unavailable |
| Tests | pytest (Python) + Playwright (E2E) |

> [!IMPORTANT]
> **Execution sandbox.** Locally, code execution prefers an isolated Docker
> container and only falls back to a host-level sandbox when Docker is not
> reachable. **On the deployed Render backend there is no Docker daemon**, so
> production currently runs with `HOST_EXECUTION_ENABLED=1` and uses the host
> sandbox exclusively â€” the "isolated containers" description above does *not*
> describe production behaviour. Host execution is being removed from the
> production configuration; see `render.yaml` for the authoritative setting.

> [!NOTE]
> **Deployment split.** The SPA is served by Vercel and the Flask API by Render.
> `vercel.json` proxies `/api/*` to the backend, whose origin comes from the
> `API_BACKEND_ORIGIN` environment variable â€” that variable must be set in the
> Vercel project or the proxy will not resolve.

</details>

---

## ðŸ… Contributing

Contributions are welcome! To get started:

1. Fork this repo and create a new branch
2. Make your changes
3. Open a Pull Request with a short description of what you changed

---
