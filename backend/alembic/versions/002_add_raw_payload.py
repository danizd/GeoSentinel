"""Add raw_payload column to events_canonical

Revision ID: 002
Revises: 001
Create Date: 2026-05-14 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'events_canonical',
        sa.Column('raw_payload', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('events_canonical', 'raw_payload')