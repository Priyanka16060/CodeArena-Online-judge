"""
The judging worker.

Run N copies of this process (see docker-compose.yml `worker` service with
`deploy.replicas`, or just start multiple containers) to scale judging
throughput horizontally — they all BRPOP from the same Redis list, so work
is naturally load-balanced across whichever worker is free, with no
coordination needed between workers themselves.

Within a single worker process, `WORKER_CONCURRENCY` submissions are judged
concurrently via asyncio, each blocking Docker call offloaded to a thread
via `asyncio.to_thread` (docker-py's client is synchronous under the hood).
"""

import asyncio
import json
import logging
import os
import signal
import socket
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Problem, Submission, TestCase, Verdict
from app.redis_client import get_redis
from worker.languages import LANGUAGE_SPECS
from worker.sandbox import (
    cleanup_workdir,
    compile_submission,
    make_submission_workdir,
    normalize_output,
    run_test_case,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("judge_worker")

settings = get_settings()
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"

_RUNTIME_ERROR_STATUS_TO_VERDICT = {
    "timeout": Verdict.TIME_LIMIT_EXCEEDED,
    "oom": Verdict.MEMORY_LIMIT_EXCEEDED,
    "runtime_error": Verdict.RUNTIME_ERROR,
    "infra_error": Verdict.INTERNAL_ERROR,
}

_shutdown = asyncio.Event()


async def publish_verdict(submission_id: str, payload: dict) -> None:
    redis = get_redis()
    channel = f"{settings.verdict_channel_prefix}{submission_id}"
    await redis.publish(channel, json.dumps(payload))


async def publish_run_event(run_id: str, payload: dict) -> None:
    """
    Unlike graded-submission verdicts (pub/sub, fire-and-forget — fine because
    the DB row is the source of truth if a client isn't listening yet), trial
    runs have no DB row. We RPUSH onto a list instead of PUBLISHing so a
    client that connects a moment late still sees every event, not just
    whatever was published after it subscribed.
    """
    redis = get_redis()
    key = f"{settings.run_result_list_prefix}{run_id}"
    await redis.rpush(key, json.dumps(payload))
    await redis.expire(key, settings.run_result_ttl_seconds)


async def judge_run(run_payload: dict) -> None:
    """
    Compiles and runs submitted code against only a problem's *sample* test
    cases. Nothing is written to the submissions table and no rate-limit
    budget beyond the dedicated trial-run limiter is consumed — this is the
    "Run" button, distinct from a graded "Submit".
    """
    run_id = run_payload["run_id"]
    problem_id = run_payload["problem_id"]
    language = run_payload["language"]
    source_code = run_payload["source_code"]

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Problem).options(selectinload(Problem.test_cases)).where(Problem.id == problem_id)
        )
        problem = result.scalar_one_or_none()

    if problem is None:
        await publish_run_event(run_id, {"final": True, "status": "error", "message": "Problem not found"})
        return

    samples = sorted((tc for tc in problem.test_cases if tc.is_sample), key=lambda t: t.ordinal)
    if not samples:
        await publish_run_event(
            run_id, {"final": True, "status": "error", "message": "This problem has no sample tests to run against"}
        )
        return

    lang = LANGUAGE_SPECS[language]
    workdir = make_submission_workdir(f"run-{run_id}")
    try:
        (workdir / lang.source_filename).write_text(source_code)

        compile_result = await asyncio.to_thread(compile_submission, lang, workdir)
        if not compile_result.success:
            await publish_run_event(
                run_id, {"final": True, "status": "compile_error", "compile_output": compile_result.output}
            )
            return

        any_failed = False
        for tc in samples:
            run_result = await asyncio.to_thread(
                run_test_case, lang, workdir, tc.input_data, problem.time_limit_seconds, problem.memory_limit_mb
            )
            passed = run_result.status == "ok" and normalize_output(run_result.stdout) == normalize_output(
                tc.expected_output
            )
            any_failed = any_failed or not passed
            await publish_run_event(
                run_id,
                {
                    "final": False,
                    "ordinal": tc.ordinal,
                    "passed": passed,
                    "status": run_result.status,
                    "input_data": tc.input_data,
                    "expected_output": tc.expected_output,
                    "actual_output": run_result.stdout if run_result.status == "ok" else None,
                    "stderr_snippet": (run_result.stderr or "")[:2000] if run_result.status != "ok" else None,
                    "time_ms": round(run_result.time_ms, 2),
                },
            )

        await publish_run_event(
            run_id, {"final": True, "status": "ok", "all_passed": not any_failed, "case_count": len(samples)}
        )
    finally:
        cleanup_workdir(workdir)


