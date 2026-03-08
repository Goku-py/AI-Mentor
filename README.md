# AI Code Mentor

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-AI%20Powered-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

> **AI Code Mentor** is a coding practice tool for students. You write code, run it, and if something goes wrong — the AI explains *what* went wrong and gives you a **hint** to fix it yourself. It never just hands you the answer.

![AI Code Mentor Screenshot](docs/assets/preview.png)

---

## 🤔 What does it do?

Imagine you're learning to code and your program crashes. Instead of staring at a confusing error message, AI Code Mentor:

1. **Runs your code** in the language you chose (Python, JavaScript, Java, C, or C++)
2. **Reads the output** — whether it crashed, printed the wrong result, or had a logic mistake
3. **Gives you a one-sentence explanation** of what went wrong
4. **Gives you one hint** pointing to the exact line — not the solution, just enough to get you thinking

It's like having a tutor sitting next to you who refuses to do your homework for you. 😄

---

## ✨ What can you do with it?

| | |
|---|---|
| 🌐 **5 languages** | Write and run Python, JavaScript, Java, C, or C++ — all in the browser |
| 🤖 **AI hints** | Google's AI reads your code and tells you what's wrong, without spoiling the fix |
| 💡 **Catches hidden mistakes** | Even if your code *runs* but gives the wrong answer, the AI notices |
| 🌙 **Light & dark mode** | Switch themes with one click |
| 🎨 **Color-coded editor** | Code automatically gets colored by language so it's easier to read |

---

## 🚀 How to run it on your computer

You'll need two free tools installed first:
- **Python** — download from https://www.python.org/ (any version 3.10 or newer)
- **Node.js** — download from https://nodejs.org/ (pick the "LTS" version)

You'll also need a **free AI key** from Google:
- Go to https://aistudio.google.com/app/apikey → click **"Create API key"** → copy it

Then open a terminal and run these commands:

**Step 1 — Download the project**
```bash
git clone https://github.com/your-username/ai-code-mentor.git
cd ai-code-mentor
```

**Step 2 — Add your AI key**
```bash
copy .env.example .env
```
Open the `.env` file that was just created, find the line that says `GEMINI_API_KEY=`, and paste your key after the `=`.

**Step 3 — Start the AI server** *(keep this window open)*
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

**Step 4 — Start the website** *(open a second terminal window)*
```bash
npm install
npm run dev
```

**Step 5 — Open it in your browser**
```
http://localhost:5173
```

Select a language, type some code, and click **Run Code**. That's it!

> [!NOTE]
> Want to run Java or C/C++ as well? You'll need to install a Java or C compiler separately — but Python and JavaScript work right away without anything extra.

> [!TIP]
> On Windows, if you see a red error about "execution policy" in the terminal, run this once and try again:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

---

## 🔥 Something not working?

| What you see | What to try |
|---|---|
| "Connection refused" or blank page | Make sure the AI server is still running (`python app.py` in the first terminal) |
| `pip install` gives an error | Run `python -m pip install --upgrade pip` first, then try again |
| `npm install` gives an error | Delete the `node_modules` folder, run `npm cache clean --force`, then `npm install` again |
| Java or C/C++ says "compiler not found" | You need to install the Java or C compiler separately and add it to your system PATH |
| No AI hint appears after running code | Double-check your `.env` file has the correct API key with no extra spaces |

Still stuck? [Open an issue on GitHub](https://github.com/your-username/ai-code-mentor/issues) and describe what happened.

---

## 🔮 What's coming next?

- **Smarter AI hints** — training the AI specifically on common student mistakes for even better feedback
- **Teacher dashboard** — so professors can see which topics their students struggle with most
- **Safer code execution** — running student code in an isolated container so nothing can go wrong on the server

---

## 🛠️ For developers

<details>
<summary>Click to expand — project structure & how it's built</summary>

The app has two parts that run at the same time:
- **AI server** (`app.py`, `analyzer.py`) — handles running code and calling Google's AI
- **Website** (`src/`) — the editor and output panel you see in the browser

```
ai-code-mentor/
├── app.py            # AI server
├── analyzer.py       # Runs the code & talks to Google AI
├── src/
│   ├── App.jsx       # The main editor + output screen
│   └── index.css     # All the styling (light/dark mode, layout)
└── tests/            # Automated tests
```

| Part | Built with |
|---|---|
| Website | React + Vite |
| AI server | Python + Flask |
| AI hints | Google Gemini (via API) |
| Tests | pytest |

</details>

---

## 🏅 Contributing

Contributions are welcome! To get started:

1. Fork this repo and create a new branch
2. Make your changes
3. Open a Pull Request with a short description of what you changed

---
