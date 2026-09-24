from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required
from datetime import datetime
import json

employee_bp = Blueprint('employee', __name__)

def get_employee_model():
    """Lazy import for Employee model"""
    from app.models.wps.employee import Employee
    return Employee

def get_db():
    """Lazy import for db"""
    from app import db
    return db

def get_salary_model():
    """Lazy import for Salary model"""
    from app.models.wps.salary import Salary
    return Salary

@employee_bp.route('/employees')
@login_required
def employees():
    """
    Display employees with status filtering including 'deleted' status
    """
    Employee = get_employee_model()
    
    try:
        # Get filter parameter
        status = request.args.get('status', 'active')
        
        # Build query based on filter
        query = Employee.query
        
        if status == 'active':
            # Active employees: employment_status = 'active' AND deleted_at IS NULL
            query = query.filter(
                Employee.employment_status == 'active',
                Employee.deleted_at.is_(None)
            )
        elif status == 'inactive':
            # Inactive employees: employment_status = 'inactive' AND deleted_at IS NULL
            query = query.filter(
                Employee.employment_status == 'inactive',
                Employee.deleted_at.is_(None)
            )
        elif status == 'deleted':
            # Deleted employees: employment_status = 'deleted' OR deleted_at IS NOT NULL
            query = query.filter(
                (Employee.employment_status == 'deleted') | 
                (Employee.deleted_at.isnot(None))
            )
        # If 'all', no filter applied
        
        employees = query.order_by(Employee.name).all()
        
        # Get counts for tabs
        active_count = Employee.query.filter(
            Employee.employment_status == 'active',
            Employee.deleted_at.is_(None)
        ).count()
        
        inactive_count = Employee.query.filter(
            Employee.employment_status == 'inactive',
            Employee.deleted_at.is_(None)
        ).count()
        
        deleted_count = Employee.query.filter(
            (Employee.employment_status == 'deleted') | 
            (Employee.deleted_at.isnot(None))
        ).count()
        
        total_count = Employee.query.count()
        
        return render_template('employee/employees.html', 
                             employees=employees,
                             active_count=active_count,
                             inactive_count=inactive_count,
                             deleted_count=deleted_count,
                             total_count=total_count,
                             current_status=status)
    except Exception as e:
        flash(f'Error loading employees: {e}', 'danger')
        return render_template('employee/employees.html', 
                             employees=[],
                             active_count=0,
                             inactive_count=0,
                             deleted_count=0,
                             total_count=0,
                             current_status='active')

@employee_bp.route('/employees/create', methods=['GET', 'POST'])
@login_required
def create_employee():
    """
    Create new employee
    """
    Employee = get_employee_model()
    db = get_db()
    
    if request.method == 'POST':
        try:
            # Get form data with proper validation
            employee_data = {
                'name': request.form.get('name', '').strip(),
                'emirates_id': request.form.get('emirates_id', '').strip() or None,
                'passport_number': request.form.get('passport_number', '').strip() or None,
                'phone_number': request.form.get('phone_number', '').strip(),
                'email': request.form.get('email', '').strip() or None,
                'position': request.form.get('position', '').strip(),
                'department': request.form.get('department', '').strip(),
                'basic_salary': float(request.form.get('basic_salary', 0)),
                'housing_allowance': float(request.form.get('housing_allowance', 0) or 0),
                'transportation_allowance': float(request.form.get('transportation_allowance', 0) or 0),
                'other_allowances': float(request.form.get('other_allowances', 0) or 0),
                'join_date': request.form.get('join_date') or None,
                'bank_name': request.form.get('bank_name', '').strip() or None,
                'bank_account': request.form.get('bank_account', '').strip() or None,
            }
            
            # Set employment_status based on checkbox
            if request.form.get('is_active') == 'on':
                employee_data['employment_status'] = 'active'
            else:
                employee_data['employment_status'] = 'inactive'
            
            # Validate required fields
            if not employee_data['name']:
                flash('Name is required', 'danger')
                return render_template('employee/create_employee.html')
            
            if not employee_data['phone_number']:
                flash('Phone number is required', 'danger')
                return render_template('employee/create_employee.html')
            
            if employee_data['basic_salary'] <= 0:
                flash('Basic salary must be greater than 0', 'danger')
                return render_template('employee/create_employee.html')
            
            employee = Employee(**employee_data)
            db.session.add(employee)
            db.session.commit()
            
            flash('Employee created successfully!', 'success')
            return redirect(url_for('employee.employees'))
            
        except ValueError as e:
            db.session.rollback()
            flash(f'Invalid input format: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating employee: {str(e)}', 'danger')
    
    return render_template('employee/create_employee.html')

