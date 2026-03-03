# AI Code Mentor

An intelligent, interactive compiler platform designed to help students learn how to code by identifying their mistakes and providing pedagogical hints without giving away the direct answers. Built with a modern, responsive web architecture and powered by Google Gemini.

## 🚀 Features

*   **Multi-Language Support**: Compiles and executes code in Python, C, C++, and Java.
*   **Intelligent AI Mentor**: Integration with Google Gemini Flash analyzes not just crashes, but *logical errors* too (e.g., executing code correctly but deriving the wrong result based on comments/context).
*   **Pedagogical First**: Strictly configured to provide a 1-sentence explanation of what went wrong, and a single bullet-point hint referencing the line number. It never yields the literal answer so students are forced to think. 
*   **Modern IDE Layout**: An immersive top-and-bottom split layout with glassmorphic aesthetics.
*   **Dynamic Editor**: Features line numbering, infinite inline horizontal scrolling, and dynamic language-based syntax highlighting powered by PrismJS.

---

## 🛠 Architecture Stack

**Frontend**
*   **React** & **Vite**: Lightweight, extremely fast front-end framework.
*   **PrismJS** & `react-simple-code-editor`: Provides real-time code highlighting and IDE-like interactions without the heavy bundle size of larger editors. 
*   **Vanilla CSS**: Custom styling prioritizing a sleek, "Dark Mode" aesthetic and Flexbox-based split-pane layout.

**Backend**
*   **Python + Flask**: A swift, RESTful backend that handles the compilation logic safely.
*   `google-genai` **SDK**: Secures the connection to Google's LLM API for rapid mentorship feedback.
*   **Subprocess Executor**: Dynamically creates source files (e.g., detecting Java `public class` names natively) and launches sandboxed execution sequences to capture raw `stdout` and `stderr` streams. 

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

### 1. Requirements
*   Node.js (for React frontend)
*   Python 3.10+ (for Flask backend)
*   C/C++ Compiler (GCC) and Java Development Kit (JDK) installed and available in system PATH.

### 2. Environment Setup
Create a `.env` file in the root directory and securely add your Google AI Studio key:
```ini
GEMINI_API_KEY=your_google_ai_studio_api_key_here
```
*(Note: To avoid hitting the "15 requests per minute" limit on the AI Mentor, attach a Google Cloud Billing account to your API key in AI Studio. The `gemini-2.5-flash` model is incredibly cost-efficient for this pipeline).*

### 3. Running the Backend
1. Open a terminal.
2. Activate your Virtual Environment: `.\venv\Scripts\Activate.ps1`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the Flask Server (Port 5000):
```bash
python app.py
```

### 4. Running the Frontend
1. Open a new terminal.
2. Install Node dependencies: `npm install`
3. Start the Vite Dev Server (Port 5173):
```bash
npm run dev
```

### 5. Access
Navigate to `http://localhost:5173/` in your browser. Select a language, type intentional errors, and let the AI teach you!
