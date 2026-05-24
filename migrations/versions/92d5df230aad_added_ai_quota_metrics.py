"""Added AI quota metrics

Revision ID: 92d5df230aad
Revises: 1353f612220a
Create Date: 2026-04-13 11:56:58.876467

NO-OP: All columns were folded into the initial migration (1353f612220a).
Kept as a pass-through to preserve the Alembic revision chain.

"""

from alembic import op
import sqlalchemy as sa


revision = "92d5df230aad"
down_revision = "1353f612220a"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
