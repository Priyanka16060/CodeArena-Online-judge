import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchMySubmissions } from "../api/client";
import type { SubmissionSummary } from "../api/types";

const DAYS_WINDOW = 14;

function buildDailyCounts(rows: SubmissionSummary[]) {
  const counts = new Map<string, number>();
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  for (let i = DAYS_WINDOW - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    counts.set(d.toISOString().slice(0, 10), 0);
  }

  for (const row of rows) {
    const day = row.submitted_at.slice(0, 10);
    if (counts.has(day)) counts.set(day, (counts.get(day) ?? 0) + 1);
  }

  return Array.from(counts.entries()).map(([day, count]) => ({
    day: day.slice(5), // MM-DD
    count,
  }));
}

export function SubmissionsPage() {
  const [rows, setRows] = useState<SubmissionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMySubmissions()
      .then(setRows)
      .catch(() => setError("Could not load your submission ledger."));
  }, []);

  const dailyCounts = useMemo(() => (rows ? buildDailyCounts(rows) : []), [rows]);
  const acceptedCount = rows ? rows.filter((r) => r.verdict === "ACCEPTED").length : 0;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Submission Ledger</h1>
        {rows && <span className="case-count">{rows.length} entries</span>}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {!rows && !error && <div className="loading-line">Pulling your ledger…</div>}

      {rows && (
        <div className="rate-chart-block">
          <div className="rate-chart-header">
            <h4>Submission Rate — last {DAYS_WINDOW} days</h4>
            <span className="folder-tab">
              {acceptedCount}/{rows.length} accepted
            </span>
          </div>
          <div className="rate-chart-frame">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={dailyCounts} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--rule)" />
                <XAxis
                  dataKey="day"
                  tick={{ fontFamily: "IBM Plex Mono", fontSize: 11, fill: "var(--ink-soft)" }}
                  axisLine={{ stroke: "var(--ink)" }}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontFamily: "IBM Plex Mono", fontSize: 11, fill: "var(--ink-soft)" }}
                  axisLine={false}
                  tickLine={false}
                  width={28}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--ink)",
                    border: "none",
                    borderRadius: 4,
                    fontFamily: "IBM Plex Mono",
                    fontSize: 12,
                  }}
                  labelStyle={{ color: "var(--paper)" }}
                  itemStyle={{ color: "var(--paper)" }}
                  cursor={{ fill: "var(--paper-dark)" }}
                />
                <Bar dataKey="count" name="Submissions" fill="var(--stamp-blue)" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {rows && rows.length === 0 && (
        <div className="empty-state">No submissions filed yet. Open a case and submit a solution.</div>
      )}

      {rows && rows.length > 0 && (
        <table className="ledger">
          <thead>
            <tr>
              <th>Submitted</th>
              <th>Problem ID</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.submitted_at).toLocaleString()}</td>
                <td className="mono">{r.problem_id.slice(0, 8)}…</td>
                <td>
                  <span className={`verdict-chip v-${r.verdict}`}>{r.verdict.replace(/_/g, " ")}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
