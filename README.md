# AI Code Mentor

An intelligent, interactive compiler platform designed to help students learn how to code by identifying their mistakes and providing pedagogical hints without giving away the direct answers. Built with a modern, responsive web architecture and powered by Google Gemini.

## 🚀 Features

*   **Multi-Language Support**: Compiles and executes code in Python, JavaScript, Java, C, and C++.
*   **Intelligent AI Mentor**: Integration with Google Gemini Flash analyzes not just crashes, but *logical errors* too (e.g., executing code correctly but deriving the wrong result based on comments/context).
*   **Pedagogical First**: Strictly configured to provide a 1-sentence explanation of what went wrong, and a single bullet-point hint referencing the line number. It never yields the literal answer so students are forced to think. 
*   **Modern IDE Layout**: An immersive top-and-bottom split layout with glassmorphic aesthetics.
*   **Dynamic Editor**: Features line numbering, infinite inline horizontal scrolling, and dynamic language-based syntax highlighting powered by PrismJS.
*   **Light & Dark Mode**: Beautiful support for both light and dark themes.

---

## 📚 Documentation

- **[Quick Start Guide](QUICKSTART.md)** ⚡ - Get running in 5 minutes!
- **[API Documentation](API.md)** - REST API endpoints and examples
- **[Implementation Summary](IMPLEMENTATION_SUMMARY.md)** - All fixes applied
- **[README Setup Instructions](#local-setup-instructions)** - Detailed setup guide
- **[Tests](tests/README.md)** - How to run automated tests

---

## 🛠 Architecture Stack

**Frontend**
*   **React** & **Vite**: Lightweight, extremely fast front-end framework with hot module reloading.
*   **PrismJS** & `react-simple-code-editor`: Provides real-time code highlighting and IDE-like interactions without the heavy bundle size of larger editors. 
*   **Vanilla CSS**: Custom styling with light/dark mode support, Flexbox-based split-pane layout.

**Backend**
*   **Python + Flask**: A swift, RESTful backend that handles the compilation logic safely.
*   `google-generativeai` **SDK**: Secures the connection to Google's LLM API for rapid mentorship feedback.
*   **Subprocess Executor**: Dynamically creates source files (e.g., detecting Java `public class` names natively) and launches sandboxed execution sequences to capture raw `stdout` and `stderr` streams.

**Testing**
*   **pytest**: Automated unit and integration tests for both backend and frontend

---

## 🔮 Future Roadmap (Scaling & Fine-Tuning)

To take this application from MVP to an enterprise-grade academic tool, our roadmap includes:

1.  **AI Fine-Tuning via Kaggle Datasets**: 
    Currently, the system uses prompt engineering (Zero-Shot execution) leveraging Gemini's innate knowledge. To guarantee strict adherence to the "Mentor Format" and eliminate edge cases, the system should be systematically fine-tuned. By utilizing major open-source Kaggle datasets covering student programming errors (e.g., *CodeSearchNet* or university bug detection datasets), we can train a specialized model (like Gemma or Mistral) that guarantees absolute consistency in its pedagogical approach across thousands of abstract syntax tree variations.
2.  **User Authentication & Tracking**:
    Allowing professors to track a student's history of bugs over a semester to identify specific conceptual weaknesses (e.g., "Student struggles conceptually with For-Loops").
3.  **Strict Process Sandboxing**:
    Implementing Docker-based containerization on the backend compiler to securely run arbitrary, untrusted C++ and Python code at scale.

---


## 💻 Local Setup Instructions

### Required Tools

Before you start, you **MUST** install these on your system:

#### 1. **Node.js & npm**
- Download from: https://nodejs.org/ (LTS version recommended)
- Verify installation:
  ```bash
  node --version
  npm --version
  ```

#### 2. **Python 3.10+**
- Download from: https://www.python.org/
- Verify installation:
  ```bash
  python --version
  ```

#### 3. **C/C++ Compiler** (Optional but recommended)
- **Windows**: Install MinGW-w64 from https://www.mingw-w64.org/ OR TDM-GCC
  - Add to Windows PATH so `gcc --version` works in PowerShell
- **macOS**: Install Xcode Command Line Tools
  ```bash
  xcode-select --install
  ```
- **Linux**: Install build-essential
  ```bash
  sudo apt-get install build-essential
  ```

#### 4. **Java Development Kit (JDK)** (Optional)
- Download from: https://www.oracle.com/java/technologies/downloads/ or https://adoptium.net/
- Verify installation:
  ```bash
  javac -version
  java -version
  ```

---

### Step 1: Clone/Navigate to Project

```bash
cd d:\College\Me\Demo
```

---

### Step 2: Set Up Environment File

1. Copy the template file:
   ```bash
   copy .env.example .env
   ```

2. Edit `.env` and add your Google Gemini API key:
   ```ini
   GEMINI_API_KEY=your_actual_api_key_here
   ```

   **Don't have an API key?**
   - Go to https://makersuite.google.com/app/apikey
   - Create a new API key (Free tier gives 15 requests/min)
   - For higher limits, attach Google Cloud Billing

---

### Step 3: Verify Prerequisites (Windows PowerShell)

Before setting up, check which tools you have:

```powershell
# Create a small verification script
$tools = @{
    'Python' = 'python --version'
    'Node.js' = 'node --version'
    'GCC' = 'gcc --version'
    'G++' = 'g++ --version'
    'Java Compiler' = 'javac -version'
    'Java Runtime' = 'java -version'
}

foreach ($tool in $tools.GetEnumerator()) {
    try {
        & ([scriptblock]::Create($tool.Value)) | Out-Null
        Write-Host "✓ $($tool.Name) is installed" -ForegroundColor Green
    } catch {
        Write-Host "✗ $($tool.Name) NOT found" -ForegroundColor Yellow
    }
}
```

The backend will tell you which languages are unsupported when it starts.

---

### Step 4: Set Up Virtual Environment (Python)

```bash
# Create virtual environment
python -m venv venv

# Activate it (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Or CMD
.\venv\Scripts\activate.bat
```

**If you get execution policy error in PowerShell:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

### Step 5: Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Troubleshooting:**
- If `pip` is not found, try: `python -m pip install -r requirements.txt`
- For SSL errors on Windows, use: `pip install --trusted-host pypi.org --trusted-host pypi.python.org -r requirements.txt`

---

### Step 6: Install Node Dependencies

Open a **new terminal** (don't close the Python one):

```bash
npm install
```

---

### Step 7: Start the Backend (Flask)

In your **Python terminal** (with venv activated):

```bash
python app.py
```

**Expected output:**
```
📊 Server Starting with Configuration:
   Available Tools: {'python': True, 'javascript': True, 'java': False, 'c': False, 'cpp': False}
   AI Mentor Enabled: True
   CORS Enabled: Yes

🚀 Flask app running on http://127.0.0.1:5000
   API Documentation: http://127.0.0.1:5000/
```

If a tool shows `False`, you haven't installed it. That's OK - static analysis will still work.

---

### Step 8: Start the Frontend (Vite)

In your **Node.js terminal**:

```bash
npm run dev
```

**Expected output:**
```
  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

---

### Step 9: Access the App

Open your browser and go to:
```
http://localhost:5173/
```

---

## 🔥 Troubleshooting

### Issue: "Connection refused" error in browser

**Cause**: Flask backend is not running  
**Fix**: 
1. Make sure Flask is running: `python app.py`
2. Check it's on port 5000: `http://127.0.0.1:5000/health`

---

### Issue: Python requirements installation fails

**Cause**: Missing build tools or SSL issues  
**Fix**:
```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Then try again with trusted hosts
pip install --trusted-host pypi.org --trusted-host pypi.python.org -r requirements.txt
```

---

### Issue: Node modules installation fails

**Cause**: npm cache corrupted  
**Fix**:
```bash
rm -r node_modules package-lock.json
npm cache clean --force
npm install
```

---

### Issue: "javac: command not found" or other compiler errors

**Cause**: Tools not installed or not on PATH  
**Fix**:
1. Install the missing tool (see Required Tools above)
2. Add it to Windows PATH:
   - Open "Edit environment variables for your account"
   - Add the installation directory to `Path`
   - Restart PowerShell/CMD
3. Verify: `javac -version`

---

### Issue: AI Mentor feedback not showing

**Cause**: GEMINI_API_KEY not set or invalid  
**Fix**:
1. Check your `.env` file has the key
2. Verify key is valid at: https://makersuite.google.com/app/apikey
3. Check Flask console for error messages
4. If rate-limited, wait a minute or upgrade billing

---

## 📋 Running the Application

Once both servers are running:

1. **Frontend** (Vite): http://localhost:5173/
2. **Backend** (Flask): http://localhost:5000/
3. Select a language → Write code → Click **Run Code**
4. View execution output and AI feedback

---

## 🏗️ Project Architecture

```
d:\College\Me\Demo\
├── app.py                  # Flask backend server
├── analyzer.py             # Code analysis & execution logic
├── requirements.txt        # Python dependencies
├── package.json            # Node.js dependencies
├── vite.config.js          # Vite frontend build config
├── .env.example            # Environment template
│
├── src/                    # React frontend source
│   ├── App.jsx             # Main React component
│   ├── main.jsx            # React entry point
│   ├── index.css           # Styling (light & dark mode)
│
└── dist/                   # Built frontend (generated by npm run build)
```

---

## 🚀 Production Deployment

To build for production:

```bash
npm run build
```

This creates optimized files in `dist/`. You can then:
- Serve static files from Flask
- Deploy to Vercel, Netlify, etc.

---

## 🛠️ Development Tips

- **Hot reload**: Both Vite and Flask auto-reload on file changes
- **Debug mode**: Flask runs with `debug=True` by default
- **Clear cache**: Ctrl+Shift+Delete in browser for full refresh
- **See available tools**: Go to `http://localhost:5000/tools` after starting server

---

