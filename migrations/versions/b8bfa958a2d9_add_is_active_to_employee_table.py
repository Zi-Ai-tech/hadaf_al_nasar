"""Add is_active to employee table

Revision ID: b8bfa958a2d9
Revises: 4dd5ffca5331
Create Date: 2025-12-25 07:01:28.180057

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8bfa958a2d9'
down_revision = '4dd5ffca5331'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'employee',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true())
    )

def downgrade():
    op.drop_column('employee', 'is_active')

