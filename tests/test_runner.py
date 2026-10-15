"""Tests for the sandbox execution runner's HTTP boundary.

These cover the trust boundary only: auth, input validation and error mapping.
Actual container execution needs a Docker daemon and is covered separately.
"""

import pytest

from runner.server import create_runner_app

SECRET = "test-runner-secret"


@pytest.fixture
def runner_app(monkeypatch):
    monkeypatch.setenv("EXECUTION_RUNNER_SECRET", SECRET)
    app = create_runner_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(runner_app):
    return runner_app.test_client()


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {SECRET}"}


def test_refuses_to_start_without_secret(monkeypatch):
    monkeypatch.setenv("EXECUTION_RUNNER_SECRET", "")
    with pytest.raises(RuntimeError, match="EXECUTION_RUNNER_SECRET"):
        create_runner_app()


def test_healthz_reports_sandbox_status(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert "ok" in response.get_json()


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer wrong-secret"},
        {"Authorization": SECRET},
        {"Authorization": "Basic test-runner-secret"},
    ],
)
def test_execute_rejects_bad_credentials(client, headers):
    response = client.post(
        "/execute",
        json={"code": "print(1)", "language": "python", "image": "x", "cmd": ["python"]},
        headers=headers,
    )
    assert response.status_code == 401


def test_execute_rejects_empty_code(client, auth):
    response = client.post(
        "/execute",
        json={"code": "   ", "language": "python", "image": "x", "cmd": ["python"]},
        headers=auth,
    )
    assert response.status_code == 400


def test_execute_rejects_oversized_code(client, auth):
    response = client.post(
        "/execute",
        json={
            "code": "a" * (102_400 + 1),
            "language": "python",
            "image": "x",
            "cmd": ["python"],
        },
        headers=auth,
    )
    assert response.status_code == 400


def test_execute_rejects_non_list_cmd(client, auth):
    response = client.post(
        "/execute",
        json={"code": "print(1)", "language": "python", "image": "x", "cmd": "python x.py"},
        headers=auth,
    )
    assert response.status_code == 400


def test_execute_clamps_timeout(client, auth, monkeypatch):
    seen = {}

    def fake_run(code, language, image, cmd, timeout):
        seen["timeout"] = timeout
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr("runner.server.run_in_sandbox_local", fake_run)
    response = client.post(
        "/execute",
        json={
            "code": "print(1)",
            "language": "python",
            "image": "x",
            "cmd": ["python"],
            "timeout": 9999,
        },
        headers=auth,
    )
    assert response.status_code == 200
    assert seen["timeout"] == 30


def test_execute_maps_unexpected_failure_to_500(client, auth, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr("runner.server.run_in_sandbox_local", boom)
    response = client.post(
        "/execute",
        json={"code": "print(1)", "language": "python", "image": "x", "cmd": ["python"]},
        headers=auth,
    )
    assert response.status_code == 500
