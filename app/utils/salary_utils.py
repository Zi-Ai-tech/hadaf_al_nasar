# app/utils/salary_utils.py
from datetime import datetime

def generate_salary_number():
    """Generate unique salary number"""
    from app.models.wps.salary import Salary
    
    # Format: SAL-YYYYMM-XXXX
    base_ref = f"SAL-{datetime.now().strftime('%Y%m')}"
    
    # Find existing salaries with same base this month
    existing = Salary.query.filter(
        Salary.salary_number.like(f"{base_ref}-%")
    ).count()
    
    return f"{base_ref}-{existing + 1:04d}"