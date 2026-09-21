"""initial_schema

Revision ID: 1353f612220a
Revises:
Create Date: 2026-04-13 09:55:12.093666

Creates the full users and audit_logs tables with all columns
matching the current model definitions in models_pkg/.
Subsequent migrations (92d5..., 18ea...) are now no-ops since
all columns are created here.

"""

from alembic import op
import sqlalchemy as sa

revision = "1353f612220a"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("github_id", sa.String(length=100), nullable=True),
        sa.Column("password_hash", sa.String(length=256), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="student"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # ponytail: boolean literal default (was SQLite-only "1", rejected by PostgreSQL).
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_github_id"), "users", ["github_id"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=20), nullable=False),
        # ponytail: boolean literal default (was SQLite-only "0", rejected by PostgreSQL).
        sa.Column("had_error", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("code_snippet", sa.String(length=200), nullable=True),
        # ponytail: no index=True here; ix_audit_logs_timestamp is created
        # explicitly below (dual definition fails on PostgreSQL).
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_audit_logs_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"]
    )
    op.create_index(
        op.f("ix_audit_logs_timestamp"), "audit_logs", ["timestamp"]
    )


def downgrade():
    op.drop_table("audit_logs")
    op.drop_table("users")
