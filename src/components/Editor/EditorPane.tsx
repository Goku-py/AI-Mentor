import { useEffect } from "react";
import Prism from "prismjs";
import Editor from "react-simple-code-editor";
import { CodeIcon } from "../Icons";

function escapeHtml(unsafe: string): string {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

interface EditorPaneProps {
  code: string;
  language: string;
  fontSize: number;
  errorLine: number | null;
  editorWrapperRef: React.RefObject<HTMLDivElement>;
  onCodeChange: (code: string) => void;
  onRun?: () => void;
}

export default function EditorPane({
  code,
  language,
  fontSize,
  errorLine,
  editorWrapperRef,
  onCodeChange,
  onRun,
}: EditorPaneProps) {
  useEffect(() => {
    const textarea = editorWrapperRef.current?.querySelector("textarea");
    textarea?.focus();
  }, [editorWrapperRef]);

  return (
    <section className="editor-pane" aria-label="Code editor">
      <h2 className="pane-header">
        <CodeIcon aria-hidden="true" /> Editor
      </h2>
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          overflowX: "auto",
          backgroundColor: "var(--bg-color)",
          minHeight: 0,
          display: "flex",
        }}
        className="editor-container"
        role="group"
        aria-label={`Code editor, language ${language}`}
      >
        <div className="line-numbers" aria-hidden="true" style={{ fontSize: fontSize + "px", minHeight: "100%" }}>
          {code.replace(/\n+$/, "").split("\n").map((_, i) => (
            <div key={i} style={{ height: "1.6em" }}>{i + 1}</div>
          ))}
        </div>
        <div style={{ flex: 1, position: "relative", minHeight: 0 }} ref={editorWrapperRef}>
          <label htmlFor="code-editor-textarea" className="sr-only">Code editor</label>
          <Editor
            key={language}
            value={code}
            onValueChange={(newCode: string) => {
              onCodeChange(newCode.replace(/\r\n/g, "\n").replace(/\r/g, "\n"));
            }}
            onKeyDown={(e: React.KeyboardEvent) => {
              if (e.ctrlKey && e.key === "Enter") {
                e.preventDefault();
                onRun?.();
              }
            }}
            textareaId="code-editor-textarea"
            highlight={(codeToHighlight: string) => {
              const grammar = language === "cpp" || language === "c"
                ? Prism.languages.cpp || Prism.languages.clike
                : language === "java"
                  ? Prism.languages.java || Prism.languages.clike
                  : language === "javascript"
                    ? Prism.languages.javascript
                    : Prism.languages.python;
              const highlighted = grammar
                ? Prism.highlight(codeToHighlight, grammar, language)
                : escapeHtml(codeToHighlight);
              return highlighted
                .split("\n")
                .map((line, idx) => `<span class="${errorLine === idx + 1 ? "error-line" : ""}">${line || " "}</span>`)
                .join("\n");
            }}
            padding={24}
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: fontSize,
              minHeight: "100%",
              whiteSpace: "pre",
            }}
            textareaClassName="code-textarea"
          />
        </div>
      </div>
    </section>
  );
}
