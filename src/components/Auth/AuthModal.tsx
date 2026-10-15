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
  const modalRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);

  // Kept current so the mount-only keydown handler never closes over a stale
  // prop. Without this, typing re-renders App, which hands us a new onClose
  // identity every keystroke.
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  // Focus management is mount-only. Re-running it on every render (via a prop
  // dep) yanked focus back to the email field on each keystroke and made
  // typing a password impossible.
  useEffect(() => {
    previousFocus.current = document.activeElement as HTMLElement | null;
    document.getElementById("auth-email")?.focus();
    return () => previousFocus.current?.focus();
  }, []);

  // Scroll lock + dismissal keys are also mount-only.
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
      if (e.key === "Tab" && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, []);

  const handleTabKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") return;
    const order: AuthTab[] = ["login", "register"];
    const idx = order.indexOf(authTab);
    const next =
      e.key === "Home" ? 0
        : e.key === "End" ? order.length - 1
          : e.key === "ArrowLeft" ? (idx - 1 + order.length) % order.length
            : (idx + 1) % order.length;
    e.preventDefault();
    onTabChange(order[next]);
    document.getElementById(next === 0 ? "tab-login" : "tab-register")?.focus();
  };

  const headingId = authTab === "login" ? "auth-title-login" : "auth-title-register";

  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- backdrop click is supplemental; Escape handles keyboard dismissal
    <div
      className="auth-overlay"
      onClick={(e: React.MouseEvent) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        ref={modalRef}
        className="auth-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
      >
        <button className="auth-modal-close" onClick={onClose} aria-label="Close dialog" type="button">✕</button>
        <div className="auth-modal-logo" aria-hidden="true">
          <CodeIcon />
          <span>AI Code Mentor</span>
        </div>
        <h2 id={headingId} className="sr-only">{authTab === "login" ? "Sign in to your account" : "Create a new account"}</h2>
        <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
          <button
            role="tab"
            aria-selected={authTab === "login"}
            aria-controls="auth-form-panel"
            id="tab-login"
            className={`auth-tab ${authTab === "login" ? "active" : ""}`}
            onClick={() => onTabChange("login")}
            onKeyDown={handleTabKeyDown}
            tabIndex={authTab === "login" ? 0 : -1}
            type="button"
          >
            Sign In
          </button>
          <button
            role="tab"
            aria-selected={authTab === "register"}
            aria-controls="auth-form-panel"
            id="tab-register"
            className={`auth-tab ${authTab === "register" ? "active" : ""}`}
            onClick={() => onTabChange("register")}
            onKeyDown={handleTabKeyDown}
            tabIndex={authTab === "register" ? 0 : -1}
            type="button"
          >
            Create Account
          </button>
        </div>
        <form id="auth-form-panel" role="tabpanel" aria-labelledby={authTab === "login" ? "tab-login" : "tab-register"} className="auth-form" onSubmit={onSubmit} noValidate>
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
              aria-required="true"
              aria-invalid={Boolean(authError)}
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
              aria-required="true"
              aria-describedby="password-hint"
            />
            <span id="password-hint" className="sr-only">
              {authTab === "register" ? "Password must be at least 8 characters and include a digit or symbol." : "Enter your password."}
            </span>
          </div>
          {authError && (
            <div className="auth-error" role="alert" aria-live="assertive">{authError}</div>
          )}
          <button type="submit" className="auth-submit" disabled={authLoading} aria-busy={authLoading}>
            {authLoading ? "Please wait…" : (authTab === "login" ? "Sign In" : "Create Account")}
          </button>
        </form>

        <p className="auth-switch">
          {authTab === "login" ? (
            <>No account? <button onClick={() => onTabChange("register")} type="button">Create one free</button></>
          ) : (
            <>Already have one? <button onClick={() => onTabChange("login")} type="button">Sign in</button></>
          )}
        </p>
      </div>
    </div>
  );
}
