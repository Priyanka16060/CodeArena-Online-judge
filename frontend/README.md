# CodeArena Web

A fresh React + TypeScript + Vite frontend for the CodeArena online judge — type code, submit it, and watch the verdict get stamped in live as your backend judges it over the `/submissions/{id}/live` WebSocket.

## What's wired up

- **Auth** — register/login against `POST /auth/register` and `POST /auth/login` (OAuth2 form login), JWT stored in `localStorage`, attached as `Authorization: Bearer <token>` on every request.
- **Problems** — case-file list from `GET /problems`, detail + sample tests from `GET /problems/{slug}`.
- **Live syntax checking** — Python gets a real syntax check (via a lazily-loaded Pyodide instance running `compile()`), JavaScript gets Monaco's built-in TypeScript-powered diagnostics for free, and C++/Java get a bracket/quote-balance heuristic linter (there's no realistic way to run a full C++/Java compiler front-end in the browser, so this catches the common typo class rather than doing full semantic validation).
- **Run (samples only)** — a fast-iteration button that judges only the problem's sample tests via `POST /submissions/run`, streaming per-sample pass/fail live over its own WebSocket, without touching the database or your graded-submission rate limit.
- **Submit & judge** — Monaco editor (Python / C++ / Java / Node), `POST /submissions`, then a live WebSocket connection that renders `QUEUED → JUDGING → <verdict>` as it happens, finishing with a stamped verdict and a REST fetch of `GET /submissions/{id}` for timing/memory/stderr detail.
- **Runtime/memory percentile** — once a submission is `ACCEPTED`, fetches `GET /submissions/{id}/percentile` and shows "faster than X% / less memory than Y%" against other accepted solutions. This is deliberately *not* Big-O complexity analysis (not reliably derivable from arbitrary code) — it's the same empirical approach LeetCode uses.
- **History + activity chart** — `GET /submissions` as a ledger table, plus a 14-day submission-rate bar chart (recharts).

## Run it

```bash
cp .env.example .env      # points at http://localhost:8000 by default
npm install
npm run dev
```

Open http://localhost:5173. Make sure your CodeArena API (and worker + Redis + Postgres) is running via `docker compose up` in the backend repo first — CORS is already wide open there (`allow_origins=["*"]`), so no backend changes are needed beyond the "Run" endpoint additions already applied to that repo.

## Notes

- If you deploy the API somewhere other than `localhost:8000`, change `VITE_API_BASE_URL` in `.env`.
- The WebSocket URLs are derived from `VITE_API_BASE_URL` (http→ws, https→wss) — no separate config needed.
- Language templates in the editor are just starting scaffolds; the actual execution behavior (compilers, time/memory limits) is entirely up to your `worker/` sandbox — this frontend just sends `{ problem_slug, language, source_code }`.
- The Python linter loads a few MB of WASM from a CDN the first time you switch to Python — it's lazy and cached, so C++/Java/JS-only users never pay for it.
