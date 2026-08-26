import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchProblems } from "../api/client";
import type { ProblemListItem } from "../api/types";

export function ProblemsListPage() {
  const [problems, setProblems] = useState<ProblemListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProblems()
      .then(setProblems)
      .catch(() => setError("Could not load the case rack. Is the API running?"));
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Open Cases</h1>
        {problems && <span className="case-count">{problems.length} on file</span>}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {!problems && !error && <div className="loading-line">Pulling the folder rack…</div>}

      {problems && problems.length === 0 && (
        <div className="empty-state">No published problems yet. Check back once a case is filed.</div>
      )}

      {problems && problems.length > 0 && (
        <div className="folder-rack">
          {problems.map((p, i) => (
            <Link key={p.id} to={`/problems/${p.slug}`} className="folder-card">
              <div>
                <span className="case-no">CASE #{String(i + 1).padStart(3, "0")}</span>
                <h3>{p.title}</h3>
              </div>
              <span className={`difficulty-tag difficulty-${p.difficulty}`}>{p.difficulty}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
