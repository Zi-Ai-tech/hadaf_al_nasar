"""Normalize expense type enum labels and include current values.

Revision ID: c2e8f4a1b7d0
Revises: b8bfa958a2d9
Create Date: 2026-09-20

"""
from alembic import op
import sqlalchemy as sa


revision = 'c2e8f4a1b7d0'
down_revision = 'b567acf32664'
branch_labels = None
depends_on = None


EXPENSE_TYPES = (
    'operational',
    'vehicle',
    'employee',
    'office',
    'administrative',
    'maintenance',
    'fuel',
    'repair',
    'insurance',
    'utilities',
    'rent',
    'salary',
    'training',
    'parts',
    'trip',
    'other',
)


def upgrade():
    quoted_types = ', '.join(f"'{expense_type}'" for expense_type in EXPENSE_TYPES)
    op.execute(sa.text(
        "ALTER TABLE expense "
        "ALTER COLUMN expense_type TYPE text "
        "USING expense_type::text"
    ))
    op.execute(sa.text("DROP TYPE expensetype"))
    op.execute(sa.text(f"CREATE TYPE expensetype AS ENUM ({quoted_types})"))
    op.execute(sa.text(
        "ALTER TABLE expense "
        "ALTER COLUMN expense_type TYPE expensetype "
        "USING lower(expense_type)::expensetype"
    ))


def downgrade():
    op.execute(sa.text(
        "ALTER TABLE expense "
        "ALTER COLUMN expense_type TYPE text "
        "USING expense_type::text"
    ))
    op.execute(sa.text("DROP TYPE expensetype"))
    op.execute(sa.text(
        "CREATE TYPE expensetype AS ENUM "
        "('FUEL', 'MAINTENANCE', 'PARTS', 'SALARY', 'TRIP', 'OTHER')"
    ))
    op.execute(sa.text(
        "ALTER TABLE expense "
        "ALTER COLUMN expense_type TYPE expensetype "
        "USING upper(expense_type)::expensetype"
    ))
