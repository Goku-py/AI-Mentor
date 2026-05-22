import { useRef, useEffect } from "react";
import { CodeIcon } from "../Icons";
import type { AuthForm, AuthTab } from "../../types";

interface AuthModalProps {
  authTab: AuthTab;
  authForm: AuthForm;
  authError: string;
  authLoading: boolean;
  onClose: () => void;
  onTabChange: (tab: AuthTab) => void;
  onFormChange: (form: AuthForm) => void;
  onSubmit: (e: React.FormEvent) => Promise<void>;
}

export default function AuthModal({
  authTab,
  authForm,
  authError,
  authLoading,
  onClose,
  onTabChange,
  onFormChange,
  onSubmit,
}: AuthModalProps) {
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previousFocus.current = document.activeElement as HTMLElement | null;
    const emailInput = document.getElementById("auth-email");
    emailInput?.focus();
    return () => {
      previousFocus.current?.focus();
    };
  }, []);

  return (
    <div
      className="auth-overlay"
      role="none"
      onClick={(e: React.MouseEvent) => { if (e.target === e.currentTarget) onClose(); }}
      onKeyDown={(e: React.KeyboardEvent) => { if (e.key === "Escape") onClose(); }}
    >
      <div className="auth-modal" role="dialog" aria-modal="true" aria-label="Sign in">
        <button className="auth-modal-close" onClick={onClose} aria-label="Close">✕</button>
        <div className="auth-modal-logo">
          <CodeIcon />
          <span>AI Code Mentor</span>
        </div>
        <div className="auth-tabs">
          <button
            className={`auth-tab ${authTab === "login" ? "active" : ""}`}
            onClick={() => onTabChange("login")}
          >
            Sign In
          </button>
          <button
            className={`auth-tab ${authTab === "register" ? "active" : ""}`}
            onClick={() => onTabChange("register")}
          >
            Create Account
          </button>
        </div>
        <form className="auth-form" onSubmit={onSubmit} noValidate>
          <div className="auth-field">
            <label htmlFor="auth-email">Email address</label>
            <input
              id="auth-email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={authForm.email}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => onFormChange({ ...authForm, email: e.target.value })}
              disabled={authLoading}
              required
            />
          </div>
          <div className="auth-field">
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              autoComplete={authTab === "login" ? "current-password" : "new-password"}
              placeholder={authTab === "register" ? "Min 8 chars, 1 digit or symbol" : "••••••••"}
              value={authForm.password}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => onFormChange({ ...authForm, password: e.target.value })}
              disabled={authLoading}
              required
            />
          </div>
          {authError && (
            <div className="auth-error" role="alert">{authError}</div>
          )}
          <button type="submit" className="auth-submit" disabled={authLoading}>
            {authLoading ? "Please wait…" : (authTab === "login" ? "Sign In" : "Create Account")}
          </button>
        </form>

        <p className="auth-switch">
          {authTab === "login" ? (
            <>No account? <button onClick={() => onTabChange("register")}>Create one free</button></>
          ) : (
            <>Already have one? <button onClick={() => onTabChange("login")}>Sign in</button></>
          )}
        </p>
      </div>
    </div>
  );
}
