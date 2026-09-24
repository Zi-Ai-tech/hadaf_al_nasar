# app/utils/invoice_income_sync.py
from app.models.finance.invoice import Invoice
from app.models.wps.income import Income

def fix_all_invoice_income_records():
    """
    Fix income records for all invoices
    Returns count of fixed invoices
    """
    invoices = Invoice.query.all()
    fixed_count = 0
    
    for invoice in invoices:
        # Sync income from existing payments
        created = invoice.sync_income_from_payments()
        
        # Verify and update income_created flag
        total_payments = sum(p.amount for p in invoice.payments if p.is_completed)
        total_income = sum(i.total_amount for i in invoice.invoice_incomes)
        if abs(total_payments - total_income) <= 0.01 and invoice.amount_paid >= invoice.total_amount:
            invoice.income_created = True
            invoice.save()
            fixed_count += 1
    
    return fixed_count

def get_invoice_income_report(invoice_id):
    """
    Get detailed report of invoice income vs payments
    """
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return None
    
    total_payments = sum(p.amount for p in invoice.payments if p.is_completed)
    total_income = sum(i.total_amount for i in invoice.invoice_incomes)
    
    return {
        'invoice_id': invoice.id,
        'invoice_number': invoice.invoice_number,
        'total_amount': invoice.total_amount,
        'amount_paid': invoice.amount_paid,
        'total_payments': total_payments,
        'total_income': total_income,
        'income_created': invoice.income_created,
        'discrepancy': total_payments - total_income,
        'payments': [{
            'id': p.id,
            'amount': p.amount,
            'reference': p.payment_reference,
            'method': p.payment_method,
            'date': p.payment_date.isoformat() if p.payment_date else None,
            'has_income': p.income is not None
        } for p in invoice.payments],
        'incomes': [{
            'id': i.id,
            'amount': i.total_amount,
            'reference': i.reference_number,
            'description': i.description,
            'date': i.income_date.isoformat() if i.income_date else None
        } for i in invoice.invoice_incomes]
    }