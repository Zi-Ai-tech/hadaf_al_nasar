from app import db
from app.models.wps.employee import Employee
from app.models.wps.salary import Salary, SalaryStatus
from app.models.wps.expense import Expense
from app.models.wps.income import Income
from app.models.logistics.vehicle import Vehicle
from app.models.core.customer import Customer
from app.exceptions import ValidationError, DatabaseError
from datetime import datetime, date
from sqlalchemy import func, extract
import json

class WPSService:
    @staticmethod
    def get_all_employees(active_only=True):
        """Get all employees, optionally filtered by active status"""
        try:
            query = Employee.query
            if active_only:
                query = query.filter(Employee.employment_status == 'active', Employee.deleted_at.is_(None))
            return query.all()
        except Exception as e:
            raise DatabaseError(f"Error retrieving employees: {str(e)}")

    @staticmethod
    def create_employee(data):
        """Create a new employee"""
        try:
            employee = Employee(**data)
            db.session.add(employee)
            db.session.commit()
            return employee
        except Exception as e:
            db.session.rollback()
            raise DatabaseError(f"Error creating employee: {str(e)}")

    @staticmethod
    def update_employee(employee_id, data):
        """Update employee details"""
        try:
            employee = Employee.query.get_or_404(employee_id)
            for key, value in data.items():
                if hasattr(employee, key):
                    setattr(employee, key, value)
            
            employee.updated_at = datetime.utcnow()
            db.session.commit()
            return employee
        except Exception as e:
            db.session.rollback()
            raise DatabaseError(f"Error updating employee: {str(e)}")

    @staticmethod
    def process_salary(employee_id, month, year, data):
        """Process salary for an employee for a specific month"""
        try:
            # Check if employee exists
            employee = Employee.query.get(employee_id)
            if not employee:
                raise ValidationError(f"Employee with ID {employee_id} not found")
        
            # Check if salary already processed for this month
            existing_salary = Salary.query.filter_by(
                employee_id=employee_id, 
                month=month, 
                year=year
            ).first()
        
            if existing_salary:
                raise ValidationError(f"Salary already processed for {month}/{year}")
        
            # Use employee defaults if not provided
            basic_salary = data.get('basic_salary') or employee.basic_salary
            housing_allowance = data.get('housing_allowance') or employee.housing_allowance or 0
            transportation_allowance = data.get('transportation_allowance') or employee.transportation_allowance or 0
            other_allowances = data.get('other_allowances') or employee.other_allowances or 0
            overtime_hours = data.get('overtime_hours', 0)
            overtime_rate = data.get('overtime_rate', employee.overtime_rate)
            
            # Get all deduction components
            deductions_amount = data.get('deductions_amount', 0)
            tax_amount = data.get('tax_amount', 0)
            social_security_amount = data.get('social_security_amount', 0)
            other_deductions = data.get('other_deductions', 0)
            incentives_amount = data.get('incentives_amount', 0)
            
            # Handle bonuses and deductions data
            bonuses_data = data.get('bonuses_data', [])
            deductions_data = data.get('deductions_data', [])
            
            # Calculate incentives from bonuses_data if provided
            if incentives_amount == 0 and bonuses_data:
                if isinstance(bonuses_data, str):
                    try:
                        bonuses_data = json.loads(bonuses_data)
                    except json.JSONDecodeError:
                        bonuses_data = []
                incentives_amount = sum(bonus.get('amount', 0) for bonus in bonuses_data)
            
            # Calculate deductions_amount from deductions_data if provided
            if deductions_amount == 0 and deductions_data:
                if isinstance(deductions_data, str):
                    try:
                        deductions_data = json.loads(deductions_data)
                    except json.JSONDecodeError:
                        deductions_data = []
                deductions_amount = sum(deduction.get('amount', 0) for deduction in deductions_data)

            # Handle status - convert string to SalaryStatus enum
            status_str = data.get('status', 'PENDING').upper()
            if status_str == 'PENDING':
                status = SalaryStatus.PENDING
            elif status_str == 'PAID':
                status = SalaryStatus.PAID
            elif status_str == 'PROCESSING':
                status = SalaryStatus.PROCESSING
            elif status_str == 'CANCELLED':
                status = SalaryStatus.CANCELLED
            else:
                status = SalaryStatus.PENDING
            
            # Prepare salary data - let the Salary model handle calculations
            salary_data = {
                'employee_id': employee_id,
                'month': month,
                'year': year,
                'basic_salary': basic_salary,
                'housing_allowance': housing_allowance,
                'transportation_allowance': transportation_allowance,
                'other_allowances': other_allowances,
                'overtime_hours': overtime_hours,
                'overtime_rate': overtime_rate,
                'deductions_amount': deductions_amount,
                'tax_amount': tax_amount,
                'social_security_amount': social_security_amount,
                'other_deductions': other_deductions,
                'incentives_amount': incentives_amount,
                'status': status
            }
            
            # Handle payment date
            if data.get('payment_date'):
                try:
                    salary_data['payment_date'] = datetime.strptime(data['payment_date'], '%Y-%m-%d')
                except ValueError:
                    raise ValidationError("Invalid payment date format. Use YYYY-MM-DD.")
            
            # Handle JSON data for bonuses and deductions
            if bonuses_data:
                if not isinstance(bonuses_data, str):
                    bonuses_data = json.dumps(bonuses_data)
                salary_data['bonuses_data'] = bonuses_data
                
            if deductions_data:
                if not isinstance(deductions_data, str):
                    deductions_data = json.dumps(deductions_data)
                salary_data['deductions_data'] = deductions_data
            
            # Handle attendance and working days
            if 'working_days' in data:
                salary_data['working_days'] = data['working_days']
            if 'actual_worked_days' in data:
                salary_data['actual_worked_days'] = data['actual_worked_days']
            if 'leave_days' in data:
                salary_data['leave_days'] = data['leave_days']
            if 'absent_days' in data:
                salary_data['absent_days'] = data['absent_days']
            
            # Create salary - let the model handle calculations
            salary = Salary(**salary_data)
            db.session.add(salary)
            db.session.commit()
            
            return salary
        
        except ValidationError:
            raise
        except Exception as e:
            db.session.rollback()
            import traceback
            print(f"Error processing salary: {str(e)}")
            print(traceback.format_exc())
            raise DatabaseError(f"Error processing salary: {str(e)}")

    @staticmethod
    def get_salary_report(month=None, year=None):
        """Get salary report for a specific period"""
        try:
            query = Salary.query
            
            # Apply filters
            if month and year:
                query = query.filter_by(month=month, year=year)
            elif year:
                query = query.filter_by(year=year)

            salaries = query.all()
            
            # Calculate totals using model's actual fields
            total_basic = sum(s.basic_salary for s in salaries)
            total_housing = sum(s.housing_allowance for s in salaries)
            total_transportation = sum(s.transportation_allowance for s in salaries)
            total_other_allowances = sum(s.other_allowances for s in salaries)
            total_allowances = total_housing + total_transportation + total_other_allowances
            total_overtime = sum(s.overtime_amount for s in salaries)
            total_incentives = sum(s.incentives_amount for s in salaries)
            total_gross = sum(s.gross_salary for s in salaries)
            
            total_deductions_amount = sum(s.deductions_amount for s in salaries)
            total_tax = sum(s.tax_amount for s in salaries)
            total_social_security = sum(s.social_security_amount for s in salaries)
            total_other_deductions = sum(s.other_deductions for s in salaries)
            total_deductions = sum(s.total_deductions for s in salaries)
            total_net = sum(s.net_salary for s in salaries)
            
            return {
                'salaries': salaries,
                'totals': {
                    'basic_salary': total_basic,
                    'housing_allowance': total_housing,
                    'transportation_allowance': total_transportation,
                    'other_allowances': total_other_allowances,
                    'total_allowances': total_allowances,
                    'overtime': total_overtime,
                    'incentives': total_incentives,
                    'gross_salary': total_gross,
                    'deductions_amount': total_deductions_amount,
                    'tax_amount': total_tax,
                    'social_security_amount': total_social_security,
                    'other_deductions': total_other_deductions,
                    'total_deductions': total_deductions,
                    'net_salary': total_net,
                    'count': len(salaries)
                }
            }
        except Exception as e:
            raise DatabaseError(f"Error generating salary report: {str(e)}")

    @staticmethod
    def record_expense(expense_data):
        """Record an expense"""
        try:
            expense = Expense(**expense_data)
            db.session.add(expense)
            db.session.commit()
            return expense
        except Exception as e:
            db.session.rollback()
            raise DatabaseError(f"Error recording expense: {str(e)}")

    @staticmethod
    def record_income(income_data):
        """Record income"""
        try:
            income = Income(**income_data)
            db.session.add(income)
            db.session.commit()
            return income
        except Exception as e:
            db.session.rollback()
            raise DatabaseError(f"Error recording income: {str(e)}")

    @staticmethod
    def get_vehicle_financial_report(vehicle_id, month=None, year=None):
        """Get financial report for a vehicle"""
        try:
            vehicle = Vehicle.query.get_or_404(vehicle_id)
            
            # Query expenses
            expense_query = Expense.query.filter_by(vehicle_id=vehicle_id)
            income_query = Income.query.filter_by(vehicle_id=vehicle_id)
            
            if month and year:
                expense_query = expense_query.filter(
                    extract('month', Expense.expense_date) == month,
                    extract('year', Expense.expense_date) == year
                )
                income_query = income_query.filter(
                    extract('month', Income.income_date) == month,
                    extract('year', Income.income_date) == year
                )
            elif year:
                expense_query = expense_query.filter(extract('year', Expense.expense_date) == year)
                income_query = income_query.filter(extract('year', Income.income_date) == year)
            
            expenses = expense_query.all()
            incomes = income_query.all()
            
            # Calculate totals by category
            expense_totals = {}
            for expense in expenses:
                if expense.expense_type.value not in expense_totals:
                    expense_totals[expense.expense_type.value] = 0
                expense_totals[expense.expense_type.value] += expense.amount
            
            income_totals = {}
            for income in incomes:
                if income.income_type.value not in income_totals:
                    income_totals[income.income_type.value] = 0
                income_totals[income.income_type.value] += income.amount
            
            total_expenses = sum(expense.amount for expense in expenses)
            total_income = sum(income.amount for income in incomes)
            profit = total_income - total_expenses
            
            return {
                'vehicle': vehicle,
                'expenses': expenses,
                'incomes': incomes,
                'expense_totals': expense_totals,
                'income_totals': income_totals,
                'total_expenses': total_expenses,
                'total_income': total_income,
                'profit': profit
            }
        except Exception as e:
            raise DatabaseError(f"Error generating vehicle report: {str(e)}")

    @staticmethod
    def get_overall_financial_report(month=None, year=None):
        """Get overall financial report including salaries and expenses"""
        try:
            # Get salary report
            salary_report = WPSService.get_salary_report(month, year)
            
            # Get all expenses (not just vehicle expenses)
            expense_query = Expense.query
            income_query = Income.query
            
            if month and year:
                expense_query = expense_query.filter(
                    extract('month', Expense.expense_date) == month,
                    extract('year', Expense.expense_date) == year
                )
                income_query = income_query.filter(
                    extract('month', Income.income_date) == month,
                    extract('year', Income.income_date) == year
                )
            elif year:
                expense_query = expense_query.filter(extract('year', Expense.expense_date) == year)
                income_query = income_query.filter(extract('year', Income.income_date) == year)
            
            all_expenses = expense_query.all()
            all_incomes = income_query.all()
            
            # Calculate expense totals by type
            expense_totals = {}
            for expense in all_expenses:
                if expense.expense_type.value not in expense_totals:
                    expense_totals[expense.expense_type.value] = 0
                expense_totals[expense.expense_type.value] += expense.amount
            
            # Calculate income totals by type
            income_totals = {}
            for income in all_incomes:
                if income.income_type.value not in income_totals:
                    income_totals[income.income_type.value] = 0
                income_totals[income.income_type.value] += income.amount
            
            total_expenses = sum(expense.amount for expense in all_expenses)
            total_income = sum(income.amount for income in all_incomes)
            
            # Add salary expenses to the totals
            total_expenses += salary_report['totals']['net_salary']
            if 'salary' not in expense_totals:
                expense_totals['salary'] = 0
            expense_totals['salary'] += salary_report['totals']['net_salary']
            
            profit = total_income - total_expenses
            
            return {
                'salary_report': salary_report,
                'expense_totals': expense_totals,
                'income_totals': income_totals,
                'total_expenses': total_expenses,
                'total_income': total_income,
                'profit': profit,
                'all_expenses': all_expenses,
                'all_incomes': all_incomes
            }
        except Exception as e:
            raise DatabaseError(f"Error generating overall financial report: {str(e)}")
        
    @staticmethod
    def update_salary(salary_id, data):
        """Update salary details"""
        try:
            print(f"DEBUG: Starting update for salary {salary_id}")
            salary = Salary.query.get_or_404(salary_id)
        
            # Update fields if provided
            if 'basic_salary' in data:
                salary.basic_salary = data['basic_salary']
            if 'housing_allowance' in data:
                salary.housing_allowance = data['housing_allowance']
            if 'transportation_allowance' in data:
                salary.transportation_allowance = data['transportation_allowance']
            if 'other_allowances' in data:
                salary.other_allowances = data['other_allowances']
            if 'overtime_hours' in data:
                salary.overtime_hours = data['overtime_hours']
            if 'overtime_rate' in data:
                salary.overtime_rate = data['overtime_rate']
            if 'deductions_amount' in data:
                salary.deductions_amount = float(data.get('deductions_amount', 0))
            if 'tax_amount' in data:
                salary.tax_amount = float(data.get('tax_amount', 0))
            if 'social_security_amount' in data:
                salary.social_security_amount = float(data.get('social_security_amount', 0))
            if 'other_deductions' in data:
                salary.other_deductions = float(data.get('other_deductions', 0))
            if 'incentives_amount' in data:
                salary.incentives_amount = float(data.get('incentives_amount', 0))

            # Convert status string to enum if provided
            if 'status' in data:
                status_str = data['status'].upper()
                if status_str == 'PENDING':
                    salary.status = SalaryStatus.PENDING
                elif status_str == 'PAID':
                    salary.status = SalaryStatus.PAID
                elif status_str == 'PROCESSING':
                    salary.status = SalaryStatus.PROCESSING
                elif status_str == 'CANCELLED':
                    salary.status = SalaryStatus.CANCELLED
                else:
                    raise ValidationError(f"Invalid status: {status_str}")
                print(f"Status updated to: {salary.status}")
        
            if 'payment_date' in data:
                if data['payment_date']:
                    try:
                        salary.payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d')
                        print(f"Payment date updated to: {salary.payment_date}")
                    except ValueError:
                        raise ValidationError("Invalid payment date format. Use YYYY-MM-DD.")
                else:
                    salary.payment_date = None

            # Use the model's recalculate_salary method instead of manual calculation
            salary.recalculate_salary()

            db.session.commit()
            print(f"Salary {salary_id} updated successfully")
            return salary
    
        except ValidationError:
            raise
        except Exception as e:
            db.session.rollback()
            import traceback
            print(f"Error updating salary: {str(e)}")
            print(traceback.format_exc())
            raise DatabaseError(f"Error updating salary: {str(e)}")
        
    @staticmethod
    def mark_salary_paid(salary_id):
        """Mark salary as paid with current date"""
        try:
            print(f"DEBUG: Marking salary {salary_id} as paid")
            salary = Salary.query.get_or_404(salary_id)
        
            # Update status and payment date
            salary.status = SalaryStatus.PAID
            salary.payment_date = datetime.utcnow().date()
        
            db.session.commit()
            print(f"Salary {salary_id} marked as paid successfully")
            return salary
        
        except Exception as e:
            db.session.rollback()
            raise DatabaseError(f"Error marking salary as paid: {str(e)}")

# CustomerService class (kept for compatibility)
class CustomerService:
    @staticmethod
    def get_customer_by_id(customer_id):
        """Get a customer by ID"""
        return Customer.query.get(customer_id)

    @staticmethod
    def update_customer(customer_id, customer_data):
        """Update a customer"""
        customer = Customer.query.get(customer_id)
        if not customer:
            return None
        
        # Update fields
        for key, value in customer_data.items():
            if hasattr(customer, key):
                setattr(customer, key, value)
        
        db.session.commit()
        return customer

    @staticmethod
    def delete_customer(customer_id):
        """Delete a customer"""
        customer = Customer.query.get(customer_id)
        if not customer:
            return False
        
        db.session.delete(customer)
        db.session.commit()
        return True
