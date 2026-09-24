"""
Finance models package for the application.

This package contains all financial models including invoices, payments, transactions,
and financial reporting functionality.
"""

from app.models.finance.invoice import Invoice, InvoiceItem
from app.models.finance.payment import Payment, Refund
from app.models.finance.transaction import Transaction, TransactionType, TransactionStatus, Supplier

# Import constants for easy access
from app.constants import ExpenseType, IncomeType

# List of all finance models for easy importing
__all__ = [
    # Invoice models
    'Invoice',
    'InvoiceItem',
    
    # Payment models
    'Payment', 
    'Refund',
    
    # Transaction models
    'Transaction',
    'TransactionType',
    'TransactionStatus',
    'Supplier',
    
    # Constants
    'ExpenseType',
    'IncomeType'
]

# Version information
__version__ = '1.0.0'
__author__ = 'Hadaf Al Nasar Team'

# Package description
__description__ = 'Financial data models and business entities for the Hadaf Al Nasar application'

def get_finance_models():
    """
    Return a dictionary of all finance models for registration or inspection.
    
    Returns:
        dict: Mapping of model class names to model classes
    """
    return {
        'Invoice': Invoice,
        'InvoiceItem': InvoiceItem,
        'Payment': Payment,
        'Refund': Refund,
        'Transaction': Transaction,
        'Supplier': Supplier,
    }

def init_finance_models():
    """
    Initialize finance models with any required setup.
    This can be called during application startup.
    
    Returns:
        bool: True if initialization was successful
    """
    try:
        # Import db to ensure models are registered with SQLAlchemy
        from app import db
        
        # Any finance model initialization logic would go here
        # For example, creating default payment methods, categories, etc.
        
        print("Finance models initialized successfully")
        return True
        
    except Exception as e:
        print(f"Error initializing finance models: {str(e)}")
        return False

def get_financial_summary(start_date, end_date):
    """
    Get comprehensive financial summary for a date range.
    
    Args:
        start_date (datetime): Start date for the period
        end_date (datetime): End date for the period
        
    Returns:
        dict: Financial summary including income, expenses, cash flow, etc.
    """
    try:
        from app.models.finance.transaction import Transaction
        
        # Get all completed transactions in the date range
        transactions = Transaction.query.filter(
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
            Transaction.status == TransactionStatus.COMPLETED.value
        ).all()
        
        # Calculate totals by type
        income_total = 0
        expense_total = 0
        salary_total = 0
        
        for transaction in transactions:
            if transaction.is_income:
                income_total += transaction.net_amount
            elif transaction.is_expense:
                expense_total += transaction.net_amount
            elif transaction.is_salary:
                salary_total += transaction.net_amount
        
        # Calculate net profit
        net_profit = income_total - expense_total - salary_total
        
        # Get payment summary
        from app.models.finance.payment import Payment
        payment_summary = Payment.get_payment_summary(start_date, end_date)
        
        # Get invoice summary
        from app.models.finance.invoice import Invoice
        overdue_invoices = Invoice.get_overdue_invoices()
        total_outstanding = Invoice.get_total_outstanding()
        
        summary = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'income': {
                'total': income_total,
                'count': len([t for t in transactions if t.is_income])
            },
            'expenses': {
                'total': expense_total,
                'count': len([t for t in transactions if t.is_expense])
            },
            'salaries': {
                'total': salary_total,
                'count': len([t for t in transactions if t.is_salary])
            },
            'net_profit': net_profit,
            'profit_margin': (net_profit / income_total * 100) if income_total > 0 else 0,
            'payments': payment_summary,
            'invoices': {
                'overdue_count': len(overdue_invoices),
                'overdue_amount': sum(inv.balance_due for inv in overdue_invoices),
                'total_outstanding': total_outstanding
            },
            'cash_flow': Transaction.get_cash_flow(start_date, end_date, 'monthly')
        }
        
        return summary
        
    except Exception as e:
        print(f"Error generating financial summary: {str(e)}")
        return {}

def get_accounts_receivable():
    """
    Get accounts receivable summary.
    
    Returns:
        dict: Accounts receivable information
    """
    try:
        from app.models.finance.invoice import Invoice
        
        overdue = Invoice.get_overdue_invoices()
        sent_invoices = Invoice.get_invoices_by_status('sent')
        partial_invoices = Invoice.get_invoices_by_status('partial')
        
        total_receivable = sum(inv.balance_due for inv in sent_invoices + partial_invoices + overdue)
        
        return {
            'total_receivable': total_receivable,
            'overdue_invoices': [inv.to_dict(include_items=False) for inv in overdue],
            'sent_invoices_count': len(sent_invoices),
            'partial_invoices_count': len(partial_invoices),
            'overdue_invoices_count': len(overdue),
            'aging_summary': {
                'current': sum(inv.balance_due for inv in sent_invoices),
                '1-30_days': sum(inv.balance_due for inv in overdue if inv.days_overdue <= 30),
                '31-60_days': sum(inv.balance_due for inv in overdue if 31 <= inv.days_overdue <= 60),
                '61-90_days': sum(inv.balance_due for inv in overdue if 61 <= inv.days_overdue <= 90),
                'over_90_days': sum(inv.balance_due for inv in overdue if inv.days_overdue > 90)
            }
        }
        
    except Exception as e:
        print(f"Error getting accounts receivable: {str(e)}")
        return {}

def get_accounts_payable():
    """
    Get accounts payable summary (to suppliers).
    
    Returns:
        dict: Accounts payable information
    """
    try:
        from app.models.finance.transaction import Transaction, Supplier
        
        # Get expense transactions that are pending or due
        payable_transactions = Transaction.query.filter(
            Transaction.transaction_type == TransactionType.EXPENSE.value,
            Transaction.status.in_(['pending', 'completed']),
            Transaction.due_date.isnot(None)
        ).all()
        
        total_payable = sum(txn.net_amount for txn in payable_transactions if txn.due_date and txn.due_date > datetime.utcnow())
        overdue_payable = sum(txn.net_amount for txn in payable_transactions if txn.due_date and txn.due_date <= datetime.utcnow())
        
        # Group by supplier
        suppliers_summary = {}
        for txn in payable_transactions:
            if txn.supplier:
                supplier_name = txn.supplier.name
                if supplier_name not in suppliers_summary:
                    suppliers_summary[supplier_name] = {
                        'total_amount': 0,
                        'transactions': []
                    }
                suppliers_summary[supplier_name]['total_amount'] += txn.net_amount
                suppliers_summary[supplier_name]['transactions'].append(txn.to_dict())
        
        return {
            'total_payable': total_payable,
            'overdue_payable': overdue_payable,
            'suppliers_summary': suppliers_summary,
            'transactions_count': len(payable_transactions)
        }
        
    except Exception as e:
        print(f"Error getting accounts payable: {str(e)}")
        return {}

# Import datetime for the functions above
from datetime import datetime

# Auto-initialize when package is imported
try:
    init_finance_models()
except Exception as e:
    # Silently fail during import to avoid circular imports
    pass