async def judge_submission(submission_id: str) -> None:
    t0 = time.monotonic()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Submission)
            .options(selectinload(Submission.problem).selectinload(Problem.test_cases))
            .where(Submission.id == submission_id)
        )
        submission = result.scalar_one_or_none()
        if submission is None:
            log.warning("Submission %s vanished before judging", submission_id)
            return

        submission.verdict = Verdict.JUDGING
        submission.worker_id = WORKER_ID
        await db.commit()
        await publish_verdict(submission_id, {"verdict": "JUDGING", "final": False})

        problem = submission.problem
        test_cases: list[TestCase] = sorted(problem.test_cases, key=lambda t: t.ordinal)
        lang = LANGUAGE_SPECS[submission.language]

        workdir = make_submission_workdir(submission_id)
        try:
            (workdir / lang.source_filename).write_text(submission.source_code)

            compile_result = await asyncio.to_thread(compile_submission, lang, workdir)
            if not compile_result.success:
                submission.verdict = Verdict.COMPILE_ERROR
                submission.compile_output = compile_result.output
                submission.total_test_count = len(test_cases)
                await _finalize(db, submission, submission_id)
                return

            total_weight = sum(tc.weight for tc in test_cases) or 1
            passed_weight = 0
            passed_count = 0
            max_time_ms = 0.0

            for tc in test_cases:
                run_result = await asyncio.to_thread(
                    run_test_case,
                    lang,
                    workdir,
                    tc.input_data,
                    problem.time_limit_seconds,
                    problem.memory_limit_mb,
                )
                max_time_ms = max(max_time_ms, run_result.time_ms)

                if run_result.status != "ok":
                    submission.verdict = _RUNTIME_ERROR_STATUS_TO_VERDICT.get(
                        run_result.status, Verdict.INTERNAL_ERROR
                    )
                    submission.stderr_snippet = (run_result.stderr or "")[:2000]
                    submission.failing_test_ordinal = tc.ordinal
                    break

                if normalize_output(run_result.stdout) == normalize_output(tc.expected_output):
                    passed_weight += tc.weight
                    passed_count += 1
                else:
                    submission.verdict = Verdict.WRONG_ANSWER
                    submission.failing_test_ordinal = tc.ordinal
                    submission.stderr_snippet = None
                    break
            else:
                # Loop completed without `break` -> every test case passed.
                submission.verdict = Verdict.ACCEPTED

            submission.passed_test_count = passed_count
            submission.total_test_count = len(test_cases)
            submission.score = round(100 * passed_weight / total_weight, 2)
            submission.max_time_ms = round(max_time_ms, 2)
            await _finalize(db, submission, submission_id)

        finally:
            cleanup_workdir(workdir)

    log.info(
        "Judged %s -> %s (%.0fms wall)",
        submission_id, submission.verdict.value, (time.monotonic() - t0) * 1000,
    )


async def _finalize(db, submission: Submission, submission_id: str) -> None:
    submission.judged_at = datetime.now(timezone.utc)
    await db.commit()
    await publish_verdict(
        submission_id,
        {
            "verdict": submission.verdict.value,
            "final": True,
            "passed_test_count": submission.passed_test_count,
            "total_test_count": submission.total_test_count,
            "score": submission.score,
        },
    )


async def worker_loop() -> None:
    redis = get_redis()
    semaphore = asyncio.Semaphore(settings.worker_concurrency)
    in_flight: set[asyncio.Task] = set()

    log.info("Worker %s started, concurrency=%d", WORKER_ID, settings.worker_concurrency)

    async def run_bounded(sub_id: str) -> None:
        async with semaphore:
            try:
                await judge_submission(sub_id)
            except Exception:
                log.exception("Unhandled error judging submission %s", sub_id)

    async def run_trial_bounded(run_payload: dict) -> None:
        async with semaphore:
            try:
                await judge_run(run_payload)
            except Exception:
                log.exception("Unhandled error on trial run %s", run_payload.get("run_id"))

    while not _shutdown.is_set():
        # BRPOP across both queues: whichever has work first wins. Trial runs
        # and graded submissions share the same worker pool/concurrency
        # limit — they're the same sandbox cost, just different bookkeeping.
        popped = await redis.brpop(
            [settings.submission_queue_key, settings.run_queue_key],
            timeout=settings.worker_poll_timeout_seconds,
        )
        if popped is None:
            in_flight = {t for t in in_flight if not t.done()}
            continue

        key, value = popped
        if key == settings.submission_queue_key:
            task = asyncio.create_task(run_bounded(value))
        else:
            task = asyncio.create_task(run_trial_bounded(json.loads(value)))
        in_flight.add(task)
        in_flight = {t for t in in_flight if not t.done()}

    if in_flight:
        log.info("Draining %d in-flight submissions before exit...", len(in_flight))
        await asyncio.gather(*in_flight, return_exceptions=True)


def _handle_signal(*_args) -> None:
    log.info("Shutdown signal received, will stop after draining in-flight work.")
    _shutdown.set()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _handle_signal)
    loop.run_until_complete(worker_loop())
