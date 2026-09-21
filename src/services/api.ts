import type { AuthForm, User } from "../types";

export const API_BASE = import.meta.env.VITE_API_URL || "";

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

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const cookies = document.cookie ? document.cookie.split("; ") : [];
  for (const c of cookies) {
    const idx = c.indexOf("=");
    if (idx < 0) continue;
    if (decodeURIComponent(c.slice(0, idx)) === name) {
      return decodeURIComponent(c.slice(idx + 1));
    }
  }
  return null;
}

// ponytail: read-only cookie lookup, zero extra requests (cookie set by
// set_refresh_cookies at login/register; cleared at logout).
export function getRefreshCsrfToken(): string | null {
  return getCookie("csrf_refresh_token");
}

function refreshCsrfHeaders(): Record<string, string> {
  const csrf = getRefreshCsrfToken();
  return csrf ? { "X-CSRF-TOKEN": csrf } : {};
}

export async function tryRefreshToken(signal?: AbortSignal): Promise<string | null> {
  try {
    const r = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      signal,
      credentials: "include",
      headers: { ...refreshCsrfHeaders() },
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

export async function analyzeCode(
  code: string,
  language: string,
  accessToken: string | null,
  csrfToken: string,
  signal?: AbortSignal,
): Promise<Response> {
  return fetch(`${API_BASE}/api/v1/analyze`, {
    method: "POST",
    signal,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
    },
    body: JSON.stringify({ code, language }),
  });
}

export function sessionRestore(signal?: AbortSignal): Promise<Response> {
  return fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    signal,
    credentials: "include",
    headers: { ...refreshCsrfHeaders() },
  });
}
