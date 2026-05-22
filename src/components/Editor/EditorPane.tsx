import { useEffect } from "react";
import Prism from "prismjs";
import Editor from "react-simple-code-editor";
import { CodeIcon } from "../Icons";

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
    <div className="editor-pane">
      <div className="pane-header">
        <CodeIcon /> Editor
      </div>
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
      >
        <div className="line-numbers" aria-hidden="true" style={{ fontSize: fontSize + "px", minHeight: "100%" }}>
          {code.split("\n").map((_, i) => (
            <div key={i} style={{ height: "1.6em" }}>{i + 1}</div>
          ))}
        </div>
        <div style={{ flex: 1, position: "relative", minHeight: 0 }} ref={editorWrapperRef}>
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
            highlight={(codeToHighlight: string) => {
              const grammar = language === "cpp" || language === "c"
                ? Prism.languages.cpp || Prism.languages.clike
                : language === "java"
                  ? Prism.languages.java || Prism.languages.clike
                  : language === "javascript"
                    ? Prism.languages.javascript
                    : Prism.languages.python;
              const highlighted = grammar ? Prism.highlight(codeToHighlight, grammar, language) : codeToHighlight;
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
    </div>
  );
}
