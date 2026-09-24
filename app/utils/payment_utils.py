# app/utils/payment_utils.py
from datetime import datetime

def generate_payment_reference():
    """Generate unique payment reference"""
    from app.models.finance.payment import Payment
    
    # Format: PAY-YYYYMMDD-XXXX
    base_ref = f"PAY-{datetime.now().strftime('%Y%m%d')}"
    
    # Find existing payments with same base today
    existing = Payment.query.filter(
        Payment.payment_reference.like(f"{base_ref}-%")
    ).count()
    
    return f"{base_ref}-{existing + 1:04d}"