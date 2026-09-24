from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required
from app.constants import SalaryStatus  # Add this import

salary_bp = Blueprint('salary', __name__)

def get_salary_model():
    """Lazy import for Salary model"""
    from app.models.wps.salary import Salary
    return Salary

def get_employee_model():
    """Lazy import for Employee model"""
    from app.models.wps.employee import Employee
    return Employee

def get_db():
    """Lazy import for db"""
    from app import db
    return db

@salary_bp.route('/salaries')
@login_required
def salaries():
    """
    Display all salary records
    """
    Salary = get_salary_model()
    Employee = get_employee_model()
    
    try:
        # Get filter parameters
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        
        # Build query with filters
        query = Salary.query
        
        if month:
            query = query.filter_by(month=month)
        if year:
            query = query.filter_by(year=year)
        
        salaries = query.all()
        
        # DEBUG: Get all employees first
        all_employees_raw = Employee.query.all()
        print(f"DEBUG in salaries(): Raw employee count: {len(all_employees_raw)}")
        
        # Filter for active employees
        all_employees = []
        for emp in all_employees_raw:
            # Check if employee is active
            is_active = emp.employment_status == 'active' and emp.deleted_at is None
            print(f"DEBUG: Employee {emp.id}: {emp.name}, "
                  f"status={emp.employment_status}, "
                  f"deleted_at={emp.deleted_at}, "
                  f"is_active={is_active}")
            
            if is_active:
                all_employees.append(emp)
        
        print(f"DEBUG in salaries(): Active employee count: {len(all_employees)}")
        
        # Calculate totals
        basic_salary_total = 0
        allowances_total = 0
        deductions_total = 0
        net_salary_total = 0
        
        for salary in salaries:
            basic_salary_total += salary.basic_salary or 0
            
            # Sum allowances
            allowances = 0
            allowances += salary.housing_allowance or 0
            allowances += salary.transportation_allowance or 0
            allowances += salary.other_allowances or 0
            allowances_total += allowances
            
            # Sum deductions - FIXED: Use correct field name
            if hasattr(salary, 'deductions_amount') and salary.deductions_amount:
                deductions_total += salary.deductions_amount
            elif hasattr(salary, 'total_deductions') and salary.total_deductions:
                deductions_total += salary.total_deductions
            else:
                deductions_total += 0
            
            # Net salary
            net_salary_total += salary.net_salary or 0
        
        totals = {
            'basic_salary': basic_salary_total,
            'allowances': allowances_total,
            'deductions': deductions_total,  # This should now work
            'net_salary': net_salary_total
        }
        
        return render_template('employee/salaries.html', 
                             salaries=salaries,
                             totals=totals,
                             all_employees=all_employees,
                             month=month,
                             year=year)
    except Exception as e:
        print(f"ERROR in salaries(): {str(e)}")
        flash(f'Error loading salaries: {e}', 'danger')
        Employee = get_employee_model()
        all_employees = Employee.query.all()
        return render_template('employee/salaries.html', 
                             salaries=[], 
                             totals={'basic_salary': 0, 'allowances': 0, 'deductions': 0, 'net_salary': 0},
                             all_employees=all_employees,
                             month=None,
                             year=None)

