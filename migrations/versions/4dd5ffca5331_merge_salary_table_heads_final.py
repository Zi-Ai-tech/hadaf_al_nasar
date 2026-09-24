"""Merge salary table heads final

Revision ID: 4dd5ffca5331
Revises: sync_salary_table_columns, 61fada57c841
Create Date: 2025-12-24 08:00:55.646750

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4dd5ffca5331'
down_revision = ('sync_salary_table_columns', '61fada57c841')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
