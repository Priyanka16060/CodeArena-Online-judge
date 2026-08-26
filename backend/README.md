# CodeArena — Distributed Sandboxed Code Execution Engine (Online Judge)

A real online judge backend: users submit code in Python/C++/Java/JS against
a problem's hidden test cases, and get back a verdict (`ACCEPTED`,
`WRONG_ANSWER`, `TIME_LIMIT_EXCEEDED`, `MEMORY_LIMIT_EXCEEDED`,
`RUNTIME_ERROR`, `COMPILE_ERROR`) — the same shape of system behind
LeetCode, Codeforces, and HackerRank's judging core.

This is not a toy that runs `exec()` on trusted input. Every submission runs
inside an isolated, resource-capped, network-disabled Docker container that
gets destroyed immediately after.

## Why this project (vs. just another CRUD app)

The interesting engineering problems here are:
1. **Sandboxing untrusted code** you did not write, with someone actively
   trying to break out of it (infinite loops, fork bombs, memory bombs,
   `os.system("rm -rf /")`, reading files it shouldn't see).
2. **Decoupling submission (fast) from judging (slow, minutes under load)**
   via a queue, so the API stays responsive under a burst of submissions.
3. **Horizontal scaling of the expensive part** — judging — independent of
   the API layer, with zero coordination between worker replicas.
4. **Correct concurrency control** on rate limiting under concurrent
   requests from the same user (a naive read-then-write rate limiter has a
   race condition; this one doesn't — see `app/rate_limit.py`).

## Architecture

```
                     ┌─────────────┐        ┌──────────────┐
  client ──HTTP──▶   │   FastAPI   │──enqueue──▶│    Redis    │
                     │     API     │  (LPUSH)   │ submission  │
                     └──────┬──────┘            │    queue    │
                            │                    └──────┬───────┘
                      writes│PENDING                    │BRPOP
                            ▼                            ▼
                     ┌─────────────┐            ┌──────────────┐
                     │ PostgreSQL  │◀───updates──│  Judge Worker │──▶ ephemeral
                     │ (source of  │   verdict   │ (N replicas)  │    Docker
                     │   truth)    │             └──────┬───────┘    containers
                     └─────────────┘                    │            per test case
                            ▲                    publish│
                            │                            ▼
                     GET /submissions/{id}      ┌──────────────┐
                     (poll)          ◀──────────│ Redis Pub/Sub │──▶ WS clients
                                      live push  │   (verdict)   │  (instant push)
                                                 └──────────────┘
```

**Submission flow:**
1. Client `POST /submissions` → API checks the Redis sliding-window rate
   limit, inserts a `Submission` row with verdict `QUEUED` (durable —
   survives a worker crash), then `LPUSH`es the submission id onto a Redis
   list. Returns `202 Accepted` immediately — the API never blocks on
   judging.
2. Any free worker (there can be many, see scaling below) `BRPOP`s the id,
   flips the row to `JUDGING`, and works through the problem's test cases
   **in order**, stopping at the first failure (fail-fast, like Codeforces —
   cheaper than always running every hidden test).
3. Each test case runs in a **fresh, ephemeral, resource-capped container**
   (see "Sandbox isolation model" below). Stdin is the test's input, stdout
   is compared against the expected output after whitespace normalization.
4. The worker writes the final verdict back to Postgres and publishes it on
   a Redis Pub/Sub channel. Clients can either poll `GET /submissions/{id}`
   or open `WS /submissions/{id}/live` for a push the instant it's ready.

## Sandbox isolation model

Every layer below is load-bearing (see `worker/sandbox.py` for the full
rationale in comments), not decorative:

| Layer | Mechanism | Stops |
|---|---|---|
| Fresh container per run | `client.containers.run()` + `remove(force=True)` | State/process leaking between test cases |
| No network | `network_disabled=True` | Exfiltration, calling out, DoSing third parties |
| No swap | `mem_limit == memswap_limit` | Escaping the memory cap via swap |
| CPU cap | `nano_cpus=1_000_000_000` (1 core) | One submission starving others on the host |
| PID cap | `pids_limit=64` | Fork bombs |
| Read-only rootfs | mounted volume is the only writable path | Tampering with the image |
| No capabilities | `cap_drop=["ALL"]`, `no-new-privileges` | Privilege escalation via runtime bugs |
| Non-root | `user="1000:1000"` | Anything that needs root |
| Hard wall-clock kill | `container.wait(timeout=...)` then `container.kill()` | A process that ignores its own limits |
| Output cap | truncate to `MAX_OUTPUT_BYTES` | Output-bomb DoS (`print("x"*10**12)`) |

This is solid single-host isolation. It is **not** gVisor/Kata/Firecracker
-grade — see "Scaling & hardening notes" for what changes if this needs to
run fully anonymous, internet-scale traffic.

## Concurrency & scaling

- **Judging throughput scales horizontally**: `docker compose up --scale
  worker=10` adds 10x judging capacity. Workers coordinate through nothing
  but the shared Redis list — no leader election, no sticky routing, no
  shared in-memory state. This is the same pattern TicketFlow and RideFlow
  use for their concurrency benchmarking, applied here to a queue-worker
  topology instead of locking strategies.
- **Within one worker process**, `WORKER_CONCURRENCY` submissions judge
  concurrently via `asyncio`, with each blocking Docker SDK call (it's
  synchronous under the hood) offloaded via `asyncio.to_thread` so it
  doesn't block the event loop.
- **Rate limiting is race-free under concurrency**: a naive
  read-count-then-write approach lets two simultaneous requests from the
  same user both read a stale count and both get admitted. `app/rate_limit.py`
  runs the whole check-and-increment as a single Redis Lua script, which
  Redis executes atomically on its single-threaded event loop — no
  distributed lock needed.
- **The Postgres row is the source of truth, the queue is just a pointer.**
  If a worker crashes mid-judge, the submission row still exists in
  `QUEUED`/`JUDGING` state and can be detected and requeued by a reaper
  (not implemented here — noted as a follow-up below, since it needs a
  visibility-timeout design like SQS rather than a plain Redis list).

## Docker-outside-of-Docker (the part everyone gets wrong first try)

The worker itself runs **inside** a container, but it needs to launch
*sibling* sandbox containers on the **host's** Docker daemon — not nested
containers (no dind image, no privileged mode). It does this by mounting
the host's `/var/run/docker.sock` into the worker container.

The gotcha: when the worker tells the (host) daemon "bind-mount this
directory into the sandbox container," the daemon resolves that path
against the **host filesystem**, not the worker container's filesystem —
because the daemon runs on the host and has never heard of the worker
container's mount namespace. So `JUDGE_WORKDIR_ROOT` must be the **same
absolute path on both sides**: the worker container bind-mounts
`${PWD}/judge-runs` from the host to the identical path
`${PWD}/judge-runs` inside itself, and uses that same path as
`JUDGE_WORKDIR_ROOT`. See the `x-worker-common` anchor in
`docker-compose.yml`.

## Repo layout

```
app/                     FastAPI service (the "control plane")
  main.py                 app factory, router wiring, /health
  config.py                all tunables in one Pydantic Settings object
  database.py               async SQLAlchemy engine/session
  models.py                    User, Problem, TestCase, Submission
  schemas.py                     Pydantic request/response models
  security.py                      JWT + bcrypt password hashing
  rate_limit.py                     Redis Lua sliding-window limiter
  deps.py                            get_current_user / get_current_admin
  redis_client.py                     Redis client singleton
  routers/
    auth.py                register / login / me
    problems.py               list / detail / create (admin)
    submissions.py               submit / poll / list / live WebSocket

worker/                  Judging worker (the "data plane")
  judge_worker.py          main loop: BRPOP -> compile -> run tests -> verdict
  sandbox.py                 Docker sandbox: the isolation model above
  languages.py                  per-language image + compile/run commands

alembic/                 Schema migrations (baseline + framework wired up)
scripts/seed_problems.py Seeds an admin user + 3 sample problems
tests/
  test_security.py        unit — JWT/password (no infra)
  test_sandbox_utils.py    unit — output normalization (no infra)
  test_api_integration.py    integration — real HTTP + real Docker judging,
                                auto-skips if the stack isn't up
docker-compose.yml        postgres + redis + api + N worker replicas
Dockerfile.api / Dockerfile.worker
```

## Running it

Requires Docker + Docker Compose. The host running `docker compose` needs
Docker itself, obviously — the worker talks to it over the mounted socket.

```bash
git clone <this repo> && cd online-judge
cp .env.example .env          # edit JWT_SECRET for anything beyond local dev
mkdir -p judge-runs            # host dir workers bind-mount sandboxes from
docker compose up -d --build
docker compose exec api python -m scripts.seed_problems
```

API docs: http://localhost:8000/docs

```bash
# Register + login
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"username":"autumn","email":"autumn@example.com","password":"testpass123"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/login \
  -d 'username=autumn&password=testpass123' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# Submit a correct Two Sum solution
curl -X POST localhost:8000/submissions -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "problem_slug": "two-sum",
    "language": "python",
    "source_code": "nums=list(map(int,input().split()));t=int(input());seen={}\nfor i,n in enumerate(nums):\n  if t-n in seen: print(seen[t-n], i); break\n  seen[n]=i"
  }'

# Poll (swap in the id from the response above)
curl localhost:8000/submissions/<id> -H "Authorization: Bearer $TOKEN"
```

Scale judging workers: `docker compose up -d --scale worker=8`

### Tests

```bash
pip install -r requirements.txt
pytest tests/test_security.py tests/test_sandbox_utils.py -v   # pure unit, no infra

docker compose up -d
docker compose exec api python -m scripts.seed_problems
pytest tests/test_api_integration.py -v                        # real end-to-end judging
```

## What I'd add next (honest scope notes for an interview)

- **Requeue/visibility-timeout on worker crash.** Right now if a worker is
  killed mid-`JUDGING`, that submission stays stuck at `JUDGING` forever.
  A proper fix moves from a plain Redis list to a visibility-timeout queue
  (Redis Streams with consumer groups + `XCLAIM`, or SQS) so an unacked
  message gets redelivered.
- **gVisor/Firecracker for true multi-tenant isolation at internet scale.**
  Standard Docker containers share the host kernel; a sufficiently novel
  syscall-level exploit could still escape. `runsc` (gVisor) as the
  container runtime intercepts syscalls in userspace and is what Judge0 and
  competitive-programming platforms actually use in production. Swapping
  it in here is a one-line `runtime="runsc"` change in `sandbox.py` once
  it's installed on the host.
- **Per-test-case container reuse for compiled languages** — right now
  every test case for a C++/Java submission spins a fresh container even
  though the compiled binary doesn't change; keeping one container alive
  per submission and `exec`-ing into it for each test would cut container
  spin-up overhead significantly, at the cost of needing a custom
  per-exec timeout (Docker's per-container `wait(timeout=)` doesn't apply
  to individual `exec` calls).
- **Idempotency key on submit** to survive client retries on a flaky
  network without double-charging the rate limit / creating duplicate rows.

## Trial runs vs. graded submissions

Two distinct paths hit the sandbox now:

- **`POST /submissions`** — graded, persisted, counts toward `submit_rate_limit`.
  Runs every test case (sample + hidden). Live updates over
  `WS /submissions/{id}/live`.
- **`POST /submissions/run`** — a "Run" button: judges only a problem's
  *sample* test cases, writes nothing to the database, and draws from its
  own separate `run_rate_limit` budget so trying things out doesn't burn
  your graded-submission quota. Results stream over
  `WS /submissions/run/{run_id}/live` as each sample case finishes
  (`{ordinal, passed, actual_output, stderr_snippet, time_ms}`), ending
  with `{"final": true, "all_passed": ...}`.

  Implementation note: the live-submission WebSocket uses Redis Pub/Sub,
  which is fine there because a DB row is the fallback if a client connects
  late. Trial runs have no DB row, so `run_live` instead reads from a Redis
  **list** the worker `RPUSH`es onto (`judge:run:{run_id}`, TTL-expired) —
  a client that connects a beat late still sees every event, not just
  whatever was published after it subscribed.

- **`GET /submissions/{id}/percentile`** — for an `ACCEPTED` submission,
  returns `faster_than_pct` / `less_memory_than_pct` against other accepted
  submissions for the same problem. This is deliberately *not* an attempt
  at Big-O time/space complexity analysis, which isn't reliably derivable
  from arbitrary submitted code — it's the same empirical-percentile
  approach LeetCode actually uses under the "Runtime beats X%" label.
