from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'sync_salary_table_columns'
down_revision = '1bc4cc17d392'  # Set this to the latest applied revision
branch_labels = None
depends_on = None

def upgrade():
    # No actual changes, just record that the columns exist
    pass

def downgrade():
    # Optional: define downgrade if needed
    pass
