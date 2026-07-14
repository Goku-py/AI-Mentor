import { useState, useEffect, useRef, useCallback } from "react";
import type {
  Issue,
  MismatchInfo,
  AnalyzeResponse,
  AnalyzeJobResponse,
  AnalyzeStatusResponse,
  AiMentorStatus,
  ExecutionResult,
  Difficulty,
} from "../types";
import { DEFAULT_CODE, EXTENSION_MAP, SUPPORTED_LANGUAGES, DEFAULT_DIFFICULTY, DIFFICULTIES } from "../types";
import { submitAnalyzeJob, pollAnalyzeStatus } from "../services/api";
import { showToast } from "../components/Toast";

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

function pollDelay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("The operation was aborted.", "AbortError"));
    };
    if (signal.aborted) {
      onAbort();
      return;
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

export interface UseCodeOptions {
  accessToken: string | null;
  csrfToken: string;
  tryRefreshToken: () => Promise<string | null>;
  refreshCsrfToken: () => Promise<string>;
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
  fileInputRef: React.RefObject<HTMLInputElement>;
  setCode: (code: string) => void;
  setLanguage: (lang: string) => void;
  handleLanguageChange: (newLang: string, keepCurrentCode?: boolean) => void;
  cycleLanguage: () => void;
  difficulty: Difficulty;
  setDifficulty: (difficulty: Difficulty) => void;
  cycleDifficulty: () => void;
  handleRun: () => Promise<void>;
  clearOutput: () => void;
  clearMismatch: () => void;
  handleShare: () => Promise<void>;
  handleFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

const MAX_FILE_SIZE = 1024 * 1024;

export function useCode(options: UseCodeOptions): UseCodeReturn {
  const { accessToken, csrfToken, tryRefreshToken, refreshCsrfToken, onUnauthenticated } = options;

  const [code, setCode] = useState<string>(DEFAULT_CODE.python);
  const [language, setLanguage] = useState<string>("python");
  const [difficulty, setDifficulty] = useState<Difficulty>(DEFAULT_DIFFICULTY);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorLine, setErrorLine] = useState<number | null>(null);
  const [output, setOutput] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [mentorFeedback, setMentorFeedback] = useState("");
  const [aiMentorStatus, setAiMentorStatus] = useState<AiMentorStatus>("ok");
  const [issues, setIssues] = useState<Issue[]>([]);
  const [mismatchInfo, setMismatchInfo] = useState<MismatchInfo | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Abort in-flight request on unmount
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const handleRun = useCallback(async () => {
    // Abort any previous in-flight request or polling loop
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

    const looksLikeCsrfError = async (response: Response): Promise<boolean> => {
      if (response.status !== 403) return false;
      try {
        const clone = response.clone();
        const data = (await clone.json()) as Record<string, unknown>;
        const text = JSON.stringify(data).toLowerCase();
        return text.includes("csrf") || text.includes("forbidden");
      } catch {
        const text = await response.clone().text();
        return text.toLowerCase().includes("csrf");
      }
    };

    const renderAnalyzeResult = (data: AnalyzeResponse) => {
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
    };

    const getStatusMessage = (status: string): string => {
      if (status === "queued") return "Queued...";
      if (status === "started") return "Running your code...";
      return "Analyzing...";
    };

    try {
      let response = await submitAnalyzeJob(
        code,
        language,
        accessToken,
        csrfToken,
        controller.signal,
        difficulty,
      );

      if (await looksLikeCsrfError(response)) {
        const newCsrfToken = await refreshCsrfToken();
        response = await submitAnalyzeJob(
          code,
          language,
          accessToken,
          newCsrfToken,
          controller.signal,
          difficulty,
        );
      }

      if (response.status === 401 && accessToken) {
        const newToken = await tryRefreshToken();
        if (!newToken) {
          onUnauthenticated();
        }
        response = await submitAnalyzeJob(
          code,
          language,
          newToken || null,
          csrfToken,
          controller.signal,
          difficulty,
        );
      }

      if (response.status === 202) {
        let jobData: AnalyzeJobResponse;
        try {
          jobData = (await response.json()) as AnalyzeJobResponse;
        } catch {
          setErrorMsg("Invalid JSON response from server.");
          setMentorFeedback("");
          setIsAnalyzing(false);
          return;
        }

        const jobId = jobData.job_id;
        const maxAttempts = 45;
        setMentorFeedback(getStatusMessage(jobData.status));

        for (let attempt = 0; attempt < maxAttempts; attempt++) {
          if (controller.signal.aborted) {
            throw new DOMException("The operation was aborted.", "AbortError");
          }
          await pollDelay(1000, controller.signal);

          const status = (await pollAnalyzeStatus(jobId, controller.signal)) as AnalyzeStatusResponse;
          setMentorFeedback(getStatusMessage(status.status));

          if (status.status === "finished") {
            if (status.result) {
              renderAnalyzeResult(status.result);
            } else {
              setErrorMsg("Analysis finished but no result was returned.");
            }
            setIsAnalyzing(false);
            return;
          }

          if (status.status === "failed") {
            setErrorMsg(status.error || "Analysis failed.");
            setMentorFeedback("");
            setIsAnalyzing(false);
            return;
          }
        }

        setErrorMsg("Analysis timed out. Please try again.");
        setMentorFeedback("");
        setIsAnalyzing(false);
        return;
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

      renderAnalyzeResult(data);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setErrorMsg("Network error: Could not reach the server.");
      setMentorFeedback("");
    } finally {
      if (!controller.signal.aborted) {
        setIsAnalyzing(false);
      }
    }
  }, [code, language, difficulty, accessToken, csrfToken, tryRefreshToken, refreshCsrfToken, onUnauthenticated]);

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

  const cycleDifficulty = useCallback(() => {
    const levels = DIFFICULTIES.map((d) => d.id);
    const idx = levels.indexOf(difficulty);
    setDifficulty(levels[(idx + 1) % levels.length]);
  }, [difficulty]);

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
      showToast("Code copied to clipboard");
    }
  }, [code, language]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > MAX_FILE_SIZE) {
      showToast("File too large. Maximum size is 1MB.");
      return;
    }

    const ext = file.name.split(".").pop()?.toLowerCase() || "";
    const detectedLang = EXTENSION_MAP[ext];
    if (!detectedLang) {
      showToast("Unsupported file type: " + ext);
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
    fileInputRef,
    setCode,
    setLanguage,
    handleLanguageChange,
    cycleLanguage,
    difficulty,
    setDifficulty,
    cycleDifficulty,
    handleRun,
    clearOutput,
    clearMismatch,
    handleShare,
    handleFileChange,
  };
}

export { inferAiMentorStatus, hasExecutionError, formatExecutionError };
