export interface User {
  id: number;
  email: string;
  role: "student" | "teacher" | "admin";
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

// ponytail: mirrors the real POST /analyze payload exactly — top-level
// duplicates of meta.* were never read and only let the e2e mocks drift.
export interface AnalyzeResponse {
  success: boolean;
  output?: string;
  error?: string;
  meta?: AnalyzeMeta;
}

export type AuthTab = "login" | "register";
export type AiMentorStatus = "ok" | "disabled" | "quota_exceeded" | "bad_response" | "api_error";

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
  mjs: "javascript",
  jsx: "javascript",
  java: "java",
  c: "c",
  h: "c",
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
    body: "AI guidance is unavailable right now. Only the compiler and static checks are running.",
  },
  api_error: {
    title: "AI Mentor could not reach Gemini.",
    body: "The AI service is unreachable right now. Only the compiler and static checks are running.",
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

// Backend rejects code above 102400 characters; the file picker allows a
// larger read so the user gets a precise message instead of a server error.
export const MAX_CODE_CHARS = 102_400;
export const MAX_FILE_SIZE = 1024 * 1024;
