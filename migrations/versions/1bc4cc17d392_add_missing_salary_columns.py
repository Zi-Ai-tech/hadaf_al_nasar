from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1bc4cc17d392'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add missing columns safely using "IF NOT EXISTS"
    conn = op.get_bind()

    conn.execute(
        """
        ALTER TABLE salary
        ADD COLUMN IF NOT EXISTS bonuses_data TEXT,
        ADD COLUMN IF NOT EXISTS incentives_amount NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS deductions_data TEXT,
        ADD COLUMN IF NOT EXISTS deductions_amount NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS tax_amount NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS social_security_amount NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS other_deductions NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS gross_salary NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS total_deductions NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS net_salary NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS status VARCHAR(20),
        ADD COLUMN IF NOT EXISTS payment_date DATE,
        ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50),
        ADD COLUMN IF NOT EXISTS payment_reference VARCHAR(100),
        ADD COLUMN IF NOT EXISTS bank_account VARCHAR(50),
        ADD COLUMN IF NOT EXISTS working_days NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS actual_worked_days NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS leave_days NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS absent_days NUMERIC(10,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS wps_salary_file_url TEXT,
        ADD COLUMN IF NOT EXISTS wps_submission_date DATE,
        ADD COLUMN IF NOT EXISTS wps_status VARCHAR(50),
        ADD COLUMN IF NOT EXISTS wps_reference VARCHAR(100),
        ADD COLUMN IF NOT EXISTS processed_by INTEGER,
        ADD COLUMN IF NOT EXISTS processed_date TIMESTAMP,
        ADD COLUMN IF NOT EXISTS approved_by INTEGER,
        ADD COLUMN IF NOT EXISTS approved_date TIMESTAMP,
        ADD COLUMN IF NOT EXISTS notes TEXT,
        ADD COLUMN IF NOT EXISTS salary_slip_url TEXT
        """
    )

def downgrade():
    # Downgrade: remove columns only if they exist
    conn = op.get_bind()

    columns = [
        "bonuses_data", "incentives_amount", "deductions_data", "deductions_amount",
        "tax_amount", "social_security_amount", "other_deductions", "gross_salary",
        "total_deductions", "net_salary", "status", "payment_date", "payment_method",
        "payment_reference", "bank_account", "working_days", "actual_worked_days",
        "leave_days", "absent_days", "wps_salary_file_url", "wps_submission_date",
        "wps_status", "wps_reference", "processed_by", "processed_date", "approved_by",
        "approved_date", "notes", "salary_slip_url"
    ]

    for col in columns:
        conn.execute(f'ALTER TABLE salary DROP COLUMN IF EXISTS {col}')
