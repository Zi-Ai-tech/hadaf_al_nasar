# app/utils/income_utils.py
from datetime import datetime

def generate_income_number():
    """Generate unique income number"""
    from app.models.wps.income import Income
    
    # Format: INC-YYYYMMDD-XXXX
    base_ref = f"INC-{datetime.now().strftime('%Y%m%d')}"
    
    # Find existing incomes with same base today
    existing = Income.query.filter(
        Income.income_number.like(f"{base_ref}-%")
    ).count()
    
    return f"{base_ref}-{existing + 1:04d}"