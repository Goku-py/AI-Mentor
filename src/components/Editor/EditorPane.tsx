import { useEffect, useMemo, useRef, useState } from "react";
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

const DEBOUNCE_MS = 120;

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
  // Tokenising the whole document through Prism on every keystroke is what
  // made the editor unusable near the 1MB ceiling. The textarea stays
  // uncontrolled and responsive; only the highlight layer lags behind.
  const [highlighted, setHighlighted] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      const grammar =
        language === "cpp" || language === "c"
          ? Prism.languages.cpp || Prism.languages.clike
          : language === "java"
            ? Prism.languages.java || Prism.languages.clike
            : language === "javascript"
              ? Prism.languages.javascript
              : Prism.languages.python;
      setHighlighted(
        grammar ? Prism.highlight(code, grammar, language) : escapeHtml(code),
      );
    }, DEBOUNCE_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [code, language]);

  // Error line shading is cheap and must feel instant, so it is applied to the
  // debounced markup rather than re-highlighting.
  const highlightWithErrorLine = useMemo(
    () =>
      highlighted
        .split("\n")
        .map((line, idx) => `<span class="${errorLine === idx + 1 ? "error-line" : ""}">${line || " "}</span>`)
        .join("\n"),
    [highlighted, errorLine],
  );

  const lineNumbers = useMemo(
    () => code.replace(/\n+$/, "").split("\n").length,
    [code],
  );

  // Re-focus after a language switch without keying the <Editor>: key={language}
  // remounted the textarea and threw focus away.
  const textareaId = "code-editor-textarea";
  useEffect(() => {
    document.getElementById(textareaId)?.focus();
  }, [language]);

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
          {Array.from({ length: lineNumbers }, (_, i) => (
            <div key={i} style={{ height: "1.6em" }}>{i + 1}</div>
          ))}
        </div>
        <div style={{ flex: 1, position: "relative", minHeight: 0 }} ref={editorWrapperRef}>
          <label htmlFor={textareaId} className="sr-only">Code editor</label>
          <Editor
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
            textareaId={textareaId}
            highlight={() => highlightWithErrorLine}
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