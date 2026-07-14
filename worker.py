"""worker.py — RQ worker entry point.

Bootstraps the Flask app in production mode and starts a worker that pulls
jobs from the configured RQ queue.

Usage:
    python worker.py
    FLASK_ENV=production python worker.py
"""

from __future__ import annotations

import os

from app_pkg import create_app
from app_pkg.extensions import get_rq_queue


def main() -> None:
    env = (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "production").strip().lower()
    os.environ.setdefault("FLASK_ENV", env)

    app = create_app(env)
    queue = get_rq_queue()

    with app.app_context():
        app.logger.info(
            "Starting RQ worker on queue=%s with timeout=%s",
            queue.name,
            os.environ.get("RQ_WORKER_TIMEOUT", "300"),
        )
        worker = queue.create_worker()
        worker.work()


if __name__ == "__main__":
    main()
