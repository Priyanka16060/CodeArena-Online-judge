"""
These tests hit a REAL running stack (`docker compose up -d`) on
http://localhost:8000, including a real judging worker executing real
Docker containers. They are the tests that actually prove the system works
end-to-end — the unit tests only cover pure logic in isolation.

Run with:  docker compose up -d && pytest tests/test_api_integration.py -v

They auto-skip if the API isn't reachable, so `pytest` alone (unit tests
only) still works without Docker running.
"""

import time
import uuid

import httpx
import pytest

BASE_URL = "http://localhost:8000"


def _api_is_up() -> bool:
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=2.0)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(not _api_is_up(), reason="API stack not running on localhost:8000")


@pytest.fixture
def client():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    username = f"pytest_{uuid.uuid4().hex[:8]}"
    client.post(
        "/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "testpass123"},
    )
    resp = client.post("/auth/login", data={"username": username, "password": "testpass123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_and_login(client):
    username = f"pytest_{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "testpass123"},
    )
    assert r.status_code == 201

    r = client.post("/auth/login", data={"username": username, "password": "wrong"})
    assert r.status_code == 401

    r = client.post("/auth/login", data={"username": username, "password": "testpass123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_list_problems_seeded(client):
    r = client.get("/problems")
    assert r.status_code == 200
    slugs = {p["slug"] for p in r.json()}
    assert "two-sum" in slugs  # requires `python -m scripts.seed_problems` to have been run


def test_accepted_submission_end_to_end(client, auth_headers):
    """Submits a correct Python solution and polls until the worker judges it ACCEPTED."""
    source = (
        "nums = list(map(int, input().split()))\n"
        "target = int(input())\n"
        "seen = {}\n"
        "for i, n in enumerate(nums):\n"
        "    if target - n in seen:\n"
        "        print(seen[target - n], i)\n"
        "        break\n"
        "    seen[n] = i\n"
    )
    r = client.post(
        "/submissions",
        json={"problem_slug": "two-sum", "language": "python", "source_code": source},
        headers=auth_headers,
    )
    assert r.status_code == 202
    submission_id = r.json()["id"]

    verdict = _poll_until_final(client, submission_id, auth_headers)
    assert verdict["verdict"] == "ACCEPTED"
    assert verdict["passed_test_count"] == verdict["total_test_count"]


def test_wrong_answer_submission(client, auth_headers):
    source = "print('definitely wrong')\n"
    r = client.post(
        "/submissions",
        json={"problem_slug": "reverse-string", "language": "python", "source_code": source},
        headers=auth_headers,
    )
    submission_id = r.json()["id"]
    verdict = _poll_until_final(client, submission_id, auth_headers)
    assert verdict["verdict"] == "WRONG_ANSWER"


def test_infinite_loop_is_killed_by_time_limit(client, auth_headers):
    source = "while True:\n    pass\n"
    r = client.post(
        "/submissions",
        json={"problem_slug": "reverse-string", "language": "python", "source_code": source},
        headers=auth_headers,
    )
    submission_id = r.json()["id"]
    verdict = _poll_until_final(client, submission_id, auth_headers, timeout_s=15)
    assert verdict["verdict"] == "TIME_LIMIT_EXCEEDED"


def test_compile_error_is_reported(client, auth_headers):
    source = "int main() { this is not valid c++ "
    r = client.post(
        "/submissions",
        json={"problem_slug": "reverse-string", "language": "cpp", "source_code": source},
        headers=auth_headers,
    )
    submission_id = r.json()["id"]
    verdict = _poll_until_final(client, submission_id, auth_headers)
    assert verdict["verdict"] == "COMPILE_ERROR"


def test_rate_limit_blocks_burst_submissions(client, auth_headers):
    source = "print(input()[::-1])"
    statuses = []
    for _ in range(10):
        r = client.post(
            "/submissions",
            json={"problem_slug": "reverse-string", "language": "python", "source_code": source},
            headers=auth_headers,
        )
        statuses.append(r.status_code)
    assert 429 in statuses, "expected the sliding-window rate limiter to reject part of the burst"


def _poll_until_final(client, submission_id, headers, timeout_s: float = 10.0) -> dict:
    deadline = time.time() + timeout_s
    terminal = {
        "ACCEPTED", "WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "MEMORY_LIMIT_EXCEEDED",
        "RUNTIME_ERROR", "COMPILE_ERROR", "INTERNAL_ERROR",
    }
    while time.time() < deadline:
        r = client.get(f"/submissions/{submission_id}", headers=headers)
        body = r.json()
        if body["verdict"] in terminal:
            return body
        time.sleep(0.3)
    raise AssertionError(f"submission {submission_id} did not reach a terminal verdict in {timeout_s}s")
