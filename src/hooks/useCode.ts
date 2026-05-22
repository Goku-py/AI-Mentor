import { useState, useEffect, useRef, useCallback } from "react";
import type {
  Issue,
  MismatchInfo,
  AnalyzeResponse,
  AiMentorStatus,
  ExecutionResult,
} from "../types";
import { DEFAULT_CODE, EXTENSION_MAP, SUPPORTED_LANGUAGES } from "../types";
import { analyzeCode, fetchCsrfToken } from "../services/api";

const inferAiMentorStatus = (feedback: string): AiMentorStatus => {
  if (feedback === "AI_MENTOR_DISABLED") return "disabled";
  if (feedback === "AI_MENTOR_QUOTA_EXCEEDED") return "quota_exceeded";
  if (feedback === "AI_MENTOR_BAD_RESPONSE") return "bad_response";
  if (feedback === "AI_MENTOR_API_ERROR" || feedback === "AI_MENTOR_API_DISABLED") return "api_error";
  return "ok";
};

const hasExecutionError = (execution: ExecutionResult | null | undefined): boolean => {
  if (!execution) return false;
  const error = execution.error;
  return Boolean(error && (typeof error !== "object" || Object.keys(error).length > 0));
};

const formatExecutionError = (execution: ExecutionResult | null | undefined, fallback = "An execution error occurred."): string => {
  if (!execution) return fallback;
  const error = execution.error;
  if (error?.type === "SandboxUnavailable") {
    return [
      "Sandbox unavailable: Docker is not available for code execution on this server.",
      error.explanation || "Production must run untrusted code inside Docker.",
      "For local development, start Docker and ensure the daemon is running.",
    ].join("\n");
  }
  if (error?.type === "ToolNotFound") {
    return [
      "Required language toolchain is not installed on this server.",
      error.explanation || "Install the runtime/compiler for the selected language and try again.",
    ].join("\n");
  }
  return execution.stderr || error?.message || fallback;
};

export interface UseCodeOptions {
  accessToken: string | null;
  csrfToken: string;
  tryRefreshToken: () => Promise<string | null>;
  onUnauthenticated: () => void;
}

export interface UseCodeReturn {
  code: string;
  language: string;
  isAnalyzing: boolean;
  errorLine: number | null;
  output: string;
  errorMsg: string;
  mentorFeedback: string;
  aiMentorStatus: AiMentorStatus;
  issues: Issue[];
  mismatchInfo: MismatchInfo | null;
  editorWrapperRef: React.RefObject<HTMLDivElement>;
  fileInputRef: React.RefObject<HTMLInputElement>;
  setCode: (code: string) => void;
  setLanguage: (lang: string) => void;
  handleLanguageChange: (newLang: string, keepCurrentCode?: boolean) => void;
  cycleLanguage: () => void;
  handleRun: () => Promise<void>;
  clearOutput: () => void;
  clearMismatch: () => void;
  handleShare: () => Promise<void>;
  handleFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

const MAX_FILE_SIZE = 1024 * 1024;

export function useCode(options: UseCodeOptions): UseCodeReturn {
  const { accessToken, csrfToken, tryRefreshToken, onUnauthenticated } = options;

  const [code, setCode] = useState<string>(DEFAULT_CODE.python);
  const [language, setLanguage] = useState<string>("python");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorLine, setErrorLine] = useState<number | null>(null);
  const [output, setOutput] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [mentorFeedback, setMentorFeedback] = useState("");
  const [aiMentorStatus, setAiMentorStatus] = useState<AiMentorStatus>("ok");
  const [issues, setIssues] = useState<Issue[]>([]);
  const [mismatchInfo, setMismatchInfo] = useState<MismatchInfo | null>(null);
  const editorWrapperRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Abort in-flight request on unmount
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  // Load Prism language on language change
  useEffect(() => {
    const loadPrismLanguage = async () => {
      if (language === "javascript") {
        await import("prismjs/components/prism-javascript");
      } else if (language === "python") {
        await import("prismjs/components/prism-python");
      } else if (language === "java") {
        await import("prismjs/components/prism-clike");
        await import("prismjs/components/prism-java");
      } else if (language === "c" || language === "cpp") {
        await import("prismjs/components/prism-clike");
        await import("prismjs/components/prism-c");
        await import("prismjs/components/prism-cpp");
      }
    };
    loadPrismLanguage();
  }, [language]);

  // Scroll to error line
  useEffect(() => {
    if (errorLine == null || !editorWrapperRef.current) return;

    const textarea = editorWrapperRef.current.querySelector("textarea.code-textarea") as HTMLTextAreaElement | null;
    if (!textarea) return;

    const computed = window.getComputedStyle(textarea);
    const lineHeight = parseFloat(computed.lineHeight) || 16 * 1.6;
    const targetScrollTop = Math.max(
      (errorLine - 1) * lineHeight - (textarea.clientHeight / 2) + (lineHeight / 2),
      0,
    );

    textarea.scrollTop = targetScrollTop;
  }, [errorLine]);

