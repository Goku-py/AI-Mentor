import { useRef, useEffect } from "react";
import Editor, { OnMount } from "@monaco-editor/react";
import { CodeIcon } from "../Icons";

interface EditorPaneProps {
  code: string;
  language: string;
  fontSize: number;
  errorLine: number | null;
  darkMode: boolean;
  onCodeChange: (code: string) => void;
  onRun?: () => void;
}

const LANGUAGE_MAP: Record<string, string> = {
  python: "python",
  javascript: "javascript",
  java: "java",
  c: "c",
  cpp: "cpp",
};

export default function EditorPane({
  code,
  language,
  fontSize,
  errorLine,
  darkMode,
  onCodeChange,
  onRun,
}: EditorPaneProps) {
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null);
  const decorationRef = useRef<string[]>([]);
  const onRunRef = useRef(onRun);
  onRunRef.current = onRun;

  const handleEditorMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    editor.focus();

    editor.addAction({
      id: "run-code",
      label: "Run Code",
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
      run: () => onRunRef.current?.(),
    });
  };

  useEffect(() => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco) return;

    const newDecorations = errorLine != null
      ? [{
          range: new monaco.Range(errorLine, 1, errorLine, 1),
          options: {
            isWholeLine: true,
            className: "error-line-monaco",
            marginClassName: "error-line-margin",
          },
        }]
      : [];

    decorationRef.current = editor.deltaDecorations(decorationRef.current, newDecorations);

    if (errorLine != null) {
      editor.revealLineInCenter(errorLine);
    }
  }, [errorLine]);

  const monacoLanguage = LANGUAGE_MAP[language] || "plaintext";

  return (
    <div className="editor-pane">
      <div className="pane-header">
        <CodeIcon /> Editor
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <Editor
          language={monacoLanguage}
          value={code}
          onChange={(value) => onCodeChange(value ?? "")}
          theme={darkMode ? "vs-dark" : "vs"}
          options={{
            fontSize,
            minimap: { enabled: false },
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            automaticLayout: true,
            padding: { top: 24 },
            fontFamily: "'Fira Code', ui-monospace, SFMono-Regular, monospace",
            renderLineHighlight: "all",
            tabSize: 4,
            insertSpaces: true,
          }}
          onMount={handleEditorMount}
        />
      </div>
    </div>
  );
}
