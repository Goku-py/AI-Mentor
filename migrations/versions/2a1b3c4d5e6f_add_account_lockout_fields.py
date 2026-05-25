"""add_account_lockout_fields

Revision ID: 2a1b3c4d5e6f
Revises: 18eaf74e4ad2
Create Date: 2026-05-24 18:00:00.000000

Adds login_attempts and locked_until columns to the users table
for auth hardening (account lockout after N failed login attempts).

"""

from alembic import op
import sqlalchemy as sa


revision = "2a1b3c4d5e6f"
down_revision = "18eaf74e4ad2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("login_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "users",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("users", "locked_until")
    op.drop_column("users", "login_attempts")