@salary_bp.route('/salaries/create', methods=['GET', 'POST'])
@login_required
def create_salary():
    """
    Create new salary record - FIXED VERSION
    """
    Salary = get_salary_model()
    Employee = get_employee_model()
    db = get_db()
    
    employees = Employee.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        # Add at the beginning of the POST handler:
        print(f"DEBUG edit_salary: Form data received")
        print(f"  basic_salary: {request.form.get('basic_salary')}")
        print(f"  housing_allowance: {request.form.get('housing_allowance')}")
        print(f"  bonus_descriptions[]: {request.form.getlist('bonus_descriptions[]')}")
        print(f"  bonus_amounts[]: {request.form.getlist('bonus_amounts[]')}")
        try:
            from datetime import datetime
            
            # Get form data with proper field names
            salary_data = {
                'employee_id': request.form.get('employee_id'),
                'basic_salary': float(request.form.get('basic_salary', 0)),
                # Use correct allowance fields
                'housing_allowance': float(request.form.get('housing_allowance', 0) or 0),
                'transportation_allowance': float(request.form.get('transportation_allowance', 0) or 0),
                'other_allowances': float(request.form.get('other_allowances', 0) or 0),
                # Use correct deductions field
                'deductions_amount': float(request.form.get('deductions', 0) or 0),
                'payment_date': datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d') if request.form.get('payment_date') else None,
                'payment_method': request.form.get('payment_method', 'bank'),
                'payment_reference': request.form.get('payment_reference'),
                'notes': request.form.get('notes'),
                'status': SalaryStatus.PENDING  # Use enum instead of string
            }
            
            # Calculate net salary
            total_allowances = (salary_data['housing_allowance'] + 
                               salary_data['transportation_allowance'] + 
                               salary_data['other_allowances'])
            salary_data['net_salary'] = salary_data['basic_salary'] + total_allowances - salary_data['deductions_amount']
            
            # Calculate gross salary
            salary_data['gross_salary'] = salary_data['basic_salary'] + total_allowances
            
            # Calculate total deductions (just deductions_amount for now)
            salary_data['total_deductions'] = salary_data['deductions_amount']
            
            salary = Salary(**salary_data)
            db.session.add(salary)
            db.session.commit()
            
            flash('Salary record created successfully!', 'success')
            return redirect(url_for('salary.salaries'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating salary record: {str(e)}', 'danger')
    
    return render_template('employee/create_salary.html', employees=employees)

@salary_bp.route('/salaries/<int:salary_id>')
@login_required
def view_salary(salary_id):
    """
    View salary details
    """
    Salary = get_salary_model()
    
    try:
        salary = Salary.query.get_or_404(salary_id)
        
        # Get lists from the model
        deductions_list = salary.deductions_list
        bonuses_list = salary.bonuses_list
        
        return render_template('employee/view_salary.html', 
                             salary=salary, 
                             deductions_list=deductions_list,
                             bonuses_list=bonuses_list)
    except Exception as e:
        print(f"ERROR in view_salary(): {str(e)}")
        flash(f'Error loading salary record: {str(e)}', 'danger')
        return redirect(url_for('salary.salaries'))
    
@salary_bp.route('/salaries/<int:salary_id>/mark-paid', methods=['POST'])
@login_required
def mark_salary_paid(salary_id):
    """
    Mark salary as paid
    """
    from datetime import datetime
    Salary = get_salary_model()
    Employee = get_employee_model()
    db = get_db()
    
    try:
        salary = Salary.query.get_or_404(salary_id)
        
        # Get employee name for flash message
        employee = Employee.query.get(salary.employee_id)
        employee_name = employee.name if employee else "Unknown"
        
        # Check if salary is already paid - use enum
        if salary.status == SalaryStatus.PAID:
            flash(f'Salary for {employee_name} is already marked as paid!', 'warning')
            return redirect(url_for('salary.salaries'))
        
        # Update salary status and payment date
        salary.status = SalaryStatus.PAID  # Use enum
        salary.payment_date = datetime.now()
        
        db.session.commit()
        
        flash(f'Salary for {employee_name} marked as paid successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking salary as paid: {str(e)}', 'danger')
    
    return redirect(url_for('salary.salaries'))

@salary_bp.route('/salaries/<int:salary_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_salary(salary_id):
    """
    Edit salary details - FIXED VERSION
    """
    Salary = get_salary_model()
    Employee = get_employee_model()
    db = get_db()
    
    salary = Salary.query.get_or_404(salary_id)
    employees = Employee.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        try:
            from datetime import datetime
            import json
            
            # Update employee
            salary.employee_id = request.form.get('employee_id', salary.employee_id)
            
            # Update basic salary
            salary.basic_salary = float(request.form.get('basic_salary', salary.basic_salary))
            
            # Update allowances
            salary.housing_allowance = float(request.form.get('housing_allowance', salary.housing_allowance) or 0)
            salary.transportation_allowance = float(request.form.get('transportation_allowance', salary.transportation_allowance) or 0)
            salary.other_allowances = float(request.form.get('other_allowances', salary.other_allowances) or 0)
            
            # Update overtime
            salary.overtime_hours = float(request.form.get('overtime_hours', salary.overtime_hours) or 0)
            salary.overtime_rate = float(request.form.get('overtime_rate', salary.overtime_rate) or 0)
            salary.overtime_amount = salary.overtime_hours * salary.overtime_rate
            
            # Update statutory deductions
            salary.tax_amount = float(request.form.get('tax_amount', salary.tax_amount) or 0)
            salary.social_security_amount = float(request.form.get('social_security_amount', salary.social_security_amount) or 0)
            salary.other_deductions = float(request.form.get('other_deductions', salary.other_deductions) or 0)
            
            # Update other deductions field
            salary.deductions_amount = float(request.form.get('deductions', salary.deductions_amount) or 0)
            
            # Process dynamic bonuses
            bonus_descriptions = request.form.getlist('bonus_descriptions[]')
            bonus_amounts = request.form.getlist('bonus_amounts[]')
            bonuses = []
            total_bonus = 0
            for desc, amt in zip(bonus_descriptions, bonus_amounts):
                if desc and amt:
                    bonuses.append({
                        'description': desc,
                        'amount': float(amt),
                        'type': 'bonus'
                    })
                    total_bonus += float(amt)
            
            # Process dynamic deductions
            deduction_descriptions = request.form.getlist('deduction_descriptions[]')
            deduction_amounts = request.form.getlist('deduction_amounts[]')
            deductions = []
            total_deduction = 0
            for desc, amt in zip(deduction_descriptions, deduction_amounts):
                if desc and amt:
                    deductions.append({
                        'description': desc,
                        'amount': float(amt),
                        'type': 'deduction'
                    })
                    total_deduction += float(amt)
            
            # Update JSON data fields
            salary.bonuses_data = json.dumps(bonuses) if bonuses else None
            salary.deductions_data = json.dumps(deductions) if deductions else None
            salary.incentives_amount = total_bonus
            salary.deductions_amount = total_deduction
            
            # Recalculate totals using model methods
            salary.gross_salary = salary.calculate_gross_salary()
            salary.total_deductions = salary.calculate_total_deductions()
            salary.net_salary = salary.gross_salary - salary.total_deductions
            
            # Update payment info
            payment_date_str = request.form.get('payment_date')
            if payment_date_str:
                salary.payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d')
            
            salary.payment_method = request.form.get('payment_method', salary.payment_method)
            salary.payment_reference = request.form.get('payment_reference', salary.payment_reference)
            salary.notes = request.form.get('notes', salary.notes)
            
            # Update status if provided
            status = request.form.get('status')
            if status:
                if status.upper() == 'PENDING':
                    salary.status = SalaryStatus.PENDING
                elif status.upper() == 'PAID':
                    salary.status = SalaryStatus.PAID
                elif status.upper() == 'PROCESSING':
                    salary.status = SalaryStatus.PROCESSING
                elif status.upper() == 'CANCELLED':
                    salary.status = SalaryStatus.CANCELLED
            
            db.session.commit()
            flash('Salary record updated successfully!', 'success')
            return redirect(url_for('salary.view_salary', salary_id=salary.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"ERROR in edit_salary: {str(e)}")  # Debug logging
            flash(f'Error updating salary record: {str(e)}', 'danger')
    
    # GET request - prepare data for template
    return render_template('employee/edit_salary.html', 
                         salary=salary, 
                         employees=employees,
                         bonuses_list=salary.bonuses_list,
                         deductions_list=salary.deductions_list)

@salary_bp.route('/salaries/<int:salary_id>/delete', methods=['POST'])
@login_required
def delete_salary(salary_id):
    """
    Delete salary record
    """
    Salary = get_salary_model()
    db = get_db()
    
    try:
        salary = Salary.query.get_or_404(salary_id)
        db.session.delete(salary)
        db.session.commit()
        flash('Salary record deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting salary record: {e}', 'danger')
    
    return redirect(url_for('salary.salaries'))

@salary_bp.route('/process/<int:employee_id>', methods=['GET', 'POST'])
@login_required
def process_salary(employee_id):
    """
    Process salary for a specific employee with duplicate prevention
    """
    from datetime import datetime
    import json
    from app.models.wps.salary import Salary
    from app.models.wps.employee import Employee
    from app import db
    from sqlalchemy.exc import IntegrityError
    
    try:
        employee = Employee.query.get_or_404(employee_id)
        current_date = datetime.now()

        if request.method == 'POST':
            try:
                # Get form data
                month = int(request.form.get('month', datetime.now().month))
                year = int(request.form.get('year', datetime.now().year))
                overtime_hours = float(request.form.get('overtime_hours', 0))
                overtime_rate_form = request.form.get('overtime_rate')
                overtime_rate = float(overtime_rate_form) if overtime_rate_form else employee.overtime_rate

                housing_allowance_form = request.form.get('housing_allowance')
                transportation_allowance_form = request.form.get('transportation_allowance')
                other_allowances_form = request.form.get('other_allowances')

                # Use form values if provided, otherwise use employee's defaults
                housing_allowance = float(housing_allowance_form) if housing_allowance_form else employee.housing_allowance
                transportation_allowance = float(transportation_allowance_form) if transportation_allowance_form else employee.transportation_allowance
                other_allowances = float(other_allowances_form) if other_allowances_form else employee.other_allowances

                # CRITICAL FIX: Get all deduction fields from form
                tax_amount = float(request.form.get('tax_amount', 0) or 0)
                social_security_amount = float(request.form.get('social_security_amount', 0) or 0)
                other_deductions_field = float(request.form.get('other_deductions', 0) or 0)
                listed_deductions = float(request.form.get('deductions', 0) or 0)  # This is deductions_amount

                # Check for existing salary
                existing_salary = Salary.query.filter_by(
                    employee_id=employee_id,
                    month=month,
                    year=year
                ).first()
                if existing_salary:
                    flash(f'Salary for {employee.name} ({month}/{year}) already exists with status: {existing_salary.status}. '
                  f'You can view or edit it from the salaries list.', 'warning')
                    return redirect(url_for('salary.view_salary', salary_id=existing_salary.id))
                
                # Get bonuses from form
                bonus_descriptions = request.form.getlist('bonus_descriptions[]')
                bonus_amounts = request.form.getlist('bonus_amounts[]')
                bonuses = []
                total_bonus = 0
                for desc, amt in zip(bonus_descriptions, bonus_amounts):
                    if desc and amt:
                        bonuses.append({
                            'description': desc,
                            'amount': float(amt),
                            'type': 'bonus'
                        })
                        total_bonus += float(amt)
                
                # Get deductions from form
                deduction_descriptions = request.form.getlist('deduction_descriptions[]')
                deduction_amounts = request.form.getlist('deduction_amounts[]')

                deductions = []
                total_deduction = 0
                for desc, amt in zip(deduction_descriptions, deduction_amounts):
                    if desc and amt:
                        deductions.append({
                            'description': desc,
                            'amount': float(amt),
                            'type': 'deduction'
                        })
                        total_deduction += float(amt)
                
                # Calculate working days
                working_days = int(request.form.get('working_days', 22))
                leave_days = int(request.form.get('leave_days', 0))
                absent_days = int(request.form.get('absent_days', 0))
                actual_worked_days = working_days - leave_days - absent_days

                # FIX: DO NOT calculate gross/total/net here - let the model handle it!
                # Just calculate overtime_amount since the model needs overtime_hours and overtime_rate
                overtime_amount = overtime_hours * overtime_rate

                # Get status from form - convert string to enum
                status_str = request.form.get('status', 'pending')
                if status_str.upper() == 'PENDING':
                    status = SalaryStatus.PENDING
                elif status_str.upper() == 'PAID':
                    status = SalaryStatus.PAID
                elif status_str.upper() == 'PROCESSING':
                    status = SalaryStatus.PROCESSING
                else:
                    status = SalaryStatus.PENDING
                
                # Create salary record - PASS ALL COMPONENTS, MODEL WILL CALCULATE
                salary = Salary(
                    employee_id=employee.id,
                    month=month,
                    year=year,
                    basic_salary=employee.basic_salary,
                    housing_allowance=housing_allowance,
                    transportation_allowance=transportation_allowance,
                    other_allowances=other_allowances,
                    overtime_hours=overtime_hours,
                    overtime_rate=overtime_rate,
                    # overtime_amount will be calculated by model
                    bonuses_data=json.dumps(bonuses) if bonuses else "[]",
                    incentives_amount=total_bonus,
                    deductions_data=json.dumps(deductions) if deductions else "[]",
                    deductions_amount=total_deduction + listed_deductions,  # Combine dynamic and listed deductions
                    # CRITICAL: ADD THESE MISSING FIELDS
                    tax_amount=tax_amount,
                    social_security_amount=social_security_amount,
                    other_deductions=other_deductions_field,
                    working_days=working_days,
                    actual_worked_days=actual_worked_days,
                    leave_days=leave_days,
                    absent_days=absent_days,
                    status=status,
                    payment_date=datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d') if request.form.get('payment_date') else None
                )
                # Note: gross_salary, total_deductions, and net_salary are calculated by Salary.__init__()
                db.session.add(salary)
                db.session.commit()
                
                # Debug: Print calculation results
                print(f"DEBUG: Salary #{salary.id} calculations:")
                print(f"  Basic: {salary.basic_salary}")
                print(f"  Housing Allowance: {salary.housing_allowance}")
                print(f"  Transportation Allowance: {salary.transportation_allowance}")
                print(f"  Other Allowances: {salary.other_allowances}")
                print(f"  Total Allowances: {salary.housing_allowance + salary.transportation_allowance + salary.other_allowances}")
                print(f"  Overtime: {salary.overtime_amount} ({salary.overtime_hours} hrs × {salary.overtime_rate})")
                print(f"  Incentives: {salary.incentives_amount}")
                print(f"  Gross Salary: {salary.gross_salary}")
                print(f"  Tax: {salary.tax_amount}")
                print(f"  Social Security: {salary.social_security_amount}")
                print(f"  Other Deductions: {salary.other_deductions}")
                print(f"  Listed Deductions: {salary.deductions_amount}")
                print(f"  Total Deductions: {salary.total_deductions}")
                print(f"  Net Salary: {salary.net_salary}")
        
                flash(f'Salary processed successfully for {employee.name} ({month}/{year})! Net: AED {salary.net_salary:.2f}', 'success')
                return redirect(url_for('salary.view_salary', salary_id=salary.id))
            except IntegrityError as e:
                db.session.rollback()
                flash(f'Salary for {employee.name} ({month}/{year}) already exists! Database prevented duplicate entry.', 'danger')
                return redirect(url_for('salary.salaries'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error processing salary: {str(e)}', 'danger')
                
        # GET request - show form
        current_date = datetime.now()
        return render_template('employee/process_salary.html', 
                             employee=employee,
                             current_month=current_date.month,
                             current_year=current_date.year,
                             now=current_date)
        
    except Exception as e:
        flash(f'Error loading employee: {str(e)}', 'danger')
        return redirect(url_for('employee.employees'))
    
@salary_bp.route('/api/check-existing-salary/<int:employee_id>')
@login_required
def check_existing_salary(employee_id):
    """
    API endpoint to check if salary exists for given employee and period
    """
    try:
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        
        if not month or not year:
            return jsonify({'error': 'Month and year required'}), 400
        
        Salary = get_salary_model()
        existing = Salary.query.filter_by(
            employee_id=employee_id,
            month=month,
            year=year
        ).first()
        
        if existing:
            return jsonify({
                'exists': True,
                'salary_id': existing.id,
                'salary_number': existing.salary_number,
                'status': existing.status.value,  # Use .value to get string
                'net_salary': existing.net_salary,
                'created_at': existing.created_at.strftime('%Y-%m-%d %H:%M') if existing.created_at else None,
                'message': f'Salary for {month}/{year} already exists'
            })
        
        return jsonify({'exists': False})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@salary_bp.route('/api/employees')
@login_required
def get_all_employees():
    """
    API endpoint to get active employees for dropdown
    """
    Employee = get_employee_model()
    try:
        # Use proper conditions for active employees
        employees = Employee.query.filter(
            Employee.employment_status == 'active',
            Employee.deleted_at.is_(None)
        ).all()
        
        employees_data = []
        for emp in employees:
            employees_data.append({
                'id': emp.id,
                'name': emp.name,
                'position': emp.position,
                'department': emp.department,
                'basic_salary': float(emp.basic_salary) if emp.basic_salary else 0,
                'is_active': True  # Since we filtered for active
            })
        return jsonify(employees_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@salary_bp.route('/debug/employees')
@login_required
def debug_employees():
    """
    Debug endpoint to check employee data
    """
    Employee = get_employee_model()
    employees = Employee.query.all()
    
    result = []
    for emp in employees:
        result.append({
            'id': emp.id,
            'name': emp.name,
            'employment_status': emp.employment_status,
            'deleted_at': str(emp.deleted_at),
            'is_active_python': emp.employment_status == 'active' and emp.deleted_at is None
        })
    
    return jsonify({
        'total_employees': len(employees),
        'employees': result
    })