from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Core ---
    app_name: str = "CodeArena Online Judge"
    environment: str = "development"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://judge:judge@postgres:5432/judge_db"

    # --- Redis (queue + rate limiting + pub/sub for live verdicts) ---
    redis_url: str = "redis://redis:6379/0"
    submission_queue_key: str = "judge:submission_queue"
    verdict_channel_prefix: str = "judge:verdict:"

    # --- "Run" (sample-tests-only, not persisted) ---
    run_queue_key: str = "judge:run_queue"
    run_result_list_prefix: str = "judge:run:"
    run_result_ttl_seconds: int = 120
    run_rate_limit: int = 10           # max trial runs
    run_rate_window_seconds: int = 60  # per this many seconds

    # --- Auth ---
    jwt_secret: str = "change-me-in-prod-please"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # --- Rate limiting (sliding window, per user) ---
    submit_rate_limit: int = 5          # max submissions
    submit_rate_window_seconds: int = 60  # per this many seconds

    # --- Sandbox execution limits (defaults, overridable per-problem) ---
    default_time_limit_seconds: float = 2.0
    default_memory_limit_mb: int = 128
    max_time_limit_seconds: float = 10.0
    max_output_bytes: int = 64 * 1024  # 64 KB, prevents output-bomb DoS

    # --- Worker / sandbox ---
    docker_host: str = "unix:///var/run/docker.sock"
    sandbox_network_disabled: bool = True
    worker_poll_timeout_seconds: int = 5
    worker_concurrency: int = 4  # containers this worker process runs in parallel

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
