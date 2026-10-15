"""drop_unused_audit_token_columns

Revision ID: c3d9e7a15b64
Revises: 2a1b3c4d5e6f
Create Date: 2026-05-25 09:00:00.000000

Two changes to audit_logs:

1. Drops prompt_tokens and completion_tokens.  No code path ever wrote them
   (only total_tokens and ip_address are referenced, and total_tokens is what
   to_dict() reports as "tokens"), so they were dead weight carrying a NOT NULL
   default on every insert.  Both are restorable by downgrade(); the data was
   always 0.

2. Adds ondelete="CASCADE" to the user_id -> users.id foreign key so deleting
   a user cannot leave orphaned audit rows.

Uses op.batch_alter_table in its default "auto" mode: SQLite cannot ALTER TABLE
... DROP COLUMN or drop a constraint, so the table is reflected and recreated
there; on PostgreSQL the same calls emit plain ALTER TABLE statements (no
recreate, no reflection), which keeps it workable in offline --sql mode.

Downgrade restores both columns and the original (non-cascading) FK.

"""

from alembic import op
import sqlalchemy as sa


revision = "c3d9e7a15b64"
down_revision = "2a1b3c4d5e6f"
branch_labels = None
depends_on = None


# The FK created by the initial migration is unnamed on SQLite, so drop_constraint
# cannot resolve it. Alembic's naming_convention assigns a deterministic name to
# unnamed constraints during the batch recreate. On PostgreSQL the constraint is
# already named fk_audit_logs_user_id, so the convention is a no-op there.
_NAMING_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s"}


def upgrade():
    with op.batch_alter_table("audit_logs", naming_convention=_NAMING_CONVENTION) as batch_op:
        batch_op.drop_column("prompt_tokens")
        batch_op.drop_column("completion_tokens")
        batch_op.drop_constraint("fk_audit_logs_user_id", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_audit_logs_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )


def downgrade():
    with op.batch_alter_table("audit_logs", naming_convention=_NAMING_CONVENTION) as batch_op:
        batch_op.add_column(
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )
        batch_op.add_column(
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )
        batch_op.drop_constraint("fk_audit_logs_user_id", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_audit_logs_user_id", "users", ["user_id"], ["id"]
        )