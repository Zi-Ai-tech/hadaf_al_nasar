# app/utils/employee_utils.py
from datetime import datetime

def generate_employee_id():
    """Generate unique employee ID"""
    from app.models.wps.employee import Employee
    
    # Format: EMP-YYYY-XXXX
    base_ref = f"EMP-{datetime.now().strftime('%Y')}"
    
    # Find existing employees with same base this year
    existing = Employee.query.filter(
        Employee.employee_code.like(f"{base_ref}-%")
    ).count()
    
    return f"{base_ref}-{existing + 1:04d}"