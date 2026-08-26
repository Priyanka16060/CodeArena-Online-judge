import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal, get_db
from app.deps import get_current_user
from app.models import Problem, Submission, User, Verdict
from app.rate_limit import enforce_run_rate_limit, enforce_submit_rate_limit
from app.redis_client import get_redis
from app.schemas import (
    PercentileOut,
    RunAccepted,
    RunCreate,
    SubmissionCreate,
    SubmissionOut,
    SubmissionSummaryOut,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])
settings = get_settings()


@router.post("", response_model=SubmissionOut, status_code=status.HTTP_202_ACCEPTED)
async def create_submission(
    payload: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Rate limit BEFORE touching the DB or queue — cheapest rejection path.
    await enforce_submit_rate_limit(current_user.id)

    # 2. Resolve problem.
    result = await db.execute(select(Problem).where(Problem.slug == payload.problem_slug))
    problem = result.scalar_one_or_none()
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    # 3. Persist submission row in PENDING state — this is the durable
    #    source of truth. The queue entry is just a pointer to it, so if a
    #    worker crashes mid-judge, the row still exists and can be requeued.
    submission = Submission(
        user_id=current_user.id,
        problem_id=problem.id,
        language=payload.language,
        source_code=payload.source_code,
        verdict=Verdict.QUEUED,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    # 4. Push onto the work queue. Any of N worker processes/replicas can
    #    pick this up via BRPOP — that's what gives us horizontal scaling
    #    of judging throughput independent of the API layer.
    redis = get_redis()
    await redis.lpush(settings.submission_queue_key, submission.id)

    return submission


@router.get("/{submission_id}", response_model=SubmissionOut)
async def get_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    submission = result.scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not your submission")
    return submission


@router.get("", response_model=list[SubmissionSummaryOut])
async def list_my_submissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 50,
):
    result = await db.execute(
        select(Submission)
        .where(Submission.user_id == current_user.id)
        .order_by(Submission.submitted_at.desc())
        .limit(min(limit, 200))
    )
    return result.scalars().all()


@router.post("/run", response_model=RunAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    payload: RunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    "Run" — judges against sample tests only, nothing persisted, separate
    rate-limit budget from real "Submit"s. Use this for fast iteration
    before spending a graded submission.
    """
    await enforce_run_rate_limit(current_user.id)

    result = await db.execute(select(Problem).where(Problem.slug == payload.problem_slug))
    problem = result.scalar_one_or_none()
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    run_id = str(uuid.uuid4())
    redis = get_redis()
    await redis.lpush(
        settings.run_queue_key,
        json.dumps(
            {
                "run_id": run_id,
                "problem_id": problem.id,
                "language": payload.language.value,
                "source_code": payload.source_code,
            }
        ),
    )
    return RunAccepted(run_id=run_id)


@router.websocket("/run/{run_id}/live")
async def run_live(websocket: WebSocket, run_id: str):
    """
    Streams trial-run events from the Redis list a worker RPUSHes onto (see
    judge_worker.publish_run_event). A list — not pub/sub — is used here on
    purpose: there's no DB row to check on late connect, so we need every
    event buffered until a client reads it, not just events published while
    someone happens to be subscribed.
    """
    await websocket.accept()
    redis = get_redis()
    key = f"{settings.run_result_list_prefix}{run_id}"

    try:
        while True:
            popped = await redis.blpop(key, timeout=15.0)
            if popped is None:
                await websocket.send_json({"ping": True})
                continue
            _key, raw = popped
            data = json.loads(raw)
            await websocket.send_json(data)
            if data.get("final"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await redis.delete(key)
        await websocket.close()


@router.get("/{submission_id}/percentile", response_model=PercentileOut)
async def get_submission_percentile(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    We don't attempt to infer algorithmic time/space complexity (Big-O) from
    arbitrary submitted code — that's not reliably derivable in general.
    Instead, like most real judges, we report where this submission's
    measured runtime/memory falls among other ACCEPTED submissions for the
    same problem: "faster than X%", "uses less memory than Y%".
    """
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    submission = result.scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not your submission")

    if submission.verdict != Verdict.ACCEPTED:
        return PercentileOut(faster_than_pct=None, less_memory_than_pct=None, sample_size=0)

    peers = await db.execute(
        select(Submission.max_time_ms, Submission.max_memory_kb).where(
            Submission.problem_id == submission.problem_id,
            Submission.verdict == Verdict.ACCEPTED,
        )
    )
    rows = peers.all()
    total = len(rows)
    if total <= 1:
        return PercentileOut(faster_than_pct=100.0, less_memory_than_pct=100.0, sample_size=total)

    slower_or_equal = sum(1 for t, _m in rows if t >= submission.max_time_ms)
    more_or_equal_mem = sum(1 for _t, m in rows if m >= submission.max_memory_kb)
    return PercentileOut(
        faster_than_pct=round(100 * slower_or_equal / total, 1),
        less_memory_than_pct=round(100 * more_or_equal_mem / total, 1),
        sample_size=total,
    )


@router.websocket("/{submission_id}/live")
async def submission_live_verdict(websocket: WebSocket, submission_id: str):
    """
    Streams the verdict the moment a worker publishes it, instead of making
    the client poll GET /submissions/{id} repeatedly. Falls back cleanly:
    if the submission is already terminal by the time the client connects,
    we send it immediately and close.
    """
    await websocket.accept()
    redis = get_redis()
    channel = f"{settings.verdict_channel_prefix}{submission_id}"

    # Check current state first in case judging already finished.
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Submission).where(Submission.id == submission_id))
        submission = result.scalar_one_or_none()

    if submission is None:
        await websocket.send_json({"error": "submission not found"})
        await websocket.close()
        return

    terminal_states = {
        Verdict.ACCEPTED, Verdict.WRONG_ANSWER, Verdict.TIME_LIMIT_EXCEEDED,
        Verdict.MEMORY_LIMIT_EXCEEDED, Verdict.RUNTIME_ERROR, Verdict.COMPILE_ERROR,
        Verdict.INTERNAL_ERROR,
    }
    if submission.verdict in terminal_states:
        await websocket.send_json({"verdict": submission.verdict.value, "final": True})
        await websocket.close()
        return

    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
            if message is not None:
                data = json.loads(message["data"])
                await websocket.send_json(data)
                if data.get("final"):
                    break
            else:
                # Heartbeat, also lets us detect client disconnects promptly.
                await websocket.send_json({"ping": True})
            await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await websocket.close()
