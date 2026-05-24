"""add_github_oauth_fields

Revision ID: 18eaf74e4ad2
Revises: 92d5df230aad
Create Date: 2026-04-13 12:16:22.896467

NO-OP: All columns were folded into the initial migration (1353f612220a).
Kept as a pass-through to preserve the Alembic revision chain.

"""

from alembic import op
import sqlalchemy as sa


revision = "18eaf74e4ad2"
down_revision = "92d5df230aad"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
