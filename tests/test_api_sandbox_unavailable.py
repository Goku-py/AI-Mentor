import os

import pytest

import analyzer


def test_analyze_sandbox_unavailable(client, monkeypatch):
    """When Docker is not available and host fallback is disabled,
    the analyze endpoint should return an `execution` dict with an
    error of type `SandboxUnavailable`.
    """
    # Ensure host fallback is disabled for this test
    monkeypatch.setenv("ALLOW_HOST_EXECUTION_FALLBACK", "0")
    # Simulate Docker SDK not installed
    monkeypatch.setattr(analyzer, "docker", None)

    resp = client.post(
        "/api/v1/analyze",
        json={"code": "print(\"hi\")", "language": "python"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    # API should include an execution dict
    assert "execution" in data and isinstance(data["execution"], dict)
    err = data["execution"].get("error")
    assert isinstance(err, dict)
    assert err.get("type") == "SandboxUnavailable"
