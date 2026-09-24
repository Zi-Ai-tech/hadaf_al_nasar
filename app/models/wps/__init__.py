"""
WPS (Workforce and Payroll System) models package for the application.

This package contains all WPS models including employees, salaries, expenses, incomes,
and payroll management functionality with UAE WPS compliance.
"""

from app.models.logistics.vehicle import Vehicle  # <- important
from app.models.wps.employee_leave import EmployeeLeave
from app.models.wps.employee import Employee
from app.models.wps.salary import Salary, SalaryNotification
from app.models.wps.expense import Expense
from app.models.wps.income import Income, Service
from app.models.wps.project import Project

# Import constants for easy access
from app.constants import SalaryStatus, ExpenseType, IncomeType

# List of all WPS models for easy importing
__all__ = [
    # Employee models
    'Employee',
    'EmployeeLeave',
    
    # Salary models
    'Salary',
    'SalaryNotification',
    
    # Expense models
    'Expense',

    # Project models
    'Project',
    
    # Income models
    'Income',
    'Service',
    
    # Constants
    'SalaryStatus',
    'ExpenseType',
    'IncomeType'
]

# Version information
__version__ = '1.0.0'
__author__ = 'Hadaf Al Nasar Team'

# Package description
__description__ = 'Workforce and Payroll System data models for the Hadaf Al Nasar application'

def get_wps_models():
    """
    Return a dictionary of all WPS models for registration or inspection.
    
    Returns:
        dict: Mapping of model class names to model classes
    """
    return {
        'Employee': Employee,
        'Salary': Salary,
        'SalaryNotification': SalaryNotification,
        'Expense': Expense,
        'Project': Project,
        'Income': Income,
        'Service': Service,
    }

def init_wps_models():
    """
    Initialize WPS models with any required setup.
    This can be called during application startup.
    
    Returns:
        bool: True if initialization was successful
    """
    try:
        # Import db to ensure models are registered with SQLAlchemy
        from app import db
        
        # Any WPS model initialization logic would go here
        # For example, creating default salary structures, expense categories, etc.
        
        print("WPS models initialized successfully")
        return True
        
    except Exception as e:
        print(f"Error initializing WPS models: {str(e)}")
        return False

def get_payroll_summary(month, year, department=None):
    """
    Get comprehensive payroll summary for a specific month and year.
    
    Args:
        month (int): Month (1-12)
        year (int): Year
        department (str): Optional department filter
        
    Returns:
        dict: Payroll summary including totals, averages, and breakdowns
    """
    try:
        from app.models.wps.salary import Salary
        from app.models.wps.employee import Employee
        
        # Get salaries for the period
        query = Salary.query.filter_by(month=month, year=year)
        
        if department:
            query = query.join(Employee).filter(Employee.department == department)
        
        salaries = query.all()
        
        if not salaries:
            return {
                'period': f"{month}/{year}",
                'department': department or 'All',
                'total_employees': 0,
                'total_salaries': 0,
                'message': 'No payroll data found for this period'
            }
        
        # Calculate totals
        total_gross = sum(s.gross_salary for s in salaries)
        total_deductions = sum(s.total_deductions for s in salaries)
        total_net = sum(s.net_salary for s in salaries)
        total_overtime = sum(s.overtime_amount for s in salaries)
        total_bonuses = sum(s.incentives_amount for s in salaries)
        
        # Status breakdown
        paid_count = len([s for s in salaries if s.is_paid])
        pending_count = len([s for s in salaries if s.is_pending])
        processed_count = len([s for s in salaries if s.is_processed])
        
        # Department breakdown (if no specific department filter)
        department_breakdown = {}
        if not department:
            for salary in salaries:
                dept = salary.employee.department
                if dept not in department_breakdown:
                    department_breakdown[dept] = {
                        'count': 0,
                        'total_net': 0,
                        'average_salary': 0
                    }
                department_breakdown[dept]['count'] += 1
                department_breakdown[dept]['total_net'] += salary.net_salary
            
            # Calculate averages
            for dept in department_breakdown:
                department_breakdown[dept]['average_salary'] = (
                    department_breakdown[dept]['total_net'] / department_breakdown[dept]['count']
                )
        
        return {
            'period': {
                'month': month,
                'year': year,
                'name': f"{month}/{year}"
            },
            'department': department or 'All',
            'totals': {
                'gross_salary': total_gross,
                'deductions': total_deductions,
                'net_salary': total_net,
                'overtime': total_overtime,
                'bonuses': total_bonuses
            },
            'statistics': {
                'total_employees': len(salaries),
                'paid_employees': paid_count,
                'pending_employees': pending_count,
                'processed_employees': processed_count,
                'payment_rate': (paid_count / len(salaries)) * 100,
                'average_salary': total_net / len(salaries),
                'average_overtime': total_overtime / len(salaries),
                'average_bonus': total_bonuses / len(salaries)
            },
            'breakdown': {
                'department': department_breakdown,
                'status': {
                    'paid': paid_count,
                    'pending': pending_count,
                    'processed': processed_count
                }
            }
        }
        
    except Exception as e:
        print(f"Error generating payroll summary: {str(e)}")
        return {}