@employee_bp.route('/employees/<int:employee_id>')
@login_required
def view_employee(employee_id):
    """
    View employee details
    """
    Employee = get_employee_model()
    
    try:
        employee = Employee.query.get_or_404(employee_id)
        return render_template('employee/view_employee.html', employee=employee)
    except Exception as e:
        flash(f'Error loading employee: {e}', 'danger')
        return redirect(url_for('employee.employees'))

@employee_bp.route('/employees/<int:employee_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_employee(employee_id):
    """
    Edit employee details
    """
    Employee = get_employee_model()
    db = get_db()
    
    employee = Employee.query.get_or_404(employee_id)
    
    if request.method == 'POST':
        try:
            # Update all fields from the form
            employee.name = request.form.get('name', employee.name)
            employee.emirates_id = request.form.get('emirates_id', employee.emirates_id) or None
            employee.passport_number = request.form.get('passport_number', employee.passport_number) or None
            employee.phone_number = request.form.get('phone_number', employee.phone_number)
            employee.email = request.form.get('email', employee.email) or None
            employee.position = request.form.get('position', employee.position)
            employee.department = request.form.get('department', employee.department)
            
            # Convert salary fields
            try:
                employee.basic_salary = float(request.form.get('basic_salary', employee.basic_salary))
                employee.housing_allowance = float(request.form.get('housing_allowance', employee.housing_allowance) or 0)
                employee.transportation_allowance = float(request.form.get('transportation_allowance', employee.transportation_allowance) or 0)
                employee.other_allowances = float(request.form.get('other_allowances', employee.other_allowances) or 0)
            except ValueError:
                flash('Invalid salary format. Please enter numeric values.', 'danger')
                return render_template('employee/edit_employee.html', employee=employee)
            
            employee.join_date = request.form.get('join_date', employee.join_date) or None
            employee.bank_name = request.form.get('bank_name', employee.bank_name) or None
            employee.bank_account = request.form.get('bank_account', employee.bank_account) or None
            
            # Handle employment_status based on is_active checkbox
            # The checkbox returns 'on' if checked, None if not
            if request.form.get('is_active') == 'on':
                # Activate: set status to 'active' and clear deleted_at if it exists
                employee.employment_status = 'active'
                employee.deleted_at = None
            else:
                # Deactivate: set status to 'inactive'
                employee.employment_status = 'inactive'
            
            # Validate required fields
            if not employee.name or not employee.name.strip():
                flash('Name is required', 'danger')
                return render_template('employee/edit_employee.html', employee=employee)
            
            if not employee.phone_number or not employee.phone_number.strip():
                flash('Phone number is required', 'danger')
                return render_template('employee/edit_employee.html', employee=employee)
            
            if employee.basic_salary <= 0:
                flash('Basic salary must be greater than 0', 'danger')
                return render_template('employee/edit_employee.html', employee=employee)
            
            db.session.commit()
            flash('Employee updated successfully!', 'success')
            return redirect(url_for('employee.employees'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating employee: {str(e)}', 'danger')
    
    return render_template('employee/edit_employee.html', employee=employee)

@employee_bp.route('/employees/<int:employee_id>/toggle-status', methods=['POST'])
@login_required
def toggle_employee_status(employee_id):
    """
    Toggle employee active/inactive status
    This toggles between 'active' and 'inactive' employment_status
    """
    Employee = get_employee_model()
    db = get_db()
    
    try:
        employee = Employee.query.get_or_404(employee_id)
        
        # Toggle the employment_status
        if employee.employment_status == 'active':
            # Deactivate the employee
            employee.employment_status = 'inactive'
            action = 'deactivated'
        else:
            # Activate the employee
            employee.employment_status = 'active'
            # Also clear deleted_at if it was set (soft delete)
            employee.deleted_at = None
            action = 'activated'
        
        db.session.commit()
        flash(f'Employee {employee.name} has been {action} successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error toggling employee status: {str(e)}', 'danger')
    
    return redirect(url_for('employee.employees'))

@employee_bp.route('/employees/<int:employee_id>/delete', methods=['POST'])
@login_required
def delete_employee(employee_id):
    """
    SAFE DELETE: Mark employee as deleted instead of hard delete
    """
    Employee = get_employee_model()
    db = get_db()
    
    try:
        # Get the employee
        employee = Employee.query.get_or_404(employee_id)
        employee_name = employee.name
        
        # Check if employee is already marked as deleted
        if employee.employment_status == 'deleted':
            flash(f'Employee {employee_name} is already marked as deleted.', 'warning')
            return redirect(url_for('employee.employees', status='inactive'))
        
        # Store original values in a JSON field for possible restoration
        deletion_backup = {
            'original_phone': employee.phone_number,
            'original_email': employee.email,
            'original_emirates_id': employee.emirates_id,
            'original_name': employee.name,
            'deleted_at': datetime.utcnow().isoformat()
        }
        
        # Store backup in qualifications field (or create a new field if needed)
        if employee.qualifications:
            employee.qualifications = f"{employee.qualifications}\n\nDELETION_BACKUP: {json.dumps(deletion_backup)}"
        else:
            employee.qualifications = f"DELETION_BACKUP: {json.dumps(deletion_backup)}"
        
        # STEP 1: Mark employment status as 'deleted'
        employee.employment_status = 'deleted'
        
        # STEP 2: Set deleted_at timestamp
        employee.deleted_at = datetime.utcnow()
        
        # STEP 3: Modify name to show it's deleted
        employee.name = f"[DELETED] {employee.name}"
        
        # STEP 4: Set phone number to a valid but anonymized format
        # Instead of prefixing with "DELETED_", use a valid UAE format
        if employee.phone_number:
            # Extract just the digits
            digits = ''.join(filter(str.isdigit, employee.phone_number))
            if digits:
                # Use a valid UAE number format that indicates deletion
                # Ensure it's within 20 character limit
                employee.phone_number = f"+9715{int(digits[-8:]):08d}"[:20]  # Valid UAE format, max 20 chars
            else:
                employee.phone_number = "+971500000000"  # Fallback
        
        # STEP 5: Set email to a valid but anonymized format (within 100 char limit)
        if employee.email:
            # Create a valid email format that indicates deletion
            # Ensure it's within 100 character limit
            email_prefix = f"deleted.{employee.id}"
            domain = "example.com"
            max_prefix_len = 100 - len(domain) - 1  # -1 for '@'
            if len(email_prefix) > max_prefix_len:
                email_prefix = email_prefix[:max_prefix_len]
            employee.email = f"{email_prefix}@{domain}"
        else:
            # Ensure email is within 100 char limit
            email_prefix = f"deleted.{employee.id}"
            if len(email_prefix) > 99:  # 100 - 1 for '@'
                email_prefix = email_prefix[:99]
            employee.email = f"{email_prefix}@example.com"
        
        # STEP 6: For Emirates ID, use a valid format that indicates deletion
        if employee.emirates_id:
            # Keep the format but mark as deleted
            # UAE Emirates ID format: 784-XXXX-XXXXXXX-X
            # We'll use: 784-9999-9999999-9 (obviously invalid but valid format)
            employee.emirates_id = "784-9999-9999999-9"
        
        # STEP 7: Clear sensitive data
        employee.passport_number = None
        employee.bank_name = None
        employee.bank_account = None
        employee.bank_iban = None
        employee.bank_branch = None
        employee.address = "Address removed"
        employee.emergency_contact_name = None
        employee.emergency_contact_phone = None
        employee.emergency_contact_relation = None
        
        # STEP 8: Clear document URLs
        employee.passport_copy_url = None
        employee.emirates_id_copy_url = None
        employee.photo_url = None
        employee.visa_copy_url = None
        employee.labor_card_url = None
        
        # STEP 9: Update employee code - FIXED: Ensure it doesn't exceed 20 characters
        if employee.employee_code:
            # Use shorter prefix 'D_' instead of 'DEL_'
            original_code = employee.employee_code
            # Ensure total length doesn't exceed 20
            if len(original_code) > 18:  # 18 + 2 ("D_") = 20
                original_code = original_code[:18]  # Truncate if necessary
            employee.employee_code = f"D_{original_code}"
        
        db.session.commit()
        
        flash(f'Employee "{employee_name}" has been marked as deleted successfully. All sensitive data has been anonymized.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking employee as deleted: {str(e)}', 'danger')
    
    return redirect(url_for('employee.employees', status='inactive'))

@employee_bp.route('/employees/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_employees():
    """
    Bulk mark employees as deleted
    """
    Employee = get_employee_model()
    db = get_db()
    
    try:
        # Get employee IDs from form
        employee_ids_str = request.form.get('employee_ids', '')
        if not employee_ids_str:
            flash('No employees selected for deletion.', 'warning')
            return redirect(url_for('employee.employees', status='inactive'))
        
        # Convert string to list of integers
        employee_ids = [int(id.strip()) for id in employee_ids_str.split(',') if id.strip()]
        
        deleted_count = 0
        already_deleted_count = 0
        failed_deletions = []
        
        for emp_id in employee_ids:
            try:
                employee = Employee.query.get(emp_id)
                
                if not employee:
                    failed_deletions.append(f"Employee ID {emp_id} not found")
                    continue
                
                # Check if already deleted
                if employee.employment_status == 'deleted':
                    already_deleted_count += 1
                    continue
                
                # Mark as deleted
                employee.employment_status = 'deleted'
                employee.deleted_at = datetime.utcnow()
                employee.name = f"[DELETED] {employee.name}"
                
                # Anonymize sensitive data
                if employee.phone_number:
                    # Ensure within 20 character limit
                    digits = ''.join(filter(str.isdigit, employee.phone_number))
                    if digits:
                        employee.phone_number = f"+9715{int(digits[-8:]):08d}"[:20]
                    else:
                        employee.phone_number = "+971500000000"
                
                if employee.email:
                    # Ensure within 100 character limit
                    email_prefix = f"deleted.{employee.id}"
                    if len(email_prefix) > 99:
                        email_prefix = email_prefix[:99]
                    employee.email = f"{email_prefix}@example.com"
                
                if employee.emirates_id:
                    employee.emirates_id = "784-9999-9999999-9"
                
                # Update employee code - ensure it doesn't exceed 20 characters
                if employee.employee_code:
                    original_code = employee.employee_code
                    if len(original_code) > 18:
                        original_code = original_code[:18]
                    employee.employee_code = f"D_{original_code}"
                
                employee.bank_account = None
                employee.bank_name = None
                
                deleted_count += 1
                
            except Exception as e:
                failed_deletions.append(f"Employee ID {emp_id}: {str(e)[:50]}...")
        
        db.session.commit()
        
        # Prepare flash messages
        if deleted_count > 0:
            flash(f'Successfully marked {deleted_count} employee(s) as deleted.', 'success')
        
        if already_deleted_count > 0:
            flash(f'{already_deleted_count} employee(s) were already marked as deleted.', 'info')
        
        if failed_deletions:
            error_msg = f'{len(failed_deletions)} employee(s) could not be processed: '
            error_msg += ', '.join(failed_deletions[:3])  # Show first 3 errors
            if len(failed_deletions) > 3:
                error_msg += f'... and {len(failed_deletions) - 3} more'
            flash(error_msg, 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error during bulk deletion: {str(e)}', 'danger')
    
    return redirect(url_for('employee.employees', status='inactive'))

@employee_bp.route('/employees/<int:employee_id>/restore', methods=['POST'])
@login_required
def restore_employee(employee_id):
    """
    Restore a deleted employee
    """
    Employee = get_employee_model()
    db = get_db()
    
    try:
        employee = Employee.query.get_or_404(employee_id)
        
        # Check if employee is actually deleted
        if employee.employment_status != 'deleted' and employee.deleted_at is None:
            flash(f'Employee {employee.name} is not marked as deleted.', 'warning')
            return redirect(url_for('employee.employees'))
        
        # Restore employment status
        employee.employment_status = 'inactive'  # Set to inactive, admin can activate later
        
        # Clear deleted_at timestamp
        employee.deleted_at = None
        
        # Remove "[DELETED]" prefix from name
        if employee.name.startswith("[DELETED] "):
            employee.name = employee.name.replace("[DELETED] ", "", 1)
        
        # Restore original data if we stored it
        # Note: In production, you might want to store original values separately
        
        # For phone number: remove DELETED_ prefix if present
        if employee.phone_number and employee.phone_number.startswith("DELETED_"):
            employee.phone_number = employee.phone_number.replace("DELETED_", "", 1)
        
        # For email: restore original if possible (simplified)
        if employee.email and "deleted_" in employee.email:
            # This is simplified - in production you'd have stored the original
            pass
        
        # For Emirates ID: remove DELETED_ prefix if present
        if employee.emirates_id and employee.emirates_id.startswith("DELETED_"):
            employee.emirates_id = employee.emirates_id.replace("DELETED_", "", 1)
        
        db.session.commit()
        
        flash(f'Employee {employee.name} has been restored successfully and moved to inactive list.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring employee: {str(e)}', 'danger')
    
    return redirect(url_for('employee.employees', status='inactive'))

@employee_bp.route('/employees/export', methods=['GET'])
@login_required
def export_employees():
    """
    Export employees to CSV
    """
    Employee = get_employee_model()
    
    try:
        status = request.args.get('status', 'active')
        
        # Build query based on filter
        query = Employee.query
        
        if status == 'active':
            query = query.filter(Employee.employment_status == 'active', Employee.deleted_at.is_(None))
        elif status == 'inactive':
            query = query.filter(Employee.employment_status == 'inactive', Employee.deleted_at.is_(None))
        elif status == 'deleted':
            query = query.filter((Employee.employment_status == 'deleted') | (Employee.deleted_at.isnot(None)))
        
        employees = query.order_by(Employee.name).all()
        
        # Create CSV content
        import csv
        from io import StringIO
        from flask import Response
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Name', 'Emirates ID', 'Phone Number', 'Email', 
            'Position', 'Department', 'Basic Salary', 'Housing Allowance',
            'Transportation Allowance', 'Other Allowances', 'Total Salary',
            'Join Date', 'Bank Name', 'Bank Account', 'Status'
        ])
        
        # Write data rows
        for emp in employees:
            total_salary = emp.basic_salary + (emp.housing_allowance or 0) + \
                          (emp.transportation_allowance or 0) + (emp.other_allowances or 0)
            
            # Determine status
            if emp.employment_status == 'deleted' or emp.deleted_at:
                status_text = 'Deleted'
            elif emp.employment_status == 'active':
                status_text = 'Active'
            else:
                status_text = 'Inactive'
            
            writer.writerow([
                emp.id, emp.name, emp.emirates_id or '', emp.phone_number or '', emp.email or '',
                emp.position or '', emp.department or '', emp.basic_salary, emp.housing_allowance or 0,
                emp.transportation_allowance or 0, emp.other_allowances or 0, total_salary,
                emp.join_date.strftime('%Y-%m-%d') if emp.join_date else '',
                emp.bank_name or '', emp.bank_account or '', status_text
            ])
        
        # Prepare response
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=employees_{status}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"}
        )
        
        return response
        
    except Exception as e:
        flash(f'Error exporting employees: {str(e)}', 'danger')
        return redirect(url_for('employee.employees'))

@employee_bp.route('/employees/check-can-delete/<int:employee_id>', methods=['GET'])
@login_required
def check_can_delete(employee_id):
    """
    Check if employee can be deleted (for UI validation)
    """
    Employee = get_employee_model()
    Salary = get_salary_model()
    
    try:
        employee = Employee.query.get_or_404(employee_id)
        
        # Check if employee has salary records
        has_salaries = Salary.query.filter_by(employee_id=employee_id).first() is not None
        
        return jsonify({
            'can_delete': employee.employment_status == 'inactive' and employee.deleted_at is None,
            'is_active': employee.employment_status == 'active',
            'is_deleted': employee.employment_status == 'deleted' or employee.deleted_at is not None,
            'employment_status': employee.employment_status,
            'has_salaries': has_salaries,
            'message': 'Employee is active and cannot be deleted' if employee.employment_status == 'active' else 
                      ('Employee is already deleted' if employee.employment_status == 'deleted' or employee.deleted_at else 
                       'Employee can be deleted')
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'can_delete': False
        }), 500

# Keep the old delete function for backward compatibility
@employee_bp.route('/employees/<int:employee_id>/deactivate', methods=['POST'])
@login_required
def deactivate_employee(employee_id):
    """
    Deactivate employee (soft delete) - maintains old functionality
    Sets employment_status to 'inactive'
    """
    Employee = get_employee_model()
    db = get_db()
    
    try:
        employee = Employee.query.get_or_404(employee_id)
        employee.employment_status = 'inactive'
        db.session.commit()
        flash(f'Employee {employee.name} has been deactivated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deactivating employee: {e}', 'danger')
    
    return redirect(url_for('employee.employees'))

@employee_bp.route('/employees/bulk-toggle-status', methods=['POST'])
@login_required
def bulk_toggle_status():
    """
    Bulk toggle employee status (activate/deactivate)
    """
    Employee = get_employee_model()
    db = get_db()
    
    try:
        # Get employee IDs and action from form
        employee_ids_str = request.form.get('employee_ids', '')
        action = request.form.get('action')  # 'activate' or 'deactivate'
        
        if not employee_ids_str or action not in ['activate', 'deactivate']:
            flash('Invalid request parameters.', 'danger')
            return redirect(url_for('employee.employees'))
        
        # Convert string to list of integers
        employee_ids = [int(id.strip()) for id in employee_ids_str.split(',') if id.strip()]
        
        # Get employees
        employees = Employee.query.filter(Employee.id.in_(employee_ids)).all()
        
        if not employees:
            flash('No employees selected.', 'warning')
            return redirect(url_for('employee.employees'))
        
        # Update each employee
        updated_count = 0
        for employee in employees:
            if action == 'activate':
                employee.employment_status = 'active'
                employee.deleted_at = None  # Clear soft delete if any
            else:  # deactivate
                employee.employment_status = 'inactive'
            updated_count += 1
        
        db.session.commit()
        
        flash(f'Successfully {action}d {updated_count} employee(s).', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error during bulk update: {str(e)}', 'danger')
    
    return redirect(url_for('employee.employees'))