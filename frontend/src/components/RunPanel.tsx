import type { RunCaseEvent, RunFinalEvent } from "../api/types";

interface Props {
  status: "idle" | "running" | "done" | "error";
  cases: RunCaseEvent[];
  final: RunFinalEvent | null;
  errorMessage: string | null;
}

export function RunPanel({ status, cases, final, errorMessage }: Props) {
  if (status === "idle") return null;

  return (
    <div className="run-panel">
      <div className="run-panel-header">
        <span className="folder-tab">Sample Run</span>
        {status === "running" && (
          <span className="run-status running">
            <span className="pulse-dot" /> running…
          </span>
        )}
        {status === "done" && final?.status === "ok" && (
          <span className={`run-status ${final.all_passed ? "pass" : "fail"}`}>
            {final.all_passed ? "All samples passed" : "Some samples failed"}
          </span>
        )}
        {status === "error" && <span className="run-status fail">{errorMessage ?? "Error"}</span>}
      </div>

      {final?.status === "compile_error" && (
        <pre className="snippet run-compile-error">{final.compile_output}</pre>
      )}

      {cases.length > 0 && (
        <div className="run-cases">
          {cases.map((c) => (
            <div key={c.ordinal} className={`run-case ${c.passed ? "pass" : "fail"}`}>
              <div className="run-case-title">
                <span>Sample #{c.ordinal + 1}</span>
                <span className="run-case-badge">{c.passed ? "PASS" : "FAIL"}</span>
                <span className="run-case-time">{c.time_ms.toFixed(0)}ms</span>
              </div>
              {!c.passed && (
                <div className="sample-pair">
                  <div>
                    <span className="lbl">Expected</span>
                    <pre>{c.expected_output}</pre>
                  </div>
                  <div>
                    <span className="lbl">Got</span>
                    <pre>{c.actual_output ?? c.stderr_snippet ?? "(no output)"}</pre>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
