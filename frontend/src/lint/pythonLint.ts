import type { LintMarker } from "./bracketLint";

declare global {
  interface Window {
    loadPyodide?: (config?: Record<string, unknown>) => Promise<any>;
  }
}

const PYODIDE_CDN = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";

let pyodidePromise: Promise<any> | null = null;

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

/**
 * Loaded once, lazily, only the first time someone edits Python — a few MB
 * of WASM isn't worth fetching for people only ever writing C++/Java/JS.
 * Real interpreter, real SyntaxError — not a heuristic, unlike the bracket
 * linter used for the other languages.
 */
async function getPyodide(): Promise<any> {
  if (!pyodidePromise) {
    pyodidePromise = (async () => {
      await loadScript(`${PYODIDE_CDN}pyodide.js`);
      if (!window.loadPyodide) throw new Error("Pyodide failed to attach to window");
      return window.loadPyodide({ indexURL: PYODIDE_CDN });
    })();
  }
  return pyodidePromise;
}

export function preloadPythonLinter(): void {
  // Fire-and-forget warm-up so the first real check isn't the slow one.
  getPyodide().catch(() => {
    /* silently ignore — linting is a nice-to-have, not a submission blocker */
  });
}

export async function lintPython(source: string): Promise<LintMarker[]> {
  try {
    const pyodide = await getPyodide();
    pyodide.globals.set("__source_to_check__", source);
    const resultJson: string = pyodide.runPython(`
import json
try:
    compile(__source_to_check__, "<submission>", "exec")
    json.dumps(None)
except SyntaxError as e:
    json.dumps({"lineno": e.lineno or 1, "offset": e.offset or 1, "msg": e.msg})
`);
    const parsed = resultJson ? JSON.parse(resultJson) : null;
    if (!parsed) return [];
    return [
      {
        startLineNumber: parsed.lineno,
        startColumn: parsed.offset,
        endLineNumber: parsed.lineno,
        endColumn: parsed.offset + 1,
        message: `SyntaxError: ${parsed.msg}`,
      },
    ];
  } catch {
    // Pyodide not ready yet or failed to load (offline, blocked CDN, etc.)
    // — fail open, no markers, rather than blocking the editor.
    return [];
  }
}
