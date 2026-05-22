import { TerminalIcon } from "../Icons";
import type { Issue, MismatchInfo } from "../../types";
import { SUPPORTED_LANGUAGES } from "../../types";

interface OutputPaneProps {
  output: string;
  errorMsg: string;
  issues: Issue[];
  mismatchInfo: MismatchInfo | null;
  language: string;
  onLanguageChange: (lang: string, keepCurrentCode?: boolean) => void;
  onClearMismatch: () => void;
}

export default function OutputPane({
  output,
  errorMsg,
  issues,
  mismatchInfo,
  language,
  onLanguageChange,
  onClearMismatch,
}: OutputPaneProps) {
  return (
    <div className="output-pane">
      <div className="pane-header">
        <TerminalIcon /> Standard Output & Code Issues
      </div>
      <div className="pane-content" role="status" aria-live="polite">
        {mismatchInfo && (
          <div
            style={{
              marginBottom: "1rem",
              padding: "0.75rem",
              border: "1px solid #facc15",
              backgroundColor: "#fef9c3",
              color: "#713f12",
              borderRadius: "8px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "0.75rem",
            }}
          >
            <span>
              ⚠️ Language Mismatch: You selected {mismatchInfo.selected} but your code looks like {mismatchInfo.detected}.
            </span>
            {mismatchInfo.detected !== language && SUPPORTED_LANGUAGES.some((l) => l.id === mismatchInfo.detected) && (
              <button
                onClick={() => {
                  onLanguageChange(mismatchInfo.detected, true);
                  onClearMismatch();
                }}
                style={{
                  border: "1px solid #ca8a04",
                  backgroundColor: "#fef08a",
                  color: "#713f12",
                  borderRadius: "6px",
                  padding: "0.35rem 0.65rem",
                  cursor: "pointer",
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                }}
              >
                Switch to {mismatchInfo.detected}
              </button>
            )}
          </div>
        )}

        {!output && !errorMsg && issues.length === 0 && (
          <div className="placeholder-text">Outputs and issues will appear here when you run code.</div>
        )}

        {issues.length > 0 && (
          <div
            style={{
              marginBottom: (output || errorMsg) ? "1rem" : 0,
              borderBottom: (output || errorMsg) ? "1px solid var(--border-color)" : "none",
              paddingBottom: (output || errorMsg) ? "0.5rem" : 0,
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: "0.5rem", color: "var(--text-secondary)" }}>Compiled Analysis Issues:</div>
            {issues.map((i: Issue, idx: number) => (
              <div key={idx} style={{ color: i.severity === "error" ? "var(--error)" : "var(--warning)", fontSize: "0.9em", marginBottom: "0.2rem" }}>
                [Line {i.line}] {i.severity.toUpperCase()}: {i.message}
              </div>
            ))}
          </div>
        )}

        {output && (
          <div style={{ marginBottom: errorMsg ? "1rem" : 0 }}>{output}</div>
        )}

        {errorMsg && (
          <div className="error-text" role="alert">
            <div style={{ fontWeight: 600, marginBottom: "0.5rem", color: "#ff7b72" }}>
              Compiler Error / Exception:
            </div>
            {errorMsg}
          </div>
        )}
      </div>
    </div>
  );
}