def get_financial_summary(start_date, end_date):
    """
    Get WPS financial summary including incomes, expenses, and net profit.
    
    Args:
        start_date (date): Start date
        end_date (date): End date
        
    Returns:
        dict: Financial summary
    """
    try:
        from app.models.wps.income import Income
        from app.models.wps.expense import Expense
        
        # Get incomes and expenses for the period
        incomes = Income.query.filter(
            Income.income_date >= start_date,
            Income.income_date <= end_date,
            Income.status == 'received'
        ).all()
        
        expenses = Expense.query.filter(
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date,
            Expense.status == 'paid'
        ).all()
        
        # Calculate totals
        total_income = sum(income.total_amount_in_default_currency for income in incomes)
        total_expense = sum(expense.total_amount_in_default_currency for expense in expenses)
        net_profit = total_income - total_expense
        
        # Income breakdown by type
        income_by_type = {}
        for income in incomes:
            income_type = income.income_type.value
            if income_type not in income_by_type:
                income_by_type[income_type] = {
                    'count': 0,
                    'amount': 0,
                    'percentage': 0
                }
            income_by_type[income_type]['count'] += 1
            income_by_type[income_type]['amount'] += income.total_amount_in_default_currency
        
        # Expense breakdown by type
        expense_by_type = {}
        for expense in expenses:
            expense_type = expense.expense_type.value
            if expense_type not in expense_by_type:
                expense_by_type[expense_type] = {
                    'count': 0,
                    'amount': 0,
                    'percentage': 0
                }
            expense_by_type[expense_type]['count'] += 1
            expense_by_type[expense_type]['amount'] += expense.total_amount_in_default_currency
        
        # Calculate percentages
        for income_type in income_by_type:
            income_by_type[income_type]['percentage'] = (
                income_by_type[income_type]['amount'] / total_income * 100
            ) if total_income > 0 else 0
        
        for expense_type in expense_by_type:
            expense_by_type[expense_type]['percentage'] = (
                expense_by_type[expense_type]['amount'] / total_expense * 100
            ) if total_expense > 0 else 0
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_income': total_income,
                'total_expense': total_expense,
                'net_profit': net_profit,
                'profit_margin': (net_profit / total_income * 100) if total_income > 0 else 0
            },
            'breakdown': {
                'income': income_by_type,
                'expense': expense_by_type
            },
            'transactions': {
                'income_count': len(incomes),
                'expense_count': len(expenses),
                'total_transactions': len(incomes) + len(expenses)
            }
        }
        
    except Exception as e:
        print(f"Error generating financial summary: {str(e)}")
        return {}

def get_employee_statistics():
    """
    Get comprehensive employee statistics.
    
    Returns:
        dict: Employee statistics and analytics
    """
    try:
        from app.models.wps.employee import Employee
        
        active_employees = Employee.get_active_employees()
        total_employees = len(active_employees)
        
        if total_employees == 0:
            return {
                'total_employees': 0,
                'message': 'No active employees found'
            }
        
        # Department breakdown
        department_stats = {}
        for employee in active_employees:
            dept = employee.department
            if dept not in department_stats:
                department_stats[dept] = {
                    'count': 0,
                    'total_salary': 0,
                    'average_salary': 0,
                    'positions': set()
                }
            department_stats[dept]['count'] += 1
            department_stats[dept]['total_salary'] += employee.total_salary
            department_stats[dept]['positions'].add(employee.position)
        
        # Calculate averages and convert sets to lists
        for dept in department_stats:
            department_stats[dept]['average_salary'] = (
                department_stats[dept]['total_salary'] / department_stats[dept]['count']
            )
            department_stats[dept]['positions'] = list(department_stats[dept]['positions'])
        
        # Position breakdown
        position_stats = {}
        for employee in active_employees:
            position = employee.position
            if position not in position_stats:
                position_stats[position] = {
                    'count': 0,
                    'total_salary': 0,
                    'average_salary': 0
                }
            position_stats[position]['count'] += 1
            position_stats[position]['total_salary'] += employee.total_salary
        
        for position in position_stats:
            position_stats[position]['average_salary'] = (
                position_stats[position]['total_salary'] / position_stats[position]['count']
            )
        
        # Employment type breakdown
        employment_type_stats = {}
        for employee in active_employees:
            emp_type = employee.employment_type
            if emp_type not in employment_type_stats:
                employment_type_stats[emp_type] = 0
            employment_type_stats[emp_type] += 1
        
        # Experience analysis
        experience_groups = {
            '0-1 years': 0,
            '1-3 years': 0,
            '3-5 years': 0,
            '5-10 years': 0,
            '10+ years': 0
        }
        
        for employee in active_employees:
            experience = employee.experience_years or 0
            if experience <= 1:
                experience_groups['0-1 years'] += 1
            elif experience <= 3:
                experience_groups['1-3 years'] += 1
            elif experience <= 5:
                experience_groups['3-5 years'] += 1
            elif experience <= 10:
                experience_groups['5-10 years'] += 1
            else:
                experience_groups['10+ years'] += 1
        
        return {
            'total_employees': total_employees,
            'department_breakdown': department_stats,
            'position_breakdown': position_stats,
            'employment_type_breakdown': employment_type_stats,
            'experience_breakdown': experience_groups,
            'salary_analysis': {
                'total_payroll': sum(employee.total_salary for employee in active_employees),
                'average_salary': sum(employee.total_salary for employee in active_employees) / total_employees,
                'highest_salary': max(employee.total_salary for employee in active_employees),
                'lowest_salary': min(employee.total_salary for employee in active_employees)
            }
        }
        
    except Exception as e:
        print(f"Error generating employee statistics: {str(e)}")
        return {}

