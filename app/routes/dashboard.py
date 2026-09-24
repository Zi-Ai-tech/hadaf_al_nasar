from flask import Blueprint, render_template, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, text
import traceback
from datetime import datetime

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Main accounts dashboard with financial and logistics overview
    """
    from app import db
    
    try:
        print("Loading dashboard data...")
        print(f"Current user: {current_user.username} (ID: {current_user.id})")
        
        from app.models.finance.invoice import Invoice

        Invoice.sync_overdue_statuses()

        # Use raw SQL to avoid ORM issues temporarily
        total_invoices = db.session.execute(text("SELECT COUNT(*) FROM invoice")).scalar() or 0
        pending_invoices = Invoice.query.filter(
            Invoice.status.in_(Invoice.OUTSTANDING_STATUSES)
        ).count()
        paid_invoices = db.session.execute(text("SELECT COUNT(*) FROM invoice WHERE status = 'paid'")).scalar() or 0
        active_customers_count = db.session.execute(text("SELECT COUNT(*) FROM customer WHERE is_active = true")).scalar() or 0
        
        outstanding_balance = float(Invoice.get_total_outstanding())

        # Financial totals used by the clickable dashboard cards.
        from app.models.wps.expense import Expense
        total_income_received = db.session.query(
            func.coalesce(func.sum(Invoice.amount_paid), 0)
        ).scalar() or 0
        total_expenses = db.session.query(
            func.coalesce(
                func.sum(Expense.total_amount * func.coalesce(Expense.exchange_rate, 1)),
                0,
            )
        ).scalar() or 0

        # Get financial summary - simplified for now
        financial_summary = {
            'total_revenue': 0,
            'total_expenses': 0,
            'net_profit': 0
        }

        # Get logistics data - simplified for now
        logistics_data = {
            'total_shipments': 0,
            'pending_shipments': 0,
            'delivered_shipments': 0
        }

        print(f"Dashboard data loaded: {total_invoices} invoices, {active_customers_count} customers")
        
        return render_template(
            'accounts/dashboard.html',
            total_invoices=total_invoices,
            pending_invoices=pending_invoices,
            paid_invoices=paid_invoices,
            active_customers_count=active_customers_count,
            outstanding_balance=outstanding_balance,
            total_income_received=float(total_income_received),
            total_expenses=float(total_expenses),
            financial_summary=financial_summary,
            logistics_data=logistics_data,
            now=datetime.now()
        )
        
    except Exception as e:
        print(f"[Dashboard Error] {e}")
        traceback.print_exc()
        
        # Return a simple error response
        return render_template(
            'accounts/dashboard.html',
            total_invoices=0,
            pending_invoices=0,
            paid_invoices=0,
            active_customers_count=0,
            outstanding_balance=0,
            total_income_received=0,
            total_expenses=0,
            financial_summary={},
            logistics_data={},
            error=str(e),
            now=datetime.now()
        )


@dashboard_bp.route('/dashboard/income')
@login_required
def income_details():
    """Show total amounts received from each customer."""
    from app import db
    from app.models.core.customer import Customer
    from app.models.finance.invoice import Invoice

    customer_totals = db.session.query(
        Customer.company_name,
        func.sum(Invoice.amount_paid).label('total_paid'),
        func.count(Invoice.id).label('invoice_count'),
    ).join(Invoice, Invoice.customer_id == Customer.id).filter(
        Invoice.amount_paid > 0
    ).group_by(Customer.id, Customer.company_name).order_by(
        func.sum(Invoice.amount_paid).desc()
    ).all()

    total_received = sum(float(row.total_paid or 0) for row in customer_totals)
    return render_template(
        'accounts/dashboard_income.html',
        customer_totals=customer_totals,
        total_received=total_received,
        now=datetime.now(),
    )


@dashboard_bp.route('/dashboard/expenses')
@login_required
def expense_details():
    """Show all recorded expenses and their details."""
    from app import db
    from app.models.wps.expense import Expense

    expenses = Expense.query.order_by(Expense.expense_date.desc(), Expense.created_at.desc()).all()
    total_expenses = sum(
        float((expense.total_amount or 0) * (expense.exchange_rate or 1))
        for expense in expenses
    )
    return render_template(
        'accounts/dashboard_expenses.html',
        expenses=expenses,
        total_expenses=total_expenses,
        now=datetime.now(),
    )
