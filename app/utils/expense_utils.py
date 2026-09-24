# app/utils/expense_utils.py
from datetime import datetime

def generate_expense_number():
    """Generate unique expense number"""
    from app.models.wps.expense import Expense
    
    # Format: EXP-YYYYMMDD-XXXX
    base_ref = f"EXP-{datetime.now().strftime('%Y%m%d')}"
    
    # Find existing expenses with same base today
    existing = Expense.query.filter(
        Expense.expense_number.like(f"{base_ref}-%")
    ).count()
    
    return f"{base_ref}-{existing + 1:04d}"