"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

difficulty_enum = postgresql.ENUM("EASY", "MEDIUM", "HARD", name="difficulty")
language_enum = postgresql.ENUM("python", "cpp", "java", "javascript", name="language")
verdict_enum = postgresql.ENUM(
    "PENDING", "QUEUED", "JUDGING", "ACCEPTED", "WRONG_ANSWER", "TIME_LIMIT_EXCEEDED",
    "MEMORY_LIMIT_EXCEEDED", "RUNTIME_ERROR", "COMPILE_ERROR", "INTERNAL_ERROR",
    name="verdict",
)


def upgrade() -> None:
    bind = op.get_bind()
    difficulty_enum.create(bind, checkfirst=True)
    language_enum.create(bind, checkfirst=True)
    verdict_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "problems",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("difficulty", difficulty_enum, server_default="EASY"),
        sa.Column("time_limit_seconds", sa.Float(), server_default="2.0"),
        sa.Column("memory_limit_mb", sa.Integer(), server_default="128"),
        sa.Column("is_published", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_problems_slug", "problems", ["slug"])

    op.create_table(
        "test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("problem_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("problems.id", ondelete="CASCADE")),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("input_data", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.false()),
        sa.Column("weight", sa.Integer(), server_default="1"),
        sa.UniqueConstraint("problem_id", "ordinal", name="uq_problem_ordinal"),
    )

    op.create_table(
        "submissions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("problem_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("problems.id", ondelete="CASCADE")),
        sa.Column("language", language_enum, nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("verdict", verdict_enum, server_default="PENDING"),
        sa.Column("passed_test_count", sa.Integer(), server_default="0"),
        sa.Column("total_test_count", sa.Integer(), server_default="0"),
        sa.Column("score", sa.Float(), server_default="0.0"),
        sa.Column("max_time_ms", sa.Float(), server_default="0.0"),
        sa.Column("max_memory_kb", sa.Float(), server_default="0.0"),
        sa.Column("compile_output", sa.Text(), nullable=True),
        sa.Column("failing_test_ordinal", sa.Integer(), nullable=True),
        sa.Column("stderr_snippet", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("judged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_submissions_verdict", "submissions", ["verdict"])


def downgrade() -> None:
    op.drop_table("submissions")
    op.drop_table("test_cases")
    op.drop_table("problems")
    op.drop_table("users")
    verdict_enum.drop(op.get_bind(), checkfirst=True)
    language_enum.drop(op.get_bind(), checkfirst=True)
    difficulty_enum.drop(op.get_bind(), checkfirst=True)