  const handleRun = useCallback(async () => {
    // Abort any previous in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsAnalyzing(true);
    setOutput("");
    setErrorMsg("");
    setMentorFeedback("AI Mentor analyzing...");
    setAiMentorStatus("ok");
    setIssues([]);
    setErrorLine(null);
    setMismatchInfo(null);

    try {
      let token = csrfToken;
      if (!token) {
        token = await fetchCsrfToken(controller.signal);
      }
      let response = await analyzeCode(code, language, accessToken, token, controller.signal);

      if (response.status === 401 && accessToken) {
        const newToken = await tryRefreshToken();
        if (!newToken) {
          onUnauthenticated();
        }
        response = await analyzeCode(code, language, newToken || null, token, controller.signal);
      }

      let data: AnalyzeResponse;
      try {
        data = (await response.json()) as AnalyzeResponse;
      } catch {
        setErrorMsg("Invalid JSON response from server.");
        setMentorFeedback("");
        setIsAnalyzing(false);
        return;
      }

      const meta = data.meta;

      if (meta?.issues) setIssues(meta.issues);

      if (meta?.mismatch) {
        setMismatchInfo({
          selected: meta.language || language,
          detected: meta.mismatch.detected || "unknown",
        });
        setOutput(data.output || "");
        setErrorMsg("");
      }

      if (!meta?.mismatch && meta?.execution) {
        const stdout = meta.execution.stdout || "";
        setOutput(stdout);

        const hasErrorIssues = meta?.issues?.some((i) => i.severity === "error") ?? false;
        if (hasExecutionError(meta.execution) || (meta.execution.returncode ?? 0) !== 0 || hasErrorIssues) {
          setErrorMsg(formatExecutionError(meta.execution));
        }
      } else if (!meta?.mismatch && !data.success) {
        setErrorMsg(data.error || "Analysis failed.");
      }

      const apiErrorLine = meta?.execution?.error?.line;
      if (apiErrorLine != null) {
        const parsedLine = Number(apiErrorLine);
        if (Number.isFinite(parsedLine) && parsedLine > 0) {
          setErrorLine(Math.floor(parsedLine));
        }
      }

      if (meta?.ai_mentor_feedback) {
        setMentorFeedback(meta.ai_mentor_feedback);
        setAiMentorStatus(
          (meta.ai_mentor_status as AiMentorStatus) || inferAiMentorStatus(meta.ai_mentor_feedback),
        );
      } else {
        setMentorFeedback("");
        setAiMentorStatus((meta?.ai_mentor_status as AiMentorStatus) || "ok");
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setErrorMsg("Network error: Could not reach the server.");
      setMentorFeedback("");
    } finally {
      if (!controller.signal.aborted) {
        setIsAnalyzing(false);
      }
    }
  }, [code, language, accessToken, csrfToken, tryRefreshToken, onUnauthenticated]);

  const handleLanguageChange = useCallback((newLang: string, keepCurrentCode = false) => {
    setLanguage(newLang);
    if (!keepCurrentCode) {
      setCode(DEFAULT_CODE[newLang] || "");
    }
  }, []);

  const cycleLanguage = useCallback(() => {
    const langs = SUPPORTED_LANGUAGES.map((l) => l.id);
    const idx = langs.indexOf(language as (typeof SUPPORTED_LANGUAGES)[number]["id"]);
    handleLanguageChange(langs[(idx + 1) % langs.length]);
  }, [language, handleLanguageChange]);

  const clearOutput = useCallback(() => {
    setOutput("");
    setErrorMsg("");
    setMentorFeedback("");
    setAiMentorStatus("ok");
    setIssues([]);
  }, []);

  const clearMismatch = useCallback(() => {
    setMismatchInfo(null);
  }, []);

  const handleShare = useCallback(async () => {
    const text = `Code:\n${code}\n\nLanguage: ${language}\nURL: ${window.location.href}`;
    if (navigator.share) {
      try { await navigator.share({ text }); } catch { /* user cancelled */ }
    } else {
      await navigator.clipboard.writeText(text);
      alert("Code copied to clipboard");
    }
  }, [code, language]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > MAX_FILE_SIZE) {
      alert("File too large. Maximum size is 1MB.");
      return;
    }

    const ext = file.name.split(".").pop()?.toLowerCase() || "";
    const detectedLang = EXTENSION_MAP[ext];
    if (!detectedLang) {
      alert("Unsupported file type: " + ext);
      return;
    }
    const reader = new FileReader();
    reader.onload = (evt: ProgressEvent<FileReader>) => {
      if (typeof evt.target?.result === "string") {
        setCode(evt.target.result);
        setLanguage(detectedLang);
      }
    };
    reader.readAsText(file);
  }, []);

  return {
    code,
    language,
    isAnalyzing,
    errorLine,
    output,
    errorMsg,
    mentorFeedback,
    aiMentorStatus,
    issues,
    mismatchInfo,
    editorWrapperRef,
    fileInputRef,
    setCode,
    setLanguage,
    handleLanguageChange,
    cycleLanguage,
    handleRun,
    clearOutput,
    clearMismatch,
    handleShare,
    handleFileChange,
  };
}

export { inferAiMentorStatus, hasExecutionError, formatExecutionError };
