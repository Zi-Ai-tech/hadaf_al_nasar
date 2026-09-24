"""Link income records to their completed payments.

Revision ID: d4f7a9c2e1b3
Revises: c2e8f4a1b7d0
Create Date: 2026-09-20

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4f7a9c2e1b3'
down_revision = 'c2e8f4a1b7d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('income', sa.Column('payment_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_income_payment_id_payment',
        'income',
        'payment',
        ['payment_id'],
        ['id'],
    )
    op.create_unique_constraint('uq_income_payment_id', 'income', ['payment_id'])


def downgrade():
    op.drop_constraint('uq_income_payment_id', 'income', type_='unique')
    op.drop_constraint('fk_income_payment_id_payment', 'income', type_='foreignkey')
    op.drop_column('income', 'payment_id')
