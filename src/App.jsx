import React, { useState } from 'react';
import './index.css';
import Editor from 'react-simple-code-editor';
import Prism from 'prismjs';
import 'prismjs/components/prism-clike';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-c';
import 'prismjs/components/prism-cpp';
import 'prismjs/components/prism-java';
import 'prismjs/themes/prism-tomorrow.css';

// Minimal inline SVG icons for styling
const PlayIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
);
const TerminalIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
);
const SparklesIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"></path><path d="M5 3v4"></path><path d="M19 17v4"></path><path d="M3 5h4"></path><path d="M17 19h4"></path></svg>
);
const CodeIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
);

// Lightweight markdown renderer string -> JSX
const renderMarkdown = (text) => {
    if (!text) return null;
    const parts = text.split(/(```[\s\S]*?```|`[^`]+`|\*\*[^*]+\*\*|\n\n)/g);
    return parts.map((part, i) => {
        if (part === '\n\n') return <br key={i} />;
        if (part.startsWith('```') && part.endsWith('```')) {
            const lines = part.slice(3, -3).split('\n');
            const code = lines.slice(1).join('\n').trim() || lines[0];
            return <pre key={i}><code>{code}</code></pre>;
        }
        if (part.startsWith('`') && part.endsWith('`')) {
            return <code key={i}>{part.slice(1, -1)}</code>;
        }
        if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={i}>{part.slice(2, -2)}</strong>;
        }
        return <span key={i}>{part}</span>;
    });
};

export default function App() {
    const [code, setCode] = useState('print("Hello World!")\n# Try making an intentional mistake here\n# my_var = 10 / 0');
    const [language, setLanguage] = useState('python');
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    // Result States
    const [output, setOutput] = useState('');
    const [errorMsg, setErrorMsg] = useState('');
    const [mentorFeedback, setMentorFeedback] = useState('');
    const [issues, setIssues] = useState([]);

    const handleRun = async () => {
        setIsAnalyzing(true);
        setOutput('');
        setErrorMsg('');
        setMentorFeedback('');
        setIssues([]);

        try {
            const response = await fetch("http://127.0.0.1:5000/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code, language }),
            });

            const data = await response.json();

            if (data.issues) {
                setIssues(data.issues);
            }

            if (data.execution) {
                const stdout = data.execution.stdout || '';
                const stderr = data.execution.stderr || '';

                setOutput(stdout);

                // If there's an error, capture raw stderr & fetch AI feedback
                // Check for errors to display in the standard output block
                const hasErrorIssues = data.issues && data.issues.some(i => i.severity === 'error');
                if (data.execution.error || data.execution.returncode !== 0 || hasErrorIssues) {
                    setErrorMsg(stderr || data.execution.error?.message || "An execution error occurred.");
                }

                // Unconditionally set AI Mentor Feedback (captures logic errors even on success)
                if (data.ai_mentor_feedback) {
                    setMentorFeedback(data.ai_mentor_feedback);
                }
            } else if (!data.ok) {
                setErrorMsg(data.error || "Analysis failed.");
            }
        } catch (err) {
            setErrorMsg("Network error: Make sure the Python backend (app.py) is running on port 5000.");
        } finally {
            setIsAnalyzing(false);
        }
    };

    const getPrismLanguage = (lang) => {
        if (lang === 'cpp' || lang === 'c') return Prism.languages.cpp || Prism.languages.clike;
        if (lang === 'java') return Prism.languages.java || Prism.languages.clike;
        if (lang === 'javascript') return Prism.languages.javascript;
        return Prism.languages.python;
    };

    return (
        <div className="app-container">
            {/* Header Area */}
            <header className="header">
                <div className="header-title">
                    <CodeIcon />
                    <span>AI Code Mentor</span>
                </div>
                <div className="controls">
                    <select
                        className="language-select"
                        value={language}
                        onChange={(e) => setLanguage(e.target.value)}
                    >
                        <option value="python">Python</option>
                        <option value="java">Java (Compilation)</option>
                        <option value="c">C (Compilation)</option>
                        <option value="cpp">C++ (Compilation)</option>
                    </select>
                    <button
                        className="run-btn"
                        onClick={handleRun}
                        disabled={isAnalyzing || !code.trim()}
                    >
                        <PlayIcon />
                        {isAnalyzing ? "Running..." : "Run Code"}
                    </button>
                </div>
            </header>

            {/* Main Editor Grid */}
            <div className="main-content">
                {/* Editor Top Block */}
                <div className="editor-pane">
                    <div className="pane-header">
                        <CodeIcon /> Editor
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', overflowX: 'auto', backgroundColor: 'var(--bg-color)', minHeight: 0, display: 'flex' }}>
                        <div className="line-numbers">
                            {code.split('\n').map((_, i) => (
                                <div key={i}>{i + 1}</div>
                            ))}
                        </div>
                        <div style={{ flex: 1, position: 'relative' }}>
                            <Editor
                                value={code}
                                onValueChange={code => setCode(code)}
                                highlight={code => Prism.highlight(code, getPrismLanguage(language), language)}
                                padding={24}
                                style={{
                                    fontFamily: 'var(--font-mono)',
                                    fontSize: 15,
                                    minHeight: '100%',
                                    whiteSpace: 'pre'
                                }}
                                textareaClassName="code-textarea"
                            />
                        </div>
                    </div>
                </div>

                {/* Terminals Bottom Block */}
                <div className="side-pane">

                    {/* Console Output Block */}
                    <div className="output-pane">
                        <div className="pane-header">
                            <TerminalIcon /> Standard Output & Code Issues
                        </div>
                        <div className="pane-content">
                            {!output && !errorMsg && issues.length === 0 && (
                                <div className="placeholder-text">Outputs and issues will appear here when you run code.</div>
                            )}

                            {issues.length > 0 && (
                                <div style={{ marginBottom: (output || errorMsg) ? '1rem' : 0, borderBottom: (output || errorMsg) ? '1px solid var(--border-color)' : 'none', paddingBottom: (output || errorMsg) ? '0.5rem' : 0 }}>
                                    <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>Compiled Analysis Issues:</div>
                                    {issues.map((i, idx) => (
                                        <div key={idx} style={{ color: i.severity === 'error' ? 'var(--error)' : 'var(--warning)', fontSize: '0.9em', marginBottom: '0.2rem' }}>
                                            [Line {i.line}] {i.severity.toUpperCase()}: {i.message}
                                        </div>
                                    ))}
                                </div>
                            )}

                            {output && (
                                <div style={{ marginBottom: errorMsg ? '1rem' : 0 }}>
                                    {output}
                                </div>
                            )}

                            {errorMsg && (
                                <div className="error-text">
                                    <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: '#ff7b72' }}>
                                        Compiler Error / Exception:
                                    </div>
                                    {errorMsg}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* AI Mentor Block */}
                    <div className="mentor-pane">
                        <div className="pane-header accent-text">
                            <SparklesIcon /> AI Mentor Feedback
                        </div>
                        <div className="pane-content mentor-content">
                            {isAnalyzing ? (
                                <div className="placeholder-text">Analyzing code ...</div>
                            ) : mentorFeedback && !mentorFeedback.includes("LOOKS_GOOD") ? (
                                <div>{renderMarkdown(mentorFeedback)}</div>
                            ) : mentorFeedback && mentorFeedback.includes("LOOKS_GOOD") ? (
                                <div className="placeholder-text">
                                    <SparklesIcon />
                                    Your code ran successfully! No errors or logical flaws detected.
                                    <br />Keep up the great work.
                                </div>
                            ) : (errorMsg || issues.some(i => i.severity === 'error')) ? (
                                <div className="placeholder-text">
                                    I will help explain any errors and how to fix them!
                                    <br /><br />
                                    (Note: Ensure your GEMINI_API_KEY is set in the server's .env file to enable AI Mentorship)
                                </div>
                            ) : (
                                <div className="placeholder-text">
                                    <SparklesIcon />
                                    Your code executed cleanly. Make sure to include comments so I can verify your logic.
                                </div>
                            )}
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
}
