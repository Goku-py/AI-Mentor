import type { AuthForm, User, AnalyzeStatusResponse } from "../types";

export const API_BASE = import.meta.env.VITE_API_URL || "";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function fetchWithRetry(
  url: string,
  options: RequestInit,
  maxRetries = 3,
): Promise<Response> {
  const signal = options.signal;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    if (signal?.aborted) {
      throw new DOMException("The operation was aborted.", "AbortError");
    }

    const response = await fetch(url, options);

    if (response.status !== 503 || attempt === maxRetries) {
      return response;
    }

    if (signal?.aborted) {
      throw new DOMException("The operation was aborted.", "AbortError");
    }

    const backoff = Math.min(500 * 2 ** attempt, 2000);
    await delay(backoff);
  }

  // Fallback (should be unreachable due to the return inside the loop)
  return fetch(url, options);
}

export async function fetchCsrfToken(signal?: AbortSignal): Promise<string> {
  const r = await fetch(`${API_BASE}/api/v1/csrf-token`, {
    signal,
    credentials: "include",
  });
  if (!r.ok) return "";
  const data: { csrf_token?: string } = await r.json();
  return data.csrf_token || "";
}

export async function authFetch(
  path: string,
  body: AuthForm,
  csrfToken: string,
): Promise<{ ok: boolean; status: number; data: Record<string, unknown> }> {
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
    },
    body: JSON.stringify(body),
  }).then((r) => r.json().then((d) => ({ ok: r.ok, status: r.status, data: d })));
}

export async function tryRefreshToken(): Promise<string | null> {
  try {
    const r = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!r.ok) return null;
    const d: { access_token: string } = await r.json();
    return d.access_token;
  } catch {
    return null;
  }
}

export async function fetchUser(token: string): Promise<User | null> {
  try {
    const r = await fetch(`${API_BASE}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    });
    if (!r.ok) return null;
    const d: { user?: User } = await r.json();
    return d.user ?? null;
  } catch {
    return null;
  }
}

export async function logout(token: string | null): Promise<void> {
  await fetch(`${API_BASE}/api/v1/auth/logout`, {
    method: "POST",
    credentials: "include",
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  }).catch(() => {});
}

export async function submitAnalyzeJob(
  code: string,
  language: string,
  accessToken: string | null,
  csrfToken: string,
  signal?: AbortSignal,
  difficulty?: "beginner" | "intermediate" | "advanced",
): Promise<Response> {
  const body: Record<string, unknown> = { code, language };
  if (difficulty) {
    body.difficulty = difficulty;
  }

  return fetchWithRetry(
    `${API_BASE}/api/v1/analyze`,
    {
      method: "POST",
      signal,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
      },
      body: JSON.stringify(body),
    },
    3,
  );
}

export async function analyzeCode(
  code: string,
  language: string,
  accessToken: string | null,
  csrfToken: string,
  signal?: AbortSignal,
  difficulty?: "beginner" | "intermediate" | "advanced",
): Promise<Response> {
  return submitAnalyzeJob(code, language, accessToken, csrfToken, signal, difficulty);
}

export async function pollAnalyzeStatus(
  jobId: string,
  signal?: AbortSignal,
): Promise<AnalyzeStatusResponse> {
  const response = await fetch(`${API_BASE}/api/v1/analyze/status/${jobId}`, {
    signal,
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Status request failed with status ${response.status}`);
  }
  return (await response.json()) as AnalyzeStatusResponse;
}

export function sessionRestore(signal?: AbortSignal): Promise<Response> {
  return fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    signal,
    credentials: "include",
  });
}
