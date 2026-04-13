import React, { useState, useEffect } from 'react';
import Editor from 'react-simple-code-editor';
import Prism from 'prismjs';
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
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9h6V3" /><path d="M21 9h-6V3" /><path d="M3 15h6v6" /><path d="M21 15h-6v6" /></svg>
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

// Lightweight markdown renderer string -> JSX.
// XSS protection is provided natively by React: all string children inside
// JSX are text nodes — never interpreted as HTML.
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

const DEFAULT_CODE = {
    python: 'print("Hello World!")\n# Start coding below',
    javascript: 'console.log("Hello World!");\n// Start coding below',
    java: 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello World!");\n    }\n}',
    c: '#include <stdio.h>\n\nint main() {\n    printf("Hello World!\\n");\n    return 0;\n}',
    cpp: '#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << "Hello World!" << endl;\n    return 0;\n}',
};

export default function App() {
    const [code, setCode] = useState(DEFAULT_CODE.python);
    const [language, setLanguage] = useState('python');
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [errorLine, setErrorLine] = useState(null);
    const editorWrapperRef = React.useRef(null);

    // --- Auth state ---
    // accessToken lives only in React memory (never localStorage) = XSS-safe.
    // The refresh token is in an httpOnly cookie managed entirely by the browser.
    const [user, setUser] = useState(null);          // { id, email, role } or null
    const [accessToken, setAccessToken] = useState(null);
    const [showAuthModal, setShowAuthModal] = useState(false);
    const [authTab, setAuthTab] = useState('login'); // 'login' | 'register'
    const [authForm, setAuthForm] = useState({ email: '', password: '' });
    const [authError, setAuthError] = useState('');
    const [authLoading, setAuthLoading] = useState(false);

    // Gap 4: CSRF token — fetched once on mount, sent on every POST
    const [csrfToken, setCsrfToken] = useState('');

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
    const [mismatchInfo, setMismatchInfo] = useState(null);
    const [repoUrl, setRepoUrl] = useState('');

    // persist settings
    React.useEffect(() => {
        localStorage.setItem('fontSize', fontSize);
    }, [fontSize]);

    React.useEffect(() => {
        document.documentElement.classList.toggle('light-mode', !darkMode);
        localStorage.setItem('darkMode', darkMode);
    }, [darkMode]);

    // Gap 4: Fetch CSRF token once on mount so all subsequent POSTs are protected
    useEffect(() => {
        const API_URL = import.meta.env.VITE_API_URL || '';
        fetch(`${API_URL}/api/v1/csrf-token`, { credentials: 'include' })
            .then(r => r.ok ? r.json() : Promise.reject(r))
            .then(data => setCsrfToken(data.csrf_token || ''))
            .catch(() => { /* non-fatal */ });
    }, []);

    // Auth: Try to silently restore session on page load via the httpOnly refresh cookie.
    // If the cookie is present and valid, we get a new access token without the user
    // needing to log in again.
    useEffect(() => {
        const urlParams = new URLSearchParams(window.location.search);
        const urlToken = urlParams.get('token');
        const API_URL = import.meta.env.VITE_API_URL || '';

        if (urlToken) {
            setAccessToken(urlToken);
            window.history.replaceState({}, document.title, window.location.pathname);
            fetch(`${API_URL}/api/v1/auth/me`, {
                headers: { 'Authorization': `Bearer ${urlToken}` },
                credentials: 'include',
            })
            .then(r => r.ok ? r.json() : null)
            .then(d => { if(d && d.ok) setUser(d.user); });
            return;
        }

        fetch(`${API_URL}/api/v1/auth/refresh`, {
            method: 'POST',
            credentials: 'include',
        })
            .then(r => r.ok ? r.json() : Promise.reject(r))
            .then(async data => {
                setAccessToken(data.access_token);
                // Load user profile
                const me = await fetch(`${API_URL}/api/v1/auth/me`, {
                    headers: { 'Authorization': `Bearer ${data.access_token}` },
                    credentials: 'include',
                });
                if (me.ok) {
                    const meData = await me.json();
                    setUser(meData.user);
                }
            })
            .catch(() => { /* No valid session — user must log in */ });
    }, []);

    // Auth: helper to post to auth endpoints
    const authFetch = (path, body) => {
        const API_URL = import.meta.env.VITE_API_URL || '';
        return fetch(`${API_URL}${path}`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
            },
            body: JSON.stringify(body),
        }).then(r => r.json().then(d => ({ ok: r.ok, status: r.status, data: d })));
    };

    // Auth: silent token refresh (called automatically if access token expires mid-session)
    const tryRefreshToken = async () => {
        const API_URL = import.meta.env.VITE_API_URL || '';
        try {
            const r = await fetch(`${API_URL}/api/v1/auth/refresh`, {
                method: 'POST', credentials: 'include',
            });
            if (!r.ok) return null;
            const d = await r.json();
            setAccessToken(d.access_token);
            return d.access_token;
        } catch { return null; }
    };

    // Auth: handle login or register form submission
    const handleAuthSubmit = async (e) => {
        e.preventDefault();
        setAuthError('');
        if (!authForm.email || !authForm.password) {
            setAuthError('Please fill in all fields.');
            return;
        }
        setAuthLoading(true);
        const path = authTab === 'login' ? '/api/v1/auth/login' : '/api/v1/auth/register';
        const result = await authFetch(path, authForm);
        setAuthLoading(false);
        if (!result.ok) {
            setAuthError(result.data?.error || 'Something went wrong. Please try again.');
            return;
        }
        setUser(result.data.user);
        setAccessToken(result.data.access_token);
        setShowAuthModal(false);
        setAuthForm({ email: '', password: '' });
    };

    // Auth: logout
    const handleLogout = async () => {
        const API_URL = import.meta.env.VITE_API_URL || '';
        await fetch(`${API_URL}/api/v1/auth/logout`, {
            method: 'POST',
            credentials: 'include',
            headers: { ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}) },
        }).catch(() => {});
        setUser(null);
        setAccessToken(null);
    };

    useEffect(() => {
        const handler = () => setIsFullscreen(!!document.fullscreenElement);
        document.addEventListener('fullscreenchange', handler);
        return () => document.removeEventListener('fullscreenchange', handler);
    }, []);

    useEffect(() => {
        const loadPrismLanguage = async () => {
            if (language === 'javascript') {
                await import('prismjs/components/prism-javascript');
            } else if (language === 'python') {
                await import('prismjs/components/prism-python');
            } else if (language === 'java') {
                await import('prismjs/components/prism-clike');
                await import('prismjs/components/prism-java');
            } else if (language === 'c' || language === 'cpp') {
                await import('prismjs/components/prism-clike');
                await import('prismjs/components/prism-c');
                await import('prismjs/components/prism-cpp');
            }
            // Force re-render to apply syntax highlighting
            setCode(c => c + ' ');
            setTimeout(() => setCode(c => c.slice(0, -1)), 0);
        };
        loadPrismLanguage();
    }, [language]);

    useEffect(() => {
        if (errorLine == null || !editorWrapperRef.current) return;

        const textarea = editorWrapperRef.current.querySelector('textarea.code-textarea');
        if (!textarea) return;

        const computed = window.getComputedStyle(textarea);
        const lineHeight = parseFloat(computed.lineHeight) || fontSize * 1.6;
        const targetScrollTop = Math.max(
            (errorLine - 1) * lineHeight - (textarea.clientHeight / 2) + (lineHeight / 2),
            0
        );

        textarea.scrollTop = targetScrollTop;
    }, [errorLine, fontSize]);

    const handleAnalyzeRepo = async () => {
        setIsAnalyzing(true);
        setOutput('');
        setErrorMsg('');
        setMentorFeedback('Analyzing GitHub Repository... This takes up to 45 seconds.');
        setIssues([]);
        setErrorLine(null);
        setMismatchInfo(null);

        const API_URL = import.meta.env.VITE_API_URL || '';
        try {
            const response = await fetch(`${API_URL}/api/v1/analyze/github`, {
                method: "POST",
                credentials: 'include',
                headers: {
                    "Content-Type": "application/json",
                    ...(accessToken ? { "Authorization": `Bearer ${accessToken}` } : {}),
                    ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
                },
                body: JSON.stringify({ repo_url: repoUrl }),
            });
            const data = await response.json();
            if (data.ok) {
                setMentorFeedback(data.ai_mentor_feedback || "Done.");
            } else {
                setErrorMsg(data.error || "Analysis failed.");
                setMentorFeedback('');
            }
        } catch (err) {
            setErrorMsg("Network error: Make sure the Python backend (app.py) is running on port 5000.");
            setMentorFeedback('');
        } finally {
            setIsAnalyzing(false);
        }
    };

    const handleRun = async () => {
        setIsAnalyzing(true);
        setOutput('');
        setErrorMsg('');
        setMentorFeedback('AI Mentor analyzing...');
        setIssues([]);
        setErrorLine(null);
        setMismatchInfo(null);

        const API_URL = import.meta.env.VITE_API_URL || '';

        // Helper: run the actual fetch (token is optional — guests have no token)
        const doFetch = (token) => fetch(`${API_URL}/api/v1/analyze`, {
            method: "POST",
            credentials: 'include',
            headers: {
                "Content-Type": "application/json",
                // Only send Authorization when user is logged in
                ...(token ? { "Authorization": `Bearer ${token}` } : {}),
                ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
            },
            body: JSON.stringify({ code, language }),
        });

        try {
            let response = await doFetch(accessToken);

            // If 401 and we had a token, try a silent refresh then retry once
            if (response.status === 401 && accessToken) {
                const newToken = await tryRefreshToken();
                if (!newToken) {
                    setUser(null);
                    setAccessToken(null);
                }
                // Retry without token (guest fallback) if refresh fails
                response = await doFetch(newToken || null);
            }

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

            if (data.mismatch) {
                setMismatchInfo({
                    selected: data.language || language,
                    detected: data.detected_language || 'unknown'
                });
                setOutput(data.output || '');
                setErrorMsg('');
            }

            if (!data.mismatch && data.execution) {
                const stdout = data.execution.stdout || '';
                const stderr = data.execution.stderr || '';

                setOutput(stdout);

                const hasErrorIssues = data.issues && data.issues.some(i => i.severity === 'error');
                if (data.execution.error || data.execution.returncode !== 0 || hasErrorIssues) {
                    setErrorMsg(stderr || data.execution.error?.message || "An execution error occurred.");
                }
            } else if (!data.mismatch && !data.ok) {
                setErrorMsg(data.error || "Analysis failed.");
            }

            const apiErrorLine = data?.result?.error?.line;
            if (apiErrorLine != null) {
                const parsedLine = Number(apiErrorLine);
                if (Number.isFinite(parsedLine) && parsedLine > 0) {
                    setErrorLine(Math.floor(parsedLine));
                }
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
    const handleLanguageChange = (newLang, keepCurrentCode = false) => {
        setLanguage(newLang);
        if (!keepCurrentCode) {
            setCode(DEFAULT_CODE[newLang] || '');
        }
    };

    const cycleLanguage = () => {
        const langs = ['python', 'javascript', 'java', 'c', 'cpp'];
        const idx = langs.indexOf(language);
        handleLanguageChange(langs[(idx + 1) % langs.length]);
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
            // File upload: keep the file's content, only change language
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
            {/* Auth Modal */}
            {showAuthModal && (
                <div className="auth-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowAuthModal(false); }}>
                    <div className="auth-modal" role="dialog" aria-modal="true" aria-label="Sign in">
                        <button className="auth-modal-close" onClick={() => setShowAuthModal(false)} aria-label="Close">✕</button>
                        <div className="auth-modal-logo">
                            <CodeIcon />
                            <span>AI Code Mentor</span>
                        </div>
                        <div className="auth-tabs">
                            <button
                                className={`auth-tab ${authTab === 'login' ? 'active' : ''}`}
                                onClick={() => { setAuthTab('login'); setAuthError(''); }}
                            >Sign In</button>
                            <button
                                className={`auth-tab ${authTab === 'register' ? 'active' : ''}`}
                                onClick={() => { setAuthTab('register'); setAuthError(''); }}
                            >Create Account</button>
                        </div>
                        <form className="auth-form" onSubmit={handleAuthSubmit} noValidate>
                            <div className="auth-field">
                                <label htmlFor="auth-email">Email address</label>
                                <input
                                    id="auth-email"
                                    type="email"
                                    autoComplete="email"
                                    placeholder="you@example.com"
                                    value={authForm.email}
                                    onChange={e => setAuthForm(f => ({ ...f, email: e.target.value }))}
                                    disabled={authLoading}
                                    required
                                />
                            </div>
                            <div className="auth-field">
                                <label htmlFor="auth-password">Password</label>
                                <input
                                    id="auth-password"
                                    type="password"
                                    autoComplete={authTab === 'login' ? 'current-password' : 'new-password'}
                                    placeholder={authTab === 'register' ? 'Min 8 chars, 1 digit or symbol' : '••••••••'}
                                    value={authForm.password}
                                    onChange={e => setAuthForm(f => ({ ...f, password: e.target.value }))}
                                    disabled={authLoading}
                                    required
                                />
                            </div>
                            {authError && (
                                <div className="auth-error" role="alert">{authError}</div>
                            )}
                            <button type="submit" className="auth-submit" disabled={authLoading}>
                                {authLoading ? 'Please wait…' : (authTab === 'login' ? 'Sign In' : 'Create Account')}
                            </button>
                        </form>
                        
                        <div className="auth-divider">
                            <span>OR</span>
                        </div>
                        <button type="button" className="auth-github-btn" onClick={() => {
                            window.location.href = `${import.meta.env.VITE_API_URL || ''}/api/v1/auth/github/login`;
                        }}>
                            Login with GitHub
                        </button>

                        <p className="auth-switch">
                            {authTab === 'login' ? (
                                <>No account? <button onClick={() => { setAuthTab('register'); setAuthError(''); }}>Create one free</button></>
                            ) : (
                                <>Already have one? <button onClick={() => { setAuthTab('login'); setAuthError(''); }}>Sign in</button></>
                            )}
                        </p>
                    </div>
                </div>
            )}

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
                    <LanguageSelector language={language} onLanguageChange={handleLanguageChange} />
                    <button
                        className="run-btn"
                        onClick={handleRun}
                        disabled={isAnalyzing || !code.trim() || !!repoUrl.trim()}
                    >
                        <PlayIcon />
                        {isAnalyzing && !repoUrl.trim() ? "Running..." : "Run"}
                    </button>
                    <input 
                        type="url" 
                        placeholder="https://github.com/..." 
                        value={repoUrl} 
                        onChange={e => setRepoUrl(e.target.value)} 
                        className="repo-input"
                        title="Enter GitHub Repository URL to statically analyze its architecture"
                    />
                    <button
                        className="run-btn"
                        onClick={handleAnalyzeRepo}
                        disabled={isAnalyzing || !repoUrl.trim()}
                        title="Analyze Repository Architecture"
                    >
                         <SparklesIcon />
                         {isAnalyzing && !!repoUrl.trim() ? "..." : "Repo"}
                    </button>
                    {/* additional controls */}
                    <button title="Clear output" onClick={clearOutput}><TrashIcon /></button>
                    <button title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'} onClick={toggleFullscreen}><FullscreenIcon exit={isFullscreen} /></button>
                    <button title="Share" onClick={handleShare}><ShareIcon /></button>

                    {/* Auth: user badge or login button */}
                    {user ? (
                        <div className="auth-user-badge">
                            <span className="auth-avatar">{user.email[0].toUpperCase()}</span>
                            <span className="auth-email" title={user.email}>{user.email.split('@')[0]}</span>
                            <span className={`auth-role-pill auth-role-${user.role}`}>{user.role}</span>
                            <button className="auth-logout-btn" onClick={handleLogout} title="Sign out">Sign out</button>
                        </div>
                    ) : (
                        <button
                            className="auth-login-btn"
                            onClick={() => { setShowAuthModal(true); setAuthTab('login'); }}
                        >
                            Sign in
                        </button>
                    )}
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
                        <div className="line-numbers" style={{ fontSize: fontSize + 'px', minHeight: '100%' }}>
                            {code.split('\n').map((_, i) => (
                                <div key={i} style={{ height: '1.6em' }}>{i + 1}</div>
                            ))}
                        </div>
                        <div style={{ flex: 1, position: 'relative', minHeight: 0 }} ref={editorWrapperRef}>
                            <Editor
                                value={code}
                                onValueChange={(newCode) => {
                                    // Clean up extra line endings and normalize the code
                                    const cleanedCode = newCode.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
                                    setCode(cleanedCode);
                                }}
                                highlight={code => {
                                    const grammar = getPrismLanguage(language);
                                    const highlighted = grammar ? Prism.highlight(code, grammar, language) : code;
                                    return highlighted
                                        .split('\n')
                                        .map((line, idx) => `<span class="${errorLine === idx + 1 ? 'error-line' : ''}">${line || ' '}</span>`)
                                        .join('\n');
                                }}
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
                            {mismatchInfo && (
                                <div
                                    style={{
                                        marginBottom: '1rem',
                                        padding: '0.75rem',
                                        border: '1px solid #facc15',
                                        backgroundColor: '#fef9c3',
                                        color: '#713f12',
                                        borderRadius: '8px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                        gap: '0.75rem'
                                    }}
                                >
                                    <span>
                                        ⚠️ Language Mismatch: You selected {mismatchInfo.selected} but your code looks like {mismatchInfo.detected}.
                                    </span>
                                    {['python', 'javascript', 'java', 'c', 'cpp'].includes(mismatchInfo.detected) && mismatchInfo.detected !== language && (
                                        <button
                                            onClick={() => {
                                                handleLanguageChange(mismatchInfo.detected, true);
                                                setMismatchInfo(null);
                                            }}
                                            style={{
                                                border: '1px solid #ca8a04',
                                                backgroundColor: '#fef08a',
                                                color: '#713f12',
                                                borderRadius: '6px',
                                                padding: '0.35rem 0.65rem',
                                                cursor: 'pointer',
                                                fontWeight: 600,
                                                whiteSpace: 'nowrap'
                                            }}
                                        >
                                            Switch to {mismatchInfo.detected}
                                        </button>
                                    )}
                                </div>
                            )}

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
