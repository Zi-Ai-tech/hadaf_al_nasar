from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import traceback
from app.models.wps.expense import Expense
from app.models.wps.project import Project
from app.models.core.user import User

from sqlalchemy.exc import SQLAlchemyError

expense_bp = Blueprint('expense', __name__)

def get_expense_model():
    """Lazy import for Expense model"""
    from app.models.wps.expense import Expense
    return Expense

def get_db():
    """Lazy import for db"""
    from app import db
    return db

def get_project_model():
    """Lazy import for Project model"""
    from app.models.wps.project import Project
    return Project

def get_employee_model():
    """Lazy import for Employee model"""
    from app.models.wps.employee import Employee
    return Employee

def get_vehicle_model():
    """Lazy import for Vehicle model"""
    from app.models.logistics.vehicle import Vehicle
    return Vehicle

@expense_bp.route('/expenses')
@login_required
def expenses():
    """
    Display all expenses with filtering options
    """
    from app.constants import ExpenseType  # Add this import
    
    Expense = get_expense_model()
    Project = get_project_model()
    Employee = get_employee_model()
    Vehicle = get_vehicle_model()
    
    try:
        # Get query parameters for filtering
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        expense_type = request.args.get('type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = Expense.query
        
        # Apply filters
        if status:
            query = query.filter_by(status=status)
        if expense_type:
            query = query.filter_by(expense_type=expense_type)
        if start_date:
            query = query.filter(Expense.expense_date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            query = query.filter(Expense.expense_date <= datetime.strptime(end_date, '%Y-%m-%d'))
        
        # Order by creation date (newest first)
        expenses_paginated = query.order_by(Expense.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Get summary statistics
        total_amount = sum(exp.total_amount for exp in expenses_paginated.items)
        pending_count = Expense.query.filter_by(status='pending').count()
        approved_count = Expense.query.filter_by(status='approved').count()
        
        # Calculate overdue count (expenses with due_date in the past and status not paid)
        from datetime import datetime
        overdue_count = Expense.query.filter(
            Expense.due_date < datetime.now().date(),
            Expense.status.in_(['pending', 'approved'])
        ).count()
        
        # Get data for dropdowns
        projects = Project.query.filter_by(status='active').all() if Project else []
        employees = Employee.query.filter_by(employment_status='active').all() if Employee else []
        vehicles = Vehicle.query.filter_by(status='active').all() if Vehicle else []
        
        # Get expense types enum
        expense_types = {item.value: item.value.replace('_', ' ').title() for item in ExpenseType}
        
        return render_template('expense/expenses.html', 
                             expenses=expenses_paginated,
                             total_amount=total_amount,
                             pending_count=pending_count,
                             approved_count=approved_count,
                             overdue_count=overdue_count,
                             projects=projects,
                             employees=employees,
                             vehicles=vehicles,
                             expense_types=expense_types)
        
    except Exception as e:
        flash(f'Error loading expenses: {str(e)}', 'danger')
        return render_template('expense/expenses.html', 
                             expenses=[],
                             total_amount=0,
                             pending_count=0,
                             approved_count=0,
                             overdue_count=0,
                             projects=[],
                             employees=[],
                             vehicles=[],
                             expense_types={})

@expense_bp.route('/expenses/create', methods=['GET', 'POST'])
@login_required
def create_expense():
    """
    Create new expense
    """
    Expense = get_expense_model()
    Project = get_project_model()
    Employee = get_employee_model()
    Vehicle = get_vehicle_model()
    db = get_db()
    
    if request.method == 'GET':
        # The existing expenses page contains the complete creation form.
        # Reuse it instead of referencing a nonexistent standalone template.
        return redirect(url_for('expense.expenses'))
    
    elif request.method == 'POST':
        try:
            # Validate required fields
            required_fields = ['description', 'amount', 'expense_type', 
                             'expense_date', 'project_id']
            
            for field in required_fields:
                if not request.form.get(field):
                    flash(f'{field.replace("_", " ").title()} is required', 'danger')
                    return redirect(request.url)
            
            # Parse amount
            amount = float(request.form.get('amount', 0))
            if amount <= 0:
                flash('Amount must be greater than 0', 'danger')
                return redirect(request.url)
            
            # Parse tax amount
            tax_amount = float(request.form.get('tax_amount', 0))
            
            # Parse dates
            expense_date = datetime.strptime(request.form.get('expense_date'), '%Y-%m-%d').date()
            
            due_date = None
            if request.form.get('due_date'):
                due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
            
            payment_date = None
            if request.form.get('payment_date'):
                payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
            
            # Build expense data
            expense_data = {
                'description': request.form.get('description'),
                'expense_type': request.form.get('expense_type'),
                'amount': amount,
                'tax_amount': tax_amount,
                'total_amount': amount + tax_amount,  # Calculate total
                'currency': request.form.get('currency', 'AED'),
                'expense_date': expense_date,
                'due_date': due_date,
                'payment_date': payment_date,
                'category': request.form.get('category'),
                'subcategory': request.form.get('subcategory'),
                'payment_method': request.form.get('payment_method'),
                'payment_reference': request.form.get('payment_reference'),
                'reference_number': request.form.get('reference_number'),
                'vendor_name': request.form.get('vendor_name'),
                'vendor_contact': request.form.get('vendor_contact'),
                'vendor_phone': request.form.get('vendor_phone'),
                'vendor_trn': request.form.get('vendor_trn'),
                'status': request.form.get('status', 'pending'),
                'requires_approval': request.form.get('requires_approval') == 'true',
                'is_recurring': request.form.get('is_recurring') == 'true',
                'recurrence_pattern': request.form.get('recurrence_pattern'),
                'receipt_url': request.form.get('receipt_url'),
                'invoice_url': request.form.get('invoice_url'),
                'budget_category': request.form.get('budget_category'),
                'gl_account': request.form.get('gl_account'),
                
                # Foreign keys
                'project_id': int(request.form.get('project_id')),
                'recorded_by': current_user.id,
            }
            
            # Optional foreign keys
            if request.form.get('employee_id'):
                expense_data['employee_id'] = int(request.form.get('employee_id'))
            
            if request.form.get('vehicle_id'):
                expense_data['vehicle_id'] = int(request.form.get('vehicle_id'))
            
            if request.form.get('approved_by'):
                expense_data['approved_by'] = int(request.form.get('approved_by'))
                expense_data['approved_date'] = datetime.utcnow()
            
            # Handle recurrence end date
            if request.form.get('recurrence_end_date'):
                expense_data['recurrence_end_date'] = datetime.strptime(
                    request.form.get('recurrence_end_date'), '%Y-%m-%d'
                ).date()
            
            # Handle tags
            tags = request.form.get('tags')
            if tags:
                expense_data['tags'] = ','.join(tag.strip() for tag in tags.split(',') if tag.strip())
            
            # Create expense using model
            expense = Expense(**expense_data)
            
            db.session.add(expense)
            db.session.commit()
            
            flash(f'Expense {expense.expense_number} created successfully!', 'success')
            return redirect(url_for('expense.expenses'))
            
        except ValueError as e:
            db.session.rollback()
            flash(f'Invalid data format: {str(e)}', 'danger')
            return redirect(request.url)
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating expense: {str(e)}', 'danger')
            return redirect(request.url)

@expense_bp.route('/expenses/<int:expense_id>')
@login_required
def view_expense(expense_id):
    """
    View expense details
    """
    Expense = get_expense_model()
    
    try:
        expense = Expense.query.get_or_404(expense_id)
        # Convert to dict with related data
        expense_data = expense.to_dict(include_related=True)
        return render_template('expense/view_expense.html', expense=expense, expense_data=expense_data)
    except Exception as e:
        flash(f'Error loading expense: {str(e)}', 'danger')
        return redirect(url_for('expense.expenses'))

@expense_bp.route('/expenses/<int:expense_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    """
    Edit expense details
    """
    Expense = get_expense_model()
    Project = get_project_model()
    Employee = get_employee_model()
    Vehicle = get_vehicle_model()
    db = get_db()
    
    expense = Expense.query.get_or_404(expense_id)
    
    if request.method == 'GET':
        try:
            from app.constants import ExpenseType

            projects = Project.query.filter_by(status='active').all()
            employees = Employee.query.filter(
                Employee.employment_status == 'active',
                Employee.deleted_at.is_(None),
            ).all()
            vehicles = Vehicle.query.filter_by(status='active').all()
            
            return render_template('expense/edit_expense.html',
                                 expense=expense,
                                 projects=projects,
                                 employees=employees,
                                 vehicles=vehicles,
                                 expense_types=list(ExpenseType))
        except Exception as e:
            flash(f'Error loading form data: {str(e)}', 'danger')
            return redirect(url_for('expense.view_expense', expense_id=expense_id))
    
    elif request.method == 'POST':
        try:
            # Update basic fields
            expense.description = request.form.get('description', expense.description)
            
            # Update amount and recalculate
            if 'amount' in request.form:
                amount = float(request.form.get('amount'))
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                expense.amount = amount
            
            if 'tax_amount' in request.form:
                expense.tax_amount = float(request.form.get('tax_amount', 0))
            
            # Recalculate total
            expense.calculate_totals()
            
            # Update other fields
            expense.expense_type = request.form.get('expense_type', expense.expense_type)
            expense.category = request.form.get('category', expense.category)
            expense.subcategory = request.form.get('subcategory', expense.subcategory)
            expense.payment_method = request.form.get('payment_method', expense.payment_method)
            expense.payment_reference = request.form.get('payment_reference', expense.payment_reference)
            expense.vendor_name = request.form.get('vendor_name', expense.vendor_name)
            expense.vendor_contact = request.form.get('vendor_contact', expense.vendor_contact)
            expense.vendor_phone = request.form.get('vendor_phone', expense.vendor_phone)
            expense.vendor_trn = request.form.get('vendor_trn', expense.vendor_trn)
            expense.status = request.form.get('status', expense.status)
            expense.reference_number = request.form.get('reference_number', expense.reference_number)
            expense.budget_category = request.form.get('budget_category', expense.budget_category)
            expense.gl_account = request.form.get('gl_account', expense.gl_account)
            
            # Update dates
            if request.form.get('expense_date'):
                expense.expense_date = datetime.strptime(request.form.get('expense_date'), '%Y-%m-%d').date()
            
            if request.form.get('due_date'):
                expense.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
            
            if request.form.get('payment_date'):
                expense.payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
            
            # Update foreign keys
            if request.form.get('project_id'):
                expense.project_id = int(request.form.get('project_id'))
            
            if request.form.get('employee_id'):
                expense.employee_id = int(request.form.get('employee_id'))
            
            if request.form.get('vehicle_id'):
                expense.vehicle_id = int(request.form.get('vehicle_id'))
            
            # Update tags
            if 'tags' in request.form:
                tags = request.form.get('tags')
                if tags:
                    expense.tags = ','.join(tag.strip() for tag in tags.split(',') if tag.strip())
                else:
                    expense.tags = None
            
            db.session.commit()
            flash('Expense updated successfully!', 'success')
            return redirect(url_for('expense.view_expense', expense_id=expense.id))
            
        except ValueError as e:
            db.session.rollback()
            flash(f'Invalid data: {str(e)}', 'danger')
            return redirect(request.url)
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating expense: {str(e)}', 'danger')
            return redirect(request.url)

@expense_bp.route('/expenses/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_expense(expense_id):
    """
    Delete expense (soft delete if model supports it)
    """
    Expense = get_expense_model()
    db = get_db()
    
    try:
        expense = Expense.query.get_or_404(expense_id)
        
        # Check if expense can be deleted
        if expense.status == 'paid':
            flash('Cannot delete paid expenses', 'warning')
            return redirect(url_for('expense.view_expense', expense_id=expense_id))
        
        # If model has is_deleted field, do soft delete
        if hasattr(Expense, 'is_deleted'):
            expense.is_deleted = True
            db.session.commit()
            flash('Expense archived successfully!', 'success')
        else:
            # Hard delete
            db.session.delete(expense)
            db.session.commit()
            flash('Expense deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting expense: {str(e)}', 'danger')
    
    return redirect(url_for('expense.expenses'))

# Additional API endpoints

@expense_bp.route('/api/expenses/<int:expense_id>/approve', methods=['POST'])
@login_required
def approve_expense(expense_id):
    """
    Approve expense
    """
    Expense = get_expense_model()
    db = get_db()
    
    try:
        expense = Expense.query.get_or_404(expense_id)
        
        if expense.status != 'pending':
            return jsonify({
                'success': False,
                'message': f'Expense is {expense.status}, cannot approve'
            }), 400
        
        # Use model's approve method
        notes = request.json.get('notes') if request.is_json else request.form.get('notes')
        expense.approve(approved_by_user_id=current_user.id, notes=notes)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Expense approved successfully',
            'expense': expense.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@expense_bp.route('/api/expenses/<int:expense_id>/mark_paid', methods=['POST'])
@login_required
def mark_expense_paid(expense_id):
    """
    Mark expense as paid
    """
    Expense = get_expense_model()
    db = get_db()
    
    try:
        expense = Expense.query.get_or_404(expense_id)
        
        if expense.status not in ['approved', 'pending']:
            return jsonify({
                'success': False,
                'message': f'Expense must be approved or pending to mark as paid'
            }), 400
        
        # Use model's mark_as_paid method
        payment_date = None
        if request.is_json and request.json.get('payment_date'):
            payment_date = datetime.strptime(request.json.get('payment_date'), '%Y-%m-%d').date()
        
        payment_method = None
        if request.is_json:
            payment_method = request.json.get('payment_method')
        
        payment_reference = None
        if request.is_json:
            payment_reference = request.json.get('payment_reference')
        
        expense.mark_as_paid(payment_date=payment_date, 
                           payment_method=payment_method,
                           payment_reference=payment_reference)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Expense marked as paid',
            'expense': expense.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@expense_bp.route('/api/expenses/summary')
@login_required
def expense_summary():
    """
    Get expense summary for dashboard
    """
    Expense = get_expense_model()
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            # Default to start of current month
            from datetime import date
            today = date.today()
            start_date = date(today.year, today.month, 1)
        
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            # Default to today
            from datetime import date
            end_date = date.today()
        
        # Get totals
        total_expenses = Expense.get_total_expenses(start_date, end_date)
        pending_expenses = Expense.get_total_expenses(start_date, end_date, status='pending')
        approved_expenses = Expense.get_total_expenses(start_date, end_date, status='approved')
        paid_expenses = Expense.get_total_expenses(start_date, end_date, status='paid')
        
        # Get summary by type
        summary_by_type = Expense.get_expense_summary(start_date, end_date, group_by='expense_type')
        
        # Get pending approvals
        pending_approvals = Expense.get_pending_approval()
        
        # Get overdue expenses
        overdue_expenses = Expense.get_overdue_expenses()
        
        return jsonify({
            'success': True,
            'summary': {
                'total': total_expenses,
                'pending': pending_expenses,
                'approved': approved_expenses,
                'paid': paid_expenses,
                'by_type': summary_by_type
            },
            'pending_approvals_count': len(pending_approvals),
            'overdue_expenses_count': len(overdue_expenses),
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
