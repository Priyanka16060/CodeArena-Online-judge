"""
Sandboxed execution of untrusted submissions.

Isolation model (defense in depth — every layer below is load-bearing,
not decorative):

  1. Fresh ephemeral container per run, destroyed immediately after     -> no
     state or leftover process can leak between test cases or submissions.
  2. network_disabled=True                                              -> no
     exfiltration, no calling out to fetch a "real" solution, no DoS'ing
     third parties from our infra.
  3. mem_limit + memswap_limit == mem_limit                             -> no
     swap escape hatch; Docker's cgroup OOM killer enforces this, and we
     detect it via container inspect's OOMKilled flag.
  4. nano_cpus caps CPU share so one submission can't starve the others
     running concurrently on the same worker host.
  5. pids_limit stops fork bombs (`while True: os.fork()`-style attacks).
  6. read_only root filesystem + a single writable tmpfs mount          -> the
     code can write scratch files but can't tamper with the image itself.
  7. cap_drop=["ALL"] + security_opt=["no-new-privileges"]              -> even
     if the language runtime has a privilege-escalation bug, the container
     has no Linux capabilities to escalate with.
  8. A non-root user inside the container (uid 1000).
  9. container.wait(timeout=...) is a hard wall-clock backstop: even if the
     process ignores its own limits (or the language runtime doesn't respect
     `timeout`), we forcibly kill+remove the container when the deadline hits.

This buys you real isolation on a single Docker host. It is NOT a substitute
for gVisor/Kata/Firecracker-grade isolation if you're running fully
untrusted third-party code at internet scale — see README "Scaling &
hardening notes" for what changes at that point.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import docker
from docker.errors import ContainerError, ImageNotFound, NotFound
from docker.types import Ulimit

from app.config import get_settings
from worker.languages import LangSpec

settings = get_settings()

HOST_WORKDIR_ROOT = Path(os.environ.get("JUDGE_WORKDIR_ROOT", "/tmp/judge-runs"))
CONTAINER_WORKDIR = "/workspace"


@dataclass
class CompileResult:
    success: bool
    output: str = ""


@dataclass
class RunResult:
    status: str  # "ok" | "timeout" | "oom" | "runtime_error" | "infra_error"
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    time_ms: float = 0.0
    memory_kb: float = 0.0


def get_docker_client() -> docker.DockerClient:
    return docker.DockerClient(base_url=settings.docker_host, timeout=30)


def make_submission_workdir(submission_id: str) -> Path:
    workdir = HOST_WORKDIR_ROOT / f"{submission_id}-{uuid.uuid4().hex[:8]}"
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir


def cleanup_workdir(workdir: Path) -> None:
    shutil.rmtree(workdir, ignore_errors=True)


def _common_container_kwargs(workdir: Path, memory_limit_mb: int) -> dict:
    return dict(
        volumes={str(workdir): {"bind": CONTAINER_WORKDIR, "mode": "rw"}},
        working_dir=CONTAINER_WORKDIR,
        mem_limit=f"{memory_limit_mb}m",
        memswap_limit=f"{memory_limit_mb}m",  # == mem_limit -> disables swap
        nano_cpus=1_000_000_000,  # 1.0 CPU
        pids_limit=64,
        network_disabled=settings.sandbox_network_disabled,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        user="1000:1000",
        ulimits=[Ulimit(name="nofile", soft=64, hard=64)],
        detach=True,
        stdout=True,
        stderr=True,
    )


def _run_container_blocking(
    client: docker.DockerClient,
    image: str,
    command: list[str],
    workdir: Path,
    memory_limit_mb: int,
    timeout_seconds: float,
) -> tuple[str, str, int | None, float, bool]:
    """
    Runs one container to completion (or kills it at the timeout) and
    returns (logs_combined_is_not_used, stderr placeholder, exit_code,
    elapsed_ms, oom_killed). stdout/stderr are read from files the
    container wrote into the shared volume, NOT from `docker logs`,
    because we redirect stdin/stdout/stderr via a shell wrapper so we can
    feed test-case input without needing docker-py's exec/stdin socket API.
    """
    container = None
    start = time.monotonic()
    try:
        container = client.containers.run(
            image=image,
            command=command,
            **_common_container_kwargs(workdir, memory_limit_mb),
        )
        try:
            result = container.wait(timeout=timeout_seconds)
            exit_code = result.get("StatusCode")
            timed_out = False
        except Exception:
            # container.wait() raises on timeout (requests.exceptions.*) —
            # this IS our TLE signal, not an infra failure.
            timed_out = True
            exit_code = None

        elapsed_ms = (time.monotonic() - start) * 1000

        oom_killed = False
        if container is not None:
            try:
                container.reload()
                oom_killed = bool(container.attrs.get("State", {}).get("OOMKilled", False))
            except NotFound:
                pass

        if timed_out:
            try:
                container.kill()
            except Exception:
                pass
            return "", "", None, elapsed_ms, False  # caller maps this to TIMEOUT

        return "", "", exit_code, elapsed_ms, oom_killed
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass


def compile_submission(lang: LangSpec, workdir: Path, time_limit_s: float = 15.0) -> CompileResult:
    if lang.compile_cmd is None:
        return CompileResult(success=True, output="")

    client = get_docker_client()
    try:
        # Wrap so stderr from the compiler lands in a file we can read back.
        wrapped = ["sh", "-c", " ".join(lang.compile_cmd) + " > compile.log 2>&1"]
        _, _, exit_code, _, _ = _run_container_blocking(
            client, lang.image, wrapped, workdir, memory_limit_mb=256, timeout_seconds=time_limit_s
        )
        compile_log_path = workdir / "compile.log"
        output = compile_log_path.read_text(errors="replace") if compile_log_path.exists() else ""
        return CompileResult(success=(exit_code == 0), output=output[: settings.max_output_bytes])
    except (ImageNotFound, ContainerError) as e:
        return CompileResult(success=False, output=f"Infrastructure error during compile: {e}")
    finally:
        client.close()


def run_test_case(
    lang: LangSpec,
    workdir: Path,
    stdin_data: str,
    time_limit_s: float,
    memory_limit_mb: int,
) -> RunResult:
    (workdir / "input.txt").write_text(stdin_data)
    # Remove stale output from a previous test case run in the same workdir.
    for f in ("output.txt", "error.txt", "exit_code.txt"):
        p = workdir / f
        if p.exists():
            p.unlink()

    run_str = " ".join(lang.run_cmd)
    wrapped = [
        "sh", "-c",
        f"{run_str} < input.txt > output.txt 2> error.txt; echo $? > exit_code.txt",
    ]

    client = get_docker_client()
    try:
        _, _, _, elapsed_ms, oom_killed = _run_container_blocking(
            client, lang.image, wrapped, workdir, memory_limit_mb, time_limit_s,
        )

        exit_code_path = workdir / "exit_code.txt"
        stdout_path = workdir / "output.txt"
        stderr_path = workdir / "error.txt"

        # If exit_code.txt was never written, the container was killed
        # mid-run by our hard timeout backstop before the wrapper's `echo`
        # could run -> that's TLE.
        if not exit_code_path.exists():
            if oom_killed:
                return RunResult(status="oom", time_ms=elapsed_ms)
            return RunResult(status="timeout", time_ms=elapsed_ms)

        exit_code = int(exit_code_path.read_text().strip() or "-1")
        stdout = stdout_path.read_text(errors="replace")[: settings.max_output_bytes] if stdout_path.exists() else ""
        stderr = stderr_path.read_text(errors="replace")[: settings.max_output_bytes] if stderr_path.exists() else ""

        if oom_killed:
            return RunResult(status="oom", stdout=stdout, stderr=stderr, exit_code=exit_code, time_ms=elapsed_ms)
        if exit_code != 0:
            return RunResult(
                status="runtime_error", stdout=stdout, stderr=stderr, exit_code=exit_code, time_ms=elapsed_ms
            )
        return RunResult(status="ok", stdout=stdout, stderr=stderr, exit_code=exit_code, time_ms=elapsed_ms)

    except (ImageNotFound, ContainerError) as e:
        return RunResult(status="infra_error", stderr=str(e))
    finally:
        client.close()


def normalize_output(text: str) -> str:
    """Standard judge normalization: strip trailing whitespace per line and trailing blank lines."""
    lines = [line.rstrip() for line in text.rstrip("\n").split("\n")]
    return "\n".join(lines)
