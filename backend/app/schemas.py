from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import Difficulty, Language, Verdict


# ---------- Auth ----------

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    username: str
    email: EmailStr
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Problems ----------

class TestCaseIn(BaseModel):
    input_data: str
    expected_output: str
    is_sample: bool = False
    weight: int = 1


class TestCaseSampleOut(BaseModel):
    ordinal: int
    input_data: str
    expected_output: str

    class Config:
        from_attributes = True


class ProblemCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9\-]+$")
    title: str
    statement: str
    difficulty: Difficulty = Difficulty.EASY
    time_limit_seconds: float = 2.0
    memory_limit_mb: int = 128
    test_cases: list[TestCaseIn]


class ProblemListOut(BaseModel):
    id: str
    slug: str
    title: str
    difficulty: Difficulty

    class Config:
        from_attributes = True


class ProblemDetailOut(BaseModel):
    id: str
    slug: str
    title: str
    statement: str
    difficulty: Difficulty
    time_limit_seconds: float
    memory_limit_mb: int
    sample_tests: list[TestCaseSampleOut]

    class Config:
        from_attributes = True


# ---------- Submissions ----------

class SubmissionCreate(BaseModel):
    problem_slug: str
    language: Language
    source_code: str = Field(min_length=1, max_length=100_000)


# ---------- Trial runs (sample tests only, nothing persisted) ----------

class RunCreate(BaseModel):
    problem_slug: str
    language: Language
    source_code: str = Field(min_length=1, max_length=100_000)


class RunAccepted(BaseModel):
    run_id: str


class PercentileOut(BaseModel):
    faster_than_pct: float | None
    less_memory_than_pct: float | None
    sample_size: int


class SubmissionOut(BaseModel):
    id: str
    problem_id: str
    language: Language
    verdict: Verdict
    passed_test_count: int
    total_test_count: int
    score: float
    max_time_ms: float
    max_memory_kb: float
    compile_output: str | None
    failing_test_ordinal: int | None
    stderr_snippet: str | None
    submitted_at: datetime
    judged_at: datetime | None
    worker_id: str | None

    class Config:
        from_attributes = True


class SubmissionSummaryOut(BaseModel):
    id: str
    problem_id: str
    verdict: Verdict
    submitted_at: datetime

    class Config:
        from_attributes = True
