import React, { useState } from 'react';
import Editor from 'react-simple-code-editor';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';
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
// New toolbar icons matching provided design
const FontDecreaseIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6H6" /><path d="M12 18v-12" /><path d="M8 14l4-4 4 4" /></svg>
);
const FontIncreaseIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 6h12" /><path d="M12 18v-12" /><path d="M10 10l4 4 4-4" /></svg>
);
const SunIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5" /><path d="M12 1v2" /><path d="M12 21v2" /><path d="M4.22 4.22l1.42 1.42" /><path d="M18.36 18.36l1.42 1.42" /><path d="M1 12h2" /><path d="M21 12h2" /><path d="M4.22 19.78l1.42-1.42" /><path d="M18.36 5.64l1.42-1.42" /></svg>
);
const MoonIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg>
);
const LanguageIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><path d="M2 12h20" /><path d="M12 2a15.3 15.3 0 0 0 0 20" /><path d="M12 2a15.3 15.3 0 0 1 0 20" /></svg>
);
const UploadIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
);
const TrashIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-2 14H7L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" /></svg>
);
const FullscreenIcon = ({ exit = false }) => (
    exit ?
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6h-6v6" /><path d="M6 18h6v-6" /></svg>
        :
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3" /><path d="M16 3h3a2 2 0 0 1 2 2v3" /><path d="M8 21H5a2 2 0 0 1-2-2v-3" /><path d="M16 21h3a2 2 0 0 0 2-2v-3" /></svg>
);
const ShareIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" /><polyline points="16 6 12 2 8 6" /><line x1="12" y1="2" x2="12" y2="15" /></svg>
);

const LanguageSelector = ({ language, onLanguageChange }) => {
    const languages = [
        { id: 'python', name: 'Python' },
        { id: 'javascript', name: 'JavaScript' },
        { id: 'java', name: 'Java' },
        { id: 'c', name: 'C' },
        { id: 'cpp', name: 'C++' }
    ];

    return (
        <div className="language-selector-wrapper">
            <select
                className="language-select"
                value={language}
                onChange={(e) => onLanguageChange(e.target.value)}
                title="Select programming language"
            >
                {languages.map(lang => (
                    <option key={lang.id} value={lang.id}>{lang.name}</option>
                ))}
            </select>
        </div>
    );
}

// Lightweight markdown renderer string -> JSX (with XSS protection)
const escapeHtml = (str) => {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
};

