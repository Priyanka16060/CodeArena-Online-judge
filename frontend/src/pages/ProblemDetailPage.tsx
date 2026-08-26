import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { createRun, createSubmission, fetchPercentile, fetchProblem } from "../api/client";
import type { Language, PercentileResult, ProblemDetail } from "../api/types";
import { CodeConsole } from "../components/CodeConsole";
import { RunPanel } from "../components/RunPanel";
import { VerdictStamp } from "../components/VerdictStamp";
import { useRunLive } from "../api/useRunLive";
import { useSubmissionLive } from "../api/useSubmissionLive";

export function ProblemDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [running, setRunning] = useState(false);
  const [activeSubmissionId, setActiveSubmissionId] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [percentile, setPercentile] = useState<PercentileResult | null>(null);

  const live = useSubmissionLive(activeSubmissionId);
  const runLive = useRunLive(activeRunId);

  useEffect(() => {
    if (!slug) return;
    setProblem(null);
    setError(null);
    setActiveSubmissionId(null);
    setActiveRunId(null);
    setPercentile(null);
    fetchProblem(slug)
      .then(setProblem)
      .catch((err) => {
        if (err?.response?.status === 404) setError("No such case file — this problem may be unpublished.");
        else setError("Could not open the case file. Is the API running?");
      });
  }, [slug]);

  // Once a submission comes back ACCEPTED, fetch how it stacks up against
  // other accepted solutions for this problem — our stand-in for "time and
  // space complexity" (see note near the verdict panel for why).
  useEffect(() => {
    if (live.status === "done" && live.result?.verdict === "ACCEPTED") {
      fetchPercentile(live.result.id).then(setPercentile).catch(() => setPercentile(null));
    } else {
      setPercentile(null);
    }
  }, [live.status, live.result]);

  async function handleSubmit(language: Language, sourceCode: string) {
    if (!slug) return;
    setSubmitting(true);
    setActiveSubmissionId(null);
    setActiveRunId(null);
    try {
      const submission = await createSubmission(slug, language, sourceCode);
      setActiveSubmissionId(submission.id);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Submission failed to reach the judge.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRun(language: Language, sourceCode: string) {
    if (!slug) return;
    setRunning(true);
    setActiveRunId(null);
    setActiveSubmissionId(null);
    try {
      const runId = await createRun(slug, language, sourceCode);
      setActiveRunId(runId);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Could not start a run against the samples.");
    } finally {
      setRunning(false);
    }
  }

  if (error && !problem) {
    return (
      <div className="page">
        <div className="error-banner">{error}</div>
      </div>
    );
  }

  if (!problem) {
    return (
      <div className="page">
        <div className="loading-line">Opening case file…</div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="dossier">
        <div className="dossier-sheet">
          <span className="case-no">FILE // {problem.slug.toUpperCase()}</span>
          <h1>{problem.title}</h1>
          <div className="dossier-meta">
            <span className={`difficulty-${problem.difficulty}`}>{problem.difficulty}</span>
            <span>{problem.time_limit_seconds}s time limit</span>
            <span>{problem.memory_limit_mb}MB memory</span>
          </div>
          <div className="statement">{problem.statement}</div>

          {problem.sample_tests.length > 0 && (
            <div className="sample-block">
              <h4>Sample Evidence</h4>
              {problem.sample_tests.map((t) => (
                <div className="sample-pair" key={t.ordinal}>
                  <div>
                    <span className="lbl">Input</span>
                    <pre>{t.input_data}</pre>
                  </div>
                  <div>
                    <span className="lbl">Expected</span>
                    <pre>{t.expected_output}</pre>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          {error && <div className="error-banner">{error}</div>}
          <CodeConsole onSubmit={handleSubmit} onRun={handleRun} submitting={submitting} running={running} />

          {activeRunId && (
            <div style={{ marginTop: "0.9rem" }}>
              <RunPanel
                status={runLive.status}
                cases={runLive.cases}
                final={runLive.final}
                errorMessage={runLive.errorMessage}
              />
            </div>
          )}

          <div style={{ marginTop: "0.9rem" }}>
            <VerdictStamp
              status={live.status}
              result={live.result}
              liveVerdict={live.liveVerdict}
              errorMessage={live.errorMessage}
              percentile={percentile}
            />
            <p className="complexity-note">
              We don't try to guess Big-O time/space complexity from arbitrary code — that's not reliably
              computable. Once a submission is accepted, the percentile above shows how its measured runtime and
              memory actually compared to other accepted solutions here.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
