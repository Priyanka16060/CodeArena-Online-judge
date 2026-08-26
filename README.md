# CodeArena - Online Judge

CodeArena is a containerized online coding judge built with **FastAPI,
PostgreSQL, Redis, Docker, and React**. Users submit code, which is
asynchronously judged inside isolated Docker containers and returned
with a verdict.

## Features

-   JWT authentication
-   Problem creation and management
-   Python, C++, Java, and JavaScript submissions
-   Redis-backed asynchronous judging queue
-   Horizontally scalable judge workers
-   Docker-based sandboxed code execution
-   CPU, memory, PID, timeout, and output limits
-   Network-disabled execution
-   Compile error, runtime error, TLE, MLE, and wrong-answer detection
-   WebSocket live verdict updates
-   Redis-based submission rate limiting
-   PostgreSQL persistence
-   Sample-test Run functionality

## Architecture

``` text
React Frontend
      |
      v
FastAPI API
      |
      +---------- PostgreSQL
      |
      +---------- Redis Queue
                     |
                     v
              Judge Workers
                     |
                     v
              Docker Sandbox
                     |
                     v
             Execute User Code
                     |
                     v
               Compare Output
                     |
                     v
                 Verdict
```

## Judging Flow

``` text
Submit Code
    |
    v
FastAPI
    |
    +-- Authenticate
    +-- Rate limit
    +-- Validate problem
    +-- Store submission
    |
    v
Redis Queue
    |
    v
Judge Worker
    |
    v
Ephemeral Docker Container
    |
    +-- Compile
    +-- Execute
    +-- Enforce limits
    +-- Capture output
    |
    v
Compare with test cases
    |
    v
PostgreSQL + Redis Pub/Sub
    |
    v
WebSocket Verdict
```

## Sandbox Security

Each test case runs inside a fresh Docker container with:

-   Network disabled
-   Non-root execution
-   Read-only filesystem
-   Dropped Linux capabilities
-   No-new-privileges
-   CPU and memory limits
-   PID limits
-   Execution timeout
-   Output-size limits

## Verdicts

  Verdict                   Meaning
  ------------------------- -------------------------------
  `ACCEPTED`                All tests passed
  `WRONG_ANSWER`            Output did not match
  `TIME_LIMIT_EXCEEDED`     Execution exceeded time limit
  `MEMORY_LIMIT_EXCEEDED`   Memory limit exceeded
  `RUNTIME_ERROR`           Program crashed
  `COMPILE_ERROR`           Compilation failed
  `INTERNAL_ERROR`          Judge infrastructure error

## Scaling

The API and workers are independently scalable:

``` bash
docker compose up -d --scale worker=8
```

Multiple workers consume submissions from the same Redis queue.

## Real-Time Verdicts

REST:

``` text
GET /submissions/{submission_id}
```

WebSocket:

``` text
WS /submissions/{submission_id}/live
```

Redis Pub/Sub delivers verdict events to connected clients.

## Rate Limiting

Submission requests use Redis-backed rate limiting. A Redis Lua script
performs the check and increment atomically to avoid concurrent-request
race conditions.

## Technology Stack

### Backend

-   Python
-   FastAPI
-   SQLAlchemy
-   Pydantic
-   PostgreSQL
-   Redis
-   JWT

### Judge Infrastructure

-   Docker
-   Docker Compose
-   Redis queues
-   Redis Pub/Sub
-   Async workers

### Frontend

-   React
-   TypeScript
-   Vite
-   Monaco Editor
-   React Router

### Testing

-   Pytest
-   API integration tests
-   Sandbox tests
-   Security tests

## Project Structure

``` text
CodeArena-Online-Judge/
├── backend/
│   ├── app/
│   ├── worker/
│   ├── scripts/
│   ├── tests/
│   ├── alembic/
│   ├── docker-compose.yml
│   ├── Dockerfile.api
│   └── Dockerfile.worker
│
└── frontend/
    ├── src/
    ├── package.json
    └── vite.config.ts
```

## Run Locally

### Backend

``` bash
cd backend
cp .env.example .env
mkdir -p judge-runs
docker compose up -d --build
```

Seed sample problems:

``` bash
docker compose exec api python -m scripts.seed_problems
```

API documentation:

``` text
http://localhost:8000/docs
```

### Frontend

``` bash
cd frontend
npm install
npm run dev
```

## Sample Problems

-   Two Sum
-   Reverse a String
-   Fibonacci mod 1e9+7

## Testing

``` bash
cd backend
docker compose up -d
pytest tests/ -v
```

## Engineering Highlights

1.  Safe execution of untrusted user code.
2.  Asynchronous judging separated from API requests.
3.  Horizontally scalable judge workers.
4.  Durable submission state in PostgreSQL.
5.  Redis queues, rate limiting, and live events.
6.  Real-time verdicts through WebSockets.
7.  Resource restrictions for submitted programs.

## Current Limitations

The project is currently designed for local and controlled deployment.

Potential production improvements:

-   Redis Streams or an acknowledgement-based queue for worker crash
    recovery.
-   Stronger sandbox isolation such as Firecracker or gVisor.
-   More efficient compiled-language execution.
-   Idempotency keys for duplicate submissions.
-   Production monitoring and alerting.

## Project Status

**Functional local deployment**

CodeArena currently supports authentication, problem management,
asynchronous judging, Docker sandbox execution, multiple workers, Redis
queueing, WebSocket verdict streaming, and automated test-case
evaluation.