const renderMarkdown = (text) => {
    if (!text) return null;
    const parts = text.split(/(```[\s\S]*?```|`[^`]+`|\*\*[^*]+\*\*|\n\n)/g);
    return parts.map((part, i) => {
        if (part === '\n\n') return <br key={i} />;
        if (part.startsWith('```') && part.endsWith('```')) {
            const lines = part.slice(3, -3).split('\n');
            const code = lines.slice(1).join('\n').trim() || lines[0];
            return <pre key={i}><code>{escapeHtml(code)}</code></pre>;
        }
        if (part.startsWith('`') && part.endsWith('`')) {
            return <code key={i}>{escapeHtml(part.slice(1, -1))}</code>;
        }
        if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={i}>{escapeHtml(part.slice(2, -2))}</strong>;
        }
        return <span key={i}>{escapeHtml(part)}</span>;
    });
};

export default function App() {
    const [code, setCode] = useState('print("Hello World!")\n# Try making an intentional mistake here\n# my_var = 10 / 0');
    const [language, setLanguage] = useState('python');
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    // UI state
    const [fontSize, setFontSize] = useState(() => {
        const saved = parseInt(localStorage.getItem('fontSize') || '15', 10);
        return isNaN(saved) ? 15 : saved;
    });
    const [darkMode, setDarkMode] = useState(() => localStorage.getItem('darkMode') === 'true');
    const [isFullscreen, setIsFullscreen] = useState(false);
    const fileInputRef = React.useRef(null);

    // Result States
    const [output, setOutput] = useState('');
    const [errorMsg, setErrorMsg] = useState('');
    const [mentorFeedback, setMentorFeedback] = useState('');
    const [issues, setIssues] = useState([]);

    // persist settings
    React.useEffect(() => {
        localStorage.setItem('fontSize', fontSize);
    }, [fontSize]);

    React.useEffect(() => {
        document.documentElement.classList.toggle('light-mode', !darkMode);
        localStorage.setItem('darkMode', darkMode);
    }, [darkMode]);

    React.useEffect(() => {
        const handler = () => setIsFullscreen(!!document.fullscreenElement);
        document.addEventListener('fullscreenchange', handler);
        return () => document.removeEventListener('fullscreenchange', handler);
    }, []);

    const handleRun = async () => {
        setIsAnalyzing(true);
        setOutput('');
        setErrorMsg('');
        setMentorFeedback('AI Mentor analyzing...');
        setIssues([]);

        const API_URL = import.meta.env.VITE_API_URL || '';

        try {
            const response = await fetch(`${API_URL}/analyze`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code, language }),
            });

            let data;
            try {
                data = await response.json();
            } catch (jsonErr) {
                setErrorMsg("Invalid JSON response from server. Make sure the backend is running correctly.");
                setMentorFeedback('');
                setIsAnalyzing(false);
                return;
            }

            // Show issues and output immediately
            if (data.issues) {
                setIssues(data.issues);
            }

            if (data.execution) {
                const stdout = data.execution.stdout || '';
                const stderr = data.execution.stderr || '';

                setOutput(stdout);

                const hasErrorIssues = data.issues && data.issues.some(i => i.severity === 'error');
                if (data.execution.error || data.execution.returncode !== 0 || hasErrorIssues) {
                    setErrorMsg(stderr || data.execution.error?.message || "An execution error occurred.");
                }
            } else if (!data.ok) {
                setErrorMsg(data.error || "Analysis failed.");
            }

            // Fetch AI Mentor Feedback asynchronously in the background
            if (data.ai_mentor_feedback) {
                setMentorFeedback(data.ai_mentor_feedback);
            } else {
                setMentorFeedback('');
            }
        } catch (err) {
            setErrorMsg("Network error: Make sure the Python backend (app.py) is running on port 5000.");
            setMentorFeedback('');
        } finally {
            setIsAnalyzing(false);
        }
    };

    const increaseFont = () => setFontSize(f => Math.min(f + 1, 36));
    const decreaseFont = () => setFontSize(f => Math.max(f - 1, 8));
    const toggleDarkMode = () => setDarkMode(d => !d);
    const cycleLanguage = () => {
        const langs = ['python', 'javascript', 'java', 'c', 'cpp'];
        const idx = langs.indexOf(language);
        setLanguage(langs[(idx + 1) % langs.length]);
    };
    const clearOutput = () => {
        setOutput('');
        setErrorMsg('');
        setMentorFeedback('');
        setIssues([]);
    };
    const handleShare = async () => {
        const text = `Code:\n${code}\n\nLanguage: ${language}\nURL: ${window.location.href}`;
        if (navigator.share) {
            try { await navigator.share({ text }); } catch (_) { }
        } else {
            await navigator.clipboard.writeText(text);
            alert('Code copied to clipboard');
        }
    };
    const toggleFullscreen = () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().then(() => setIsFullscreen(true));
        } else {
            document.exitFullscreen().then(() => setIsFullscreen(false));
        }
    };
    const MAX_FILE_SIZE = 1024 * 1024; // 1MB limit

    const handleFileChange = (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;

        if (file.size > MAX_FILE_SIZE) {
            alert('File too large. Maximum size is 1MB.');
            return;
        }

        const ext = file.name.split('.').pop().toLowerCase();
        const map = { py: 'python', js: 'javascript', java: 'java', c: 'c', cpp: 'cpp', cc: 'cpp', cxx: 'cpp' };
        if (!map[ext]) {
            alert('Unsupported file type: ' + ext);
            return;
        }
        const reader = new FileReader();
        reader.onload = evt => {
            setCode(evt.target.result);
            setLanguage(map[ext]);
        };
        reader.readAsText(file);
    };

    const getPrismLanguage = (lang) => {
        if (lang === 'cpp' || lang === 'c') return Prism.languages.cpp || Prism.languages.clike;
        if (lang === 'java') return Prism.languages.java || Prism.languages.clike;
        if (lang === 'javascript') return Prism.languages.javascript;
        return Prism.languages.python;
    };

    return (
        <div className="app-container">
            {/* hidden file input for uploads */}
            <input
                type="file"
                accept=".py,.js,.java,.c,.cpp,.cc,.cxx"
                style={{ display: 'none' }}
                ref={fileInputRef}
                onChange={handleFileChange}
            />

            {/* Header Area */}
            <header className="header">
                <div className="header-title">
                    <CodeIcon />
                    <span>AI Code Mentor</span>
                </div>
                <div className="controls">
                    {/* font size */}
                    <button className="font-btn" title="Decrease font" onClick={decreaseFont}>A−</button>
                    <button className="font-btn" title="Increase font" onClick={increaseFont}>A+</button>
                    {/* theme toggle */}
                    <button title="Toggle dark/light" onClick={toggleDarkMode}>{darkMode ? <SunIcon /> : <MoonIcon />}</button>
                    {/* cycle language */}
                    <button title="Next language" onClick={cycleLanguage}><LanguageIcon /></button>
                    {/* upload */}
                    <button title="Upload code file" onClick={() => fileInputRef.current && fileInputRef.current.click()}><UploadIcon /></button>
                    <LanguageSelector language={language} onLanguageChange={setLanguage} />
                    <button
                        className="run-btn"
                        onClick={handleRun}
                        disabled={isAnalyzing || !code.trim()}
                    >
                        <PlayIcon />
                        {isAnalyzing ? "Running..." : "Run Code"}
                    </button>
                    {/* additional controls */}
                    <button title="Clear output" onClick={clearOutput}><TrashIcon /></button>
                    <button title="Toggle fullscreen" onClick={toggleFullscreen}><FullscreenIcon exit={isFullscreen} /></button>
                    <button title="Share" onClick={handleShare}><ShareIcon /></button>
                </div>
            </header>

            {/* Main Editor Grid */}
            <div className="main-content">
                {/* Editor Top Block */}
                <div className="editor-pane">
                    <div className="pane-header">
                        <CodeIcon /> Editor
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', overflowX: 'auto', backgroundColor: 'var(--bg-color)', minHeight: 0, display: 'flex' }} className="editor-container">
                        <div className="line-numbers" style={{ fontSize: fontSize + 'px' }}>
                            {code.split('\n').map((_, i) => (
                                <div key={i} style={{ height: '1.6em' }}>{i + 1}</div>
                            ))}
                        </div>
                        <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
                            <Editor
                                value={code}
                                onValueChange={(newCode) => {
                                    // Clean up extra line endings and normalize the code
                                    const cleanedCode = newCode.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
                                    setCode(cleanedCode);
                                }}
                                highlight={code => Prism.highlight(code, getPrismLanguage(language), language)}
                                padding={24}
                                style={{
                                    fontFamily: 'var(--font-mono)',
                                    fontSize: fontSize,
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
                            ) : mentorFeedback && mentorFeedback === "AI_MENTOR_DISABLED" ? (
                                <div className="placeholder-text">
                                    <SparklesIcon />
                                    AI Mentor is disabled.
                                    <br />
                                    (Set GEMINI_API_KEY in .env to enable)
                                </div>
                            ) : mentorFeedback && mentorFeedback === "AI_MENTOR_API_ERROR" ? (
                                <div className="placeholder-text" style={{ color: 'var(--warning)' }}>
                                    <SparklesIcon />
                                    AI Mentor API error.
                                    <br />
                                    Check if API key is valid and not rate-limited.
                                </div>
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
