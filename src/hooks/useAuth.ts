import { useState, useEffect, useCallback } from "react";
import type { User, AuthForm, AuthTab } from "../types";
import {
  fetchCsrfToken,
  authFetch,
  tryRefreshToken as apiTryRefresh,
  fetchUser,
  logout as apiLogout,
  sessionRestore,
} from "../services/api";

export interface UseAuthReturn {
  user: User | null;
  accessToken: string | null;
  csrfToken: string;
  showAuthModal: boolean;
  authTab: AuthTab;
  authForm: AuthForm;
  authError: string;
  authLoading: boolean;
  setShowAuthModal: (v: boolean) => void;
  setAuthTab: (v: AuthTab) => void;
  setAuthForm: (v: AuthForm) => void;
  setAuthError: (err: string) => void;
  handleAuthSubmit: (e: React.FormEvent) => Promise<void>;
  handleLogout: () => Promise<void>;
  tryRefreshToken: () => Promise<string | null>;
  handleUnauthenticated: () => void;
}

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [csrfToken, setCsrfToken] = useState<string>("");
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authTab, setAuthTab] = useState<AuthTab>("login");
  const [authForm, setAuthForm] = useState<AuthForm>({ email: "", password: "" });
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetchCsrfToken(controller.signal).then(setCsrfToken).catch(() => {});
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    sessionRestore(controller.signal)
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then(async (data: { access_token: string }) => {
        setAccessToken(data.access_token);
        const u = await fetchUser(data.access_token);
        if (u) setUser(u);
      })
      .catch(() => { /* No valid session */ });

    return () => controller.abort();
  }, []);

  const tryRefreshToken = useCallback(async (): Promise<string | null> => {
    const token = await apiTryRefresh();
    if (token) setAccessToken(token);
    return token;
  }, []);

  const handleUnauthenticated = useCallback(() => {
    setUser(null);
    setAccessToken(null);
  }, []);

  const handleAuthSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setAuthError("");

      if (!authForm.email || !authForm.password) {
        setAuthError("Please fill in all fields.");
        return;
      }
      if (authForm.email.length > 254) {
        setAuthError("Email must be at most 254 characters.");
        return;
      }
      if (!/^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/.test(authForm.email)) {
        setAuthError("Email address is not valid.");
        return;
      }
      if (authForm.password.length < 8) {
        setAuthError("Password must be at least 8 characters.");
        return;
      }
      if (authForm.password.length > 128) {
        setAuthError("Password must be at most 128 characters.");
        return;
      }
      const hasDigit = /\d/.test(authForm.password);
      const hasSpecial = /[^a-zA-Z0-9]/.test(authForm.password);
      if (!hasDigit && !hasSpecial) {
        setAuthError("Password must contain at least one digit or special character.");
        return;
      }

      setAuthLoading(true);
      const path = authTab === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register";
      const result = await authFetch(path, authForm, csrfToken);
      setAuthLoading(false);
      if (!result.ok) {
        setAuthError((result.data?.error as string) || "Something went wrong. Please try again.");
        return;
      }
      const resultData = result.data as { user: User; access_token: string };
      setUser(resultData.user);
      setAccessToken(resultData.access_token);
      setShowAuthModal(false);
      setAuthForm({ email: "", password: "" });
    },
    [authForm, authTab, csrfToken],
  );

  const handleLogout = useCallback(async () => {
    await apiLogout(accessToken);
    setUser(null);
    setAccessToken(null);
  }, [accessToken]);

  return {
    user,
    accessToken,
    csrfToken,
    showAuthModal,
    authTab,
    authForm,
    authError,
    authLoading,
    setShowAuthModal,
    setAuthTab,
    setAuthForm,
    setAuthError,
    handleAuthSubmit,
    handleLogout,
    tryRefreshToken,
    handleUnauthenticated,
  };
}
