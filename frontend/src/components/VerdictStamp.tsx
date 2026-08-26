import type { PercentileResult, SubmissionResult, Verdict } from "../api/types";

const STAMP_LABEL: Record<Verdict, string> = {
  PENDING: "Filed",
  QUEUED: "Queued",
  JUDGING: "Judging",
  ACCEPTED: "Accepted",
  WRONG_ANSWER: "Wrong Answer",
  TIME_LIMIT_EXCEEDED: "Time Limit",
  MEMORY_LIMIT_EXCEEDED: "Memory Limit",
  RUNTIME_ERROR: "Runtime Error",
  COMPILE_ERROR: "Compile Error",
  INTERNAL_ERROR: "Internal Error",
};

function stampClass(verdict: Verdict): string {
  if (verdict === "ACCEPTED") return "ok";
  if (verdict === "PENDING" || verdict === "QUEUED" || verdict === "JUDGING") return "warn";
  return "bad";
}

interface Props {
  status: "idle" | "connecting" | "pending" | "done" | "error";
  result: SubmissionResult | null;
  liveVerdict: Verdict | null;
  errorMessage?: string | null;
  percentile?: PercentileResult | null;
}

export function VerdictStamp({ status, result, liveVerdict, errorMessage, percentile }: Props) {
  if (status === "idle") {
    return (
      <div className="verdict-dock">
        <div className="verdict-idle">Submit your solution — the verdict lands here.</div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="verdict-dock">
        <div className="verdict-idle">{errorMessage ?? "Something went wrong reaching the judge."}</div>
      </div>
    );
  }

  const verdict = liveVerdict ?? result?.verdict;

  if (status === "connecting" || !verdict || verdict === "PENDING" || verdict === "QUEUED" || verdict === "JUDGING") {
    return (
      <div className="verdict-dock">
        <div className="verdict-pending">
          <span className="pulse-dot" />
          {verdict ? STAMP_LABEL[verdict] : "Submitting"}&hellip;
        </div>
      </div>
    );
  }

  return (
    <div className="verdict-dock">
      <div className="verdict-stack">
        <div className={`stamp ${stampClass(verdict)}`}>{STAMP_LABEL[verdict]}</div>
        {result && (
          <div className="verdict-detail">
            {result.passed_test_count}/{result.total_test_count} tests passed &middot; score {result.score.toFixed(0)}
            {result.max_time_ms > 0 && <> &middot; {result.max_time_ms.toFixed(0)}ms</>}
            {result.max_memory_kb > 0 && <> &middot; {(result.max_memory_kb / 1024).toFixed(1)}MB</>}
          </div>
        )}
        {result?.stderr_snippet && <pre className="snippet">{result.stderr_snippet}</pre>}
        {result?.compile_output && !result.stderr_snippet && (
          <pre className="snippet">{result.compile_output}</pre>
        )}
        {verdict === "ACCEPTED" && percentile && percentile.sample_size > 0 && (
          <div className="percentile-line">
            Faster than {percentile.faster_than_pct}% &middot; less memory than {percentile.less_memory_than_pct}%
            <span className="percentile-note"> (of accepted solutions on this problem)</span>
          </div>
        )}
      </div>
    </div>
  );
}
