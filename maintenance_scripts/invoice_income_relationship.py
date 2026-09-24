# Example migration script
from app import db
from app.models.finance.invoice import Invoice
from app.models.wps.income import Income

def migrate_invoice_income_relationship():
    # This would typically be an Alembic migration
    # For now, we can run this as a one-time script
    
    # Find all invoices with payments but no income records
    invoices = Invoice.query.filter(
        Invoice.amount_paid > 0,
        ~Invoice.incomes.any()  # Invoices without income records
    ).all()

    for invoice in invoices:
        invoice.sync_income_from_payments()

    print(f"Fixed {len(invoices)} invoices")
