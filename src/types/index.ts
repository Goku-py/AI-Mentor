export interface User {
  id: number;
  email: string;
  role: "student" | "admin";
}

export interface AuthForm {
  email: string;
  password: string;
}

export interface Issue {
  line?: number;
  severity: "error" | "warning" | "info";
  code?: string;
  message: string;
}

export interface ExecutionError {
  type?: string;
  message?: string;
  line?: number;
  explanation?: string;
  suggestions?: string[];
}

export interface ExecutionResult {
  stdout?: string;
  stderr?: string;
  returncode?: number;
  error?: ExecutionError;
  timed_out?: boolean;
  tool_missing?: boolean;
}

export interface MismatchInfo {
  selected: string;
  detected: string;
}

export interface AnalyzeMeta {
  language: string;
  executionTimeMs?: number;
  issues?: Issue[];
  ai_mentor_feedback?: string;
  ai_mentor_status?: string;
  mismatch?: MismatchInfo;
  execution?: ExecutionResult;
}

export interface AnalyzeResponse {
  success: boolean;
  output?: string;
  error?: string;
  issues?: Issue[];
  mismatch?: MismatchInfo;
  language?: string;
  detected_language?: string;
  execution?: ExecutionResult;
  ai_mentor_feedback?: string;
  ai_mentor_status?: string;
  ok?: boolean;
  meta?: AnalyzeMeta;
}

export interface AnalyzeJobResponse {
  ok: boolean;
  job_id: string;
  status: string;
  poll_url: string;
}

export interface AnalyzeStatusResponse {
  ok: boolean;
  job_id: string;
  status: "queued" | "started" | "finished" | "failed";
  result?: AnalyzeResponse;
  error?: string;
}

export type AuthTab = "login" | "register";
export type AiMentorStatus = "ok" | "disabled" | "quota_exceeded" | "bad_response" | "api_error";
export type Difficulty = "beginner" | "intermediate" | "advanced";

export const DEFAULT_DIFFICULTY: Difficulty = "beginner";

export const DIFFICULTIES: { id: Difficulty; name: string }[] = [
  { id: "beginner", name: "Beginner" },
  { id: "intermediate", name: "Intermediate" },
  { id: "advanced", name: "Advanced" },
] as const;

export const SUPPORTED_LANGUAGES = [
  { id: "python", name: "Python" },
  { id: "javascript", name: "JavaScript" },
  { id: "java", name: "Java" },
  { id: "c", name: "C" },
  { id: "cpp", name: "C++" },
] as const;

export type LanguageId = (typeof SUPPORTED_LANGUAGES)[number]["id"];

export const EXTENSION_MAP: Record<string, string> = {
  py: "python",
  js: "javascript",
  java: "java",
  c: "c",
  cpp: "cpp",
  cc: "cpp",
  cxx: "cpp",
};

export const DEFAULT_CODE: Record<string, string> = {
  python: "print(\"Hello World!\")\n# Start coding below",
  javascript: "console.log(\"Hello World!\");\n// Start coding below",
  java: "public class Main {\n    public static void main(String[] args) {\n        System.out.println(\"Hello World!\");\n    }\n}",
  c: "#include <stdio.h>\n\nint main() {\n    printf(\"Hello World!\\n\");\n    return 0;\n}",
  cpp: "#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << \"Hello World!\" << endl;\n    return 0;\n}",
};

export const aiMentorStatusCopy: Record<string, { title: string; body: string }> = {
  disabled: {
    title: "AI Mentor is disabled.",
    body: "Set GEMINI_API_KEY in the server environment to enable AI guidance.",
  },
  api_error: {
    title: "AI Mentor could not reach Gemini.",
    body: "Check GEMINI_API_KEY, GEMINI_MODEL, and whether the Gemini API is enabled for the key.",
  },
  quota_exceeded: {
    title: "AI Mentor quota is exhausted.",
    body: "Use the compiler output for now, then try again after the quota window resets.",
  },
  bad_response: {
    title: "AI Mentor returned an unreadable response.",
    body: "The code still ran; retry once, or check the server logs if this keeps happening.",
  },
};
