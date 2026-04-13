"""
app_pkg/cli.py — Custom Flask CLI management commands.

Wire into create_app():
    from app_pkg.cli import register_cli
    register_cli(app)

Usage:
    flask db-seed          Create the first admin user (idempotent)
    flask db-stats         Show row counts for every table
    flask db-check         Verify DB connectivity and migration state
"""

from __future__ import annotations

import secrets

import click
from flask import Flask
from sqlalchemy import inspect, text


def register_cli(app: Flask) -> None:
    """Register all custom management commands on the Flask app."""

    @app.cli.command("db-seed")
    @click.option(
        "--email", default="admin@example.com", show_default=True, help="Admin email"
    )
    @click.option(
        "--password", default=None, help="Admin password (auto-generated if omitted)"
    )
    def db_seed(email: str, password: str | None) -> None:
        """Create the first admin user. Safe to run multiple times (idempotent)."""
        from models_pkg import User, db

        existing = User.query.filter_by(email=email.strip().lower()).first()
        if existing:
            click.echo(
                f"[db-seed] Admin already exists: {existing.email} (role={existing.role})"
            )
            return

        if not password:
            password = secrets.token_urlsafe(16)
            click.echo(f"[db-seed] Auto-generated password: {password}")
            click.echo("[db-seed] Save this password — it will not be shown again.")

        admin = User(email=email.strip().lower(), role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"[db-seed] Created admin user: {admin.email} (id={admin.id})")

    @app.cli.command("db-stats")
    def db_stats() -> None:
        """Print row counts for every table in the database."""
        from models_pkg import db

        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()

        if not table_names:
            click.echo("[db-stats] No tables found. Run: flask db upgrade")
            return

        click.echo(f"\n{'Table':<30} {'Rows':>10}")
        click.echo("-" * 42)
        with db.engine.connect() as conn:
            for table in sorted(table_names):
                try:
                    row = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()  # noqa: S608
                    count = row[0] if row else "?"
                except Exception:
                    count = "error"
                click.echo(f"{table:<30} {count:>10}")
        click.echo("")

    @app.cli.command("db-check")
    def db_check() -> None:
        """Verify database connectivity and print migration state."""
        from models_pkg import db

        # 1. Connectivity
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            click.echo("[db-check] ✓ Database connection OK")
            click.echo(f"[db-check]   URL: {str(db.engine.url)!r}")
        except Exception as exc:
            click.echo(f"[db-check] ✗ Database connection FAILED: {exc}", err=True)
            raise SystemExit(1) from exc

        # 2. Tables
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if tables:
            click.echo(f"[db-check] ✓ Tables present: {', '.join(sorted(tables))}")
        else:
            click.echo("[db-check] ✗ No tables found — run: flask db upgrade", err=True)

        # 3. Migration state (alembic_version table)
        try:
            with db.engine.connect() as conn:
                row = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).fetchone()
                if row:
                    click.echo(f"[db-check] ✓ Migration version: {row[0]}")
                else:
                    click.echo(
                        "[db-check] ✗ alembic_version is empty — run: flask db upgrade"
                    )
        except Exception:
            click.echo(
                "[db-check] ✗ alembic_version table missing — run: flask db upgrade"
            )
