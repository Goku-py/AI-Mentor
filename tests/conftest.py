"""
Shared pytest fixtures for the test suite.

Gemini API calls are mocked by default so tests never hit the real API.
This prevents rate-limiting on the free tier during local development and CI.
To run tests against the live API, set the env var: ENABLE_LIVE_AI=1
"""

import os
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_ai_mentorship():
    """
    Patch _get_ai_mentorship for every test so no real Gemini HTTP requests
    are made.  Tests that need the real API can opt out by setting the
    environment variable ENABLE_LIVE_AI=1.
    """
    if os.environ.get("ENABLE_LIVE_AI") == "1":
        yield  # let the real call through
        return

    with patch("analyzer._get_ai_mentorship", return_value="LOOKS_GOOD"):
        yield
