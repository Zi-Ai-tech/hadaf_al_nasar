from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from sqlalchemy import func, extract

financial_report_bp = Blueprint('financial_report', __name__)

def get_expense_model():
    """Lazy import for Expense model"""
    from app.models.wps.expense import Expense
    return Expense

def get_income_model():
    """Lazy import for Income model"""
    from app.models.wps.income import Income
    return Income

def get_salary_model():
    """Lazy import for Salary model"""
    from app.models.wps.salary import Salary
    return Salary

@financial_report_bp.route('/financial-report')
@login_required
def financial_report():
    """
    Financial report dashboard
    """
    Expense = get_expense_model()
    Income = get_income_model()
    Salary = get_salary_model()
    
    try:
        # Get filter parameters
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int, default=datetime.now().year)
        
        # Build query filters
        filters = []
        
        if year:
            filters.append(extract('year', Expense.expense_date) == year)
            filters.append(extract('year', Income.income_date) == year)
        
        if month:
            filters.append(extract('month', Expense.expense_date) == month)
            filters.append(extract('month', Income.income_date) == month)
        
        # Get expense summary by type
        expense_query = Expense.query
        income_query = Income.query
        
        if year:
            expense_query = expense_query.filter(extract('year', Expense.expense_date) == year)
            income_query = income_query.filter(extract('year', Income.income_date) == year)
        
        if month:
            expense_query = expense_query.filter(extract('month', Expense.expense_date) == month)
            income_query = income_query.filter(extract('month', Income.income_date) == month)
        
        # Get all expenses and incomes for the period
        all_expenses = expense_query.order_by(Expense.expense_date.desc()).limit(50).all()
        all_incomes = income_query.order_by(Income.income_date.desc()).limit(50).all()
        
        # Calculate totals by expense type
        expense_totals = {}
        expense_by_type = expense_query.with_entities(
            Expense.expense_type,
            func.sum(Expense.total_amount).label('total')
        ).group_by(Expense.expense_type).all()
        
        for expense_type, total in expense_by_type:
            if expense_type and total:
                expense_totals[expense_type.value] = float(total)
        
        # Calculate totals by income type
        income_totals = {}
        income_by_type = income_query.with_entities(
            Income.income_type,
            func.sum(Income.total_amount).label('total')
        ).group_by(Income.income_type).all()
        
        for income_type, total in income_by_type:
            if income_type and total:
                income_totals[income_type.value] = float(total)
        
        # Calculate overall totals
        total_expenses = sum(expense_totals.values())
        total_income = sum(income_totals.values())
        profit = total_income - total_expenses
        
        # Get salary report for the period
        salary_query = Salary.query
        
        if year:
            salary_query = salary_query.filter(extract('year', Salary.payment_date) == year)
        
        if month:
            salary_query = salary_query.filter(extract('month', Salary.payment_date) == month)
        
        salary_data = salary_query.all()
        salary_totals = {
            'count': len(salary_data),
            'net_salary': sum(s.net_salary for s in salary_data if s.net_salary),
            'gross_salary': sum(s.gross_salary for s in salary_data if s.gross_salary),
            'deductions': sum(s.total_deductions for s in salary_data if s.total_deductions)
        }
        
        # Build report object
        report = {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'profit': profit,
            'expense_totals': expense_totals,
            'income_totals': income_totals,
            'all_expenses': all_expenses,
            'all_incomes': all_incomes,
            'salary_report': {
                'totals': salary_totals,
                'data': salary_data[:10]  # Limit to 10 entries for display
            },
            'period': {
                'month': month,
                'year': year,
                'month_name': datetime(year, month, 1).strftime('%B') if month else None
            }
        }
        
        # Get expense and income types for display
        from app.constants import ExpenseType, IncomeType
        
        expense_types = {e.value: e.value.replace('_', ' ').title() for e in ExpenseType}
        income_types = {i.value: i.value.replace('_', ' ').title() for i in IncomeType}
        
        return render_template('employee/financial_report.html',
                             report=report,
                             now=datetime.now(),
                             expense_types=expense_types,
                             income_types=income_types,
                             current_year=datetime.now().year,
                             date=date)  # ADDED: Pass date class to template
                             
    except Exception as e:
        # Return empty report structure on error
        report = {
            'total_income': 0,
            'total_expenses': 0,
            'profit': 0,
            'expense_totals': {},
            'income_totals': {},
            'all_expenses': [],
            'all_incomes': [],
            'salary_report': {
                'totals': {'count': 0, 'net_salary': 0, 'gross_salary': 0, 'deductions': 0},
                'data': []
            },
            'period': {'month': month, 'year': year, 'month_name': None}
        }
        
        return render_template('employee/financial_report.html',
                             report=report,
                             now=datetime.now(),
                             current_year=datetime.now().year,
                             error=str(e),
                             date=date)  # ADDED: Pass date class to template in error case too

@financial_report_bp.route('/api/financial-summary')
@login_required
def financial_summary_api():
    """
    API endpoint for financial summary (for dashboards)
    """
    Expense = get_expense_model()
    Income = get_income_model()
    
    try:
        # Get current month data
        now = datetime.now()
        year = request.args.get('year', now.year, type=int)
        month = request.args.get('month', now.month, type=int)
        
        # Calculate date range
        from datetime import date
        start_date = date(year, month, 1)
        
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        # Get totals
        expenses = Expense.query.filter(
            Expense.expense_date >= start_date,
            Expense.expense_date < end_date
        ).all()
        
        incomes = Income.query.filter(
            Income.income_date >= start_date,
            Income.income_date < end_date
        ).all()
        
        total_expenses = sum(e.total_amount for e in expenses)
        total_income = sum(i.total_amount for i in incomes)
        
        # Calculate by category
        expense_by_type = {}
        for expense in expenses:
            exp_type = expense.expense_type.value
            expense_by_type[exp_type] = expense_by_type.get(exp_type, 0) + expense.total_amount
        
        income_by_type = {}
        for income in incomes:
            inc_type = income.income_type.value
            income_by_type[inc_type] = income_by_type.get(inc_type, 0) + income.total_amount
        
        return jsonify({
            'success': True,
            'summary': {
                'total_income': total_income,
                'total_expenses': total_expenses,
                'profit': total_income - total_expenses,
                'profit_margin': ((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0
            },
            'expense_breakdown': expense_by_type,
            'income_breakdown': income_by_type,
            'period': {
                'year': year,
                'month': month,
                'month_name': start_date.strftime('%B')
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500