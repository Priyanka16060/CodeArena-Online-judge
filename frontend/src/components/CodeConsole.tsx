import Editor, { OnMount } from "@monaco-editor/react";
import { useEffect, useRef, useState } from "react";
import type { Language } from "../api/types";
import { lintBrackets } from "../lint/bracketLint";
import { lintPython, preloadPythonLinter } from "../lint/pythonLint";

const LANGUAGE_OPTIONS: { value: Language; label: string; monacoId: string; template: string }[] = [
  {
    value: "python",
    label: "Python 3",
    monacoId: "python",
    template: "def solve():\n    pass\n\n\nif __name__ == \"__main__\":\n    solve()\n",
  },
  {
    value: "cpp",
    label: "C++17",
    monacoId: "cpp",
    template: "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    return 0;\n}\n",
  },
  {
    value: "java",
    label: "Java 17",
    monacoId: "java",
    template: "public class Main {\n    public static void main(String[] args) {\n\n    }\n}\n",
  },
  {
    value: "javascript",
    label: "Node.js",
    monacoId: "javascript",
    template: "function solve() {\n\n}\n\nsolve();\n",
  },
];

const LINT_DEBOUNCE_MS = 500;

interface Props {
  onSubmit: (language: Language, sourceCode: string) => void;
  onRun: (language: Language, sourceCode: string) => void;
  submitting: boolean;
  running: boolean;
}

export function CodeConsole({ onSubmit, onRun, submitting, running }: Props) {
  const [language, setLanguage] = useState<Language>("python");
  const [code, setCode] = useState(LANGUAGE_OPTIONS[0].template);
  const [errorCount, setErrorCount] = useState(0);
  const monacoRef = useRef<any>(null);
  const editorRef = useRef<any>(null);
  const lintTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleLanguageChange(next: Language) {
    setLanguage(next);
    const option = LANGUAGE_OPTIONS.find((o) => o.value === next)!;
    setCode(option.template);
    if (next === "python") preloadPythonLinter();
  }

  useEffect(() => {
    if (language === "python") preloadPythonLinter();
  }, [language]);

  // Debounced syntax check: real interpreter for Python (via Pyodide),
  // bracket/quote balance heuristic for C++/Java. JavaScript gets Monaco's
  // own built-in TypeScript-powered diagnostics for free — nothing to wire.
  useEffect(() => {
    if (language === "javascript") return;
    if (lintTimer.current) clearTimeout(lintTimer.current);

    lintTimer.current = setTimeout(async () => {
      const monaco = monacoRef.current;
      const editor = editorRef.current;
      if (!monaco || !editor) return;
      const model = editor.getModel();
      if (!model) return;

      const markers = language === "python" ? await lintPython(code) : lintBrackets(code);
      monaco.editor.setModelMarkers(
        model,
        "codearena-lint",
        markers.map((m) => ({ ...m, severity: monaco.MarkerSeverity.Error }))
      );
      setErrorCount(markers.length);
    }, LINT_DEBOUNCE_MS);

    return () => {
      if (lintTimer.current) clearTimeout(lintTimer.current);
    };
  }, [code, language]);

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
  };

  const active = LANGUAGE_OPTIONS.find((o) => o.value === language)!;
  const extension =
    active.value === "python" ? "py" : active.value === "cpp" ? "cpp" : active.value === "java" ? "java" : "js";

  return (
    <div className="console">
      <div className="console-toolbar">
        <div className="field">
          <label htmlFor="language-select">Language</label>
          <select
            id="language-select"
            value={language}
            onChange={(e) => handleLanguageChange(e.target.value as Language)}
          >
            {LANGUAGE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        {errorCount > 0 && (
          <span className="lint-flag">
            {errorCount} syntax issue{errorCount > 1 ? "s" : ""}
          </span>
        )}
      </div>

      <div className="editor-frame">
        <div className="editor-titlebar">
          <span>solution.{extension}</span>
          <span className="dots">
            <span />
            <span />
            <span />
          </span>
        </div>
        <Editor
          height="420px"
          language={active.monacoId}
          value={code}
          onChange={(value) => setCode(value ?? "")}
          onMount={handleMount}
          theme="vs-dark"
          options={{
            fontSize: 13,
            fontFamily: "IBM Plex Mono, monospace",
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            automaticLayout: true,
          }}
        />
      </div>

      <div className="console-actions">
        <button className="btn secondary" disabled={running || !code.trim()} onClick={() => onRun(language, code)}>
          {running ? "Running…" : "Run (samples)"}
        </button>
        <button className="btn" disabled={submitting || !code.trim()} onClick={() => onSubmit(language, code)}>
          {submitting ? "Submitting…" : "Submit for judging"}
        </button>
      </div>
    </div>
  );
}
