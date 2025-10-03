"""add offer model

Revision ID: 8f3a2b1c9d4e
Revises: 5d74bcf385ba
Create Date: 2025-10-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8f3a2b1c9d4e'
down_revision = '5d74bcf385ba'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'offer',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=True),
        sa.Column('image_url', sa.String(length=200), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('offer')