def get_wps_compliance_report(month, year):
    """
    Generate WPS (Wage Protection System) compliance report.
    
    Args:
        month (int): Month (1-12)
        year (int): Year
        
    Returns:
        dict: WPS compliance report
    """
    try:
        from app.models.wps.salary import Salary
        
        salaries = Salary.get_by_period(month, year)
        
        if not salaries:
            return {
                'period': f"{month}/{year}",
                'compliance_status': 'NO_DATA',
                'message': 'No salary data found for this period'
            }
        
        total_salaries = len(salaries)
        wps_submitted = len([s for s in salaries if s.wps_status == 'submitted'])
        wps_processed = len([s for s in salaries if s.wps_status == 'processed'])
        paid_salaries = len([s for s in salaries if s.is_paid])
        
        # Check compliance criteria
        compliance_criteria = {
            'all_salaries_paid': paid_salaries == total_salaries,
            'wps_submission_rate': (wps_submitted / total_salaries) * 100 >= 95,  # 95% threshold
            'wps_processing_rate': (wps_processed / total_salaries) * 100 >= 90,  # 90% threshold
            'timely_payment': all(
                s.payment_date and s.payment_date.day <= 15  # Paid by 15th of next month
                for s in salaries if s.is_paid
            ) if paid_salaries > 0 else False
        }
        
        compliance_status = 'COMPLIANT' if all(compliance_criteria.values()) else 'NON_COMPLIANT'
        
        return {
            'period': f"{month}/{year}",
            'compliance_status': compliance_status,
            'summary': {
                'total_salaries': total_salaries,
                'paid_salaries': paid_salaries,
                'wps_submitted': wps_submitted,
                'wps_processed': wps_processed,
                'payment_rate': (paid_salaries / total_salaries) * 100,
                'wps_submission_rate': (wps_submitted / total_salaries) * 100,
                'wps_processing_rate': (wps_processed / total_salaries) * 100
            },
            'compliance_criteria': compliance_criteria,
            'non_compliant_salaries': [
                {
                    'salary_number': s.salary_number,
                    'employee_name': s.employee.name,
                    'issues': [
                        'Not paid' if not s.is_paid else None,
                        'WPS not submitted' if s.wps_status != 'submitted' else None,
                        'WPS not processed' if s.wps_status != 'processed' else None,
                        'Late payment' if s.payment_date and s.payment_date.day > 15 else None
                    ]
                }
                for s in salaries 
                if not s.is_paid or s.wps_status != 'processed' or (s.payment_date and s.payment_date.day > 15)
            ]
        }
        
    except Exception as e:
        print(f"Error generating WPS compliance report: {str(e)}")
        return {}

def generate_wps_salary_file(month, year):
    """
    Generate WPS salary file data for submission to UAE WPS system.
    
    Args:
        month (int): Month (1-12)
        year (int): Year
        
    Returns:
        dict: WPS file data and metadata
    """
    try:
        from app.models.wps.salary import Salary
        
        salaries = Salary.query.filter_by(month=month, year=year, status='paid').all()
        
        if not salaries:
            return {
                'error': 'No paid salaries found for the specified period',
                'period': f"{month}/{year}"
            }
        
        wps_data = []
        total_amount = 0
        
        for salary in salaries:
            salary_data = salary.prepare_wps_data()
            wps_data.append(salary_data)
            total_amount += salary.net_salary
        
        # Generate WPS file header
        file_header = {
            'company_name': 'Hadaf Al Nasar Transport',
            'company_trn': 'YOUR_COMPANY_TRN',  # Should be configured
            'period': f"{month:02d}/{year}",
            'submission_date': datetime.now().strftime('%Y-%m-%d'),
            'total_employees': len(salaries),
            'total_amount': total_amount,
            'currency': 'AED'
        }
        
        return {
            'file_header': file_header,
            'salary_data': wps_data,
            'metadata': {
                'total_records': len(wps_data),
                'total_amount': total_amount,
                'generated_at': datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        print(f"Error generating WPS salary file: {str(e)}")
        return {'error': str(e)}

# Import datetime for the functions above
from datetime import datetime

# Auto-initialize when package is imported
try:
    init_wps_models()
except Exception as e:
    # Silently fail during import to avoid circular imports
    pass