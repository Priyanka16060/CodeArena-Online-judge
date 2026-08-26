from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import get_current_admin
from app.models import Problem, TestCase, User
from app.schemas import ProblemCreate, ProblemDetailOut, ProblemListOut

router = APIRouter(prefix="/problems", tags=["problems"])


@router.get("", response_model=list[ProblemListOut])
async def list_problems(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Problem).where(Problem.is_published.is_(True)).order_by(Problem.created_at)
    )
    return result.scalars().all()


@router.get("/{slug}", response_model=ProblemDetailOut)
async def get_problem(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Problem).options(selectinload(Problem.test_cases)).where(Problem.slug == slug)
    )
    problem = result.scalar_one_or_none()
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")

    # Attach only sample test cases with sequential ordinals for display.
    # NOTE: ProblemDetailOut.sample_tests is a required field, but the ORM
    # `Problem` object has no `sample_tests` attribute — only `test_cases`
    # (all cases, hidden + sample). Calling model_validate(problem) directly
    # fails validation before we get the chance to fill sample_tests in.
    # Build the dict ourselves instead of validating the bare ORM object.
    samples = [tc for tc in problem.test_cases if tc.is_sample]
    out = ProblemDetailOut(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        statement=problem.statement,
        difficulty=problem.difficulty,
        time_limit_seconds=problem.time_limit_seconds,
        memory_limit_mb=problem.memory_limit_mb,
        sample_tests=[
            {"ordinal": i, "input_data": tc.input_data, "expected_output": tc.expected_output}
            for i, tc in enumerate(samples)
        ],
    )
    return out


@router.post("", response_model=ProblemDetailOut, status_code=status.HTTP_201_CREATED)
async def create_problem(
    payload: ProblemCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    if not payload.test_cases:
        raise HTTPException(status_code=400, detail="At least one test case is required")

    problem = Problem(
        slug=payload.slug,
        title=payload.title,
        statement=payload.statement,
        difficulty=payload.difficulty,
        time_limit_seconds=payload.time_limit_seconds,
        memory_limit_mb=payload.memory_limit_mb,
    )
    problem.test_cases = [
        TestCase(
            ordinal=i,
            input_data=tc.input_data,
            expected_output=tc.expected_output,
            is_sample=tc.is_sample,
            weight=tc.weight,
        )
        for i, tc in enumerate(payload.test_cases)
    ]

    db.add(problem)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A problem with this slug already exists")
    await db.refresh(problem, attribute_names=["test_cases"])

    out = ProblemDetailOut(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        statement=problem.statement,
        difficulty=problem.difficulty,
        time_limit_seconds=problem.time_limit_seconds,
        memory_limit_mb=problem.memory_limit_mb,
        sample_tests=[
            {"ordinal": i, "input_data": tc.input_data, "expected_output": tc.expected_output}
            for i, tc in enumerate(t for t in problem.test_cases if t.is_sample)
        ],
    )
    return out
