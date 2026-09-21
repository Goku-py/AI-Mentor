import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="not-found" role="alert" aria-live="assertive" style={{ minHeight: "100vh" }}>
          <div className="not-found-code" aria-hidden="true">!</div>
          <h1 className="not-found-title">Something went wrong</h1>
          <p className="not-found-desc">
            An unexpected error occurred. Your work is saved locally. Try reloading or resetting the editor.
          </p>
          <pre
            style={{
              maxWidth: 560,
              width: "100%",
              textAlign: "left",
              background: "var(--panel-bg)",
              border: "1px solid var(--border-color)",
              borderRadius: "8px",
              padding: "0.75rem",
              fontSize: "0.8rem",
              overflowX: "auto",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {this.state.error?.message ?? "Unknown error"}
          </pre>
          <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
            <button
              className="run-btn"
              onClick={() => this.setState({ hasError: false, error: null })}
              type="button"
            >
              Try again
            </button>
            <a href="/" className="not-found-link" style={{ background: "var(--panel-bg)", color: "var(--text-primary)", border: "1px solid var(--border-color)" }}>
              Reload app
            </a>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
