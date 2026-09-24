# app/utils/transaction_utils.py
from datetime import datetime

def generate_transaction_number():
    """Generate unique transaction reference"""
    from app.models.finance.transaction import Transaction
    
    # Format: TRX-YYYYMMDD-XXXX
    base_ref = f"TRX-{datetime.now().strftime('%Y%m%d')}"
    
    # Find existing transactions with same base today
    existing = Transaction.query.filter(
        Transaction.transaction_number.like(f"{base_ref}-%")
    ).count()
    
    return f"{base_ref}-{existing + 1:04d}"