"""app_pkg/jobs — Background job tasks executed by RQ workers."""

from __future__ import annotations

from app_pkg.jobs.analyze_job import run_analyze_job

__all__ = ["run_analyze_job"]
