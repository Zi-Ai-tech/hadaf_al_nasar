"""
Income Routes - Handles all income-related web endpoints
Integrates with IncomeService for business logic operations and Validation utilities
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app, session
from flask_login import login_required, current_user
from datetime import datetime, date
from decimal import Decimal
import traceback
import time

income_bp = Blueprint('income', __name__)

# Import services and validation utilities
from app.services.income_service import IncomeService
from app.exceptions import ValidationError, DatabaseError, BusinessRuleError
from app.utils.validation import (
    validate_income_data,
    validate_customer_data,
    Validator,
    sanitize_string,
    format_phone_number,
    parse_date,
    format_amount,
    is_valid_email,
    is_valid_phone,
    is_valid_amount
)

def get_models():
    """Lazy import for models to avoid circular imports"""
    from app.models.wps.income import Income, Service
    from app.models.core.customer import Customer
    from app.models.logistics.shipment import Shipment
    from app.models.logistics.vehicle import Vehicle
    from app.models.finance.invoice import Invoice
    from app import db
    
    return {
        'Income': Income,
        'Service': Service,
        'Customer': Customer,
        'Shipment': Shipment,
        'Vehicle': Vehicle,
        'Invoice': Invoice,
        'db': db
    }

def prepare_income_form_data(form_data, is_update=False):
    """
    Prepare and sanitize form data for income creation/update
    
    Args:
        form_data: Flask request.form or dict
        is_update: Whether this is an update operation
        
    Returns:
        dict: Sanitized and parsed form data
    """
    result = {}
    
    # Convert to dict if needed
    if hasattr(form_data, 'to_dict'):
        data = form_data.to_dict()
    else:
        data = dict(form_data)
    
    # Parse amounts with validation
    if 'amount' in data and data['amount']:
        try:
            # Clean amount string (remove commas)
            amount_str = str(data['amount']).replace(',', '').strip()
            result['amount'] = float(Decimal(amount_str))
        except (ValueError, TypeError):
            raise ValidationError("Invalid amount format. Please enter a valid number.")
    
    if 'tax_amount' in data and data['tax_amount']:
        try:
            tax_str = str(data['tax_amount']).replace(',', '').strip()
            result['tax_amount'] = float(Decimal(tax_str))
        except (ValueError, TypeError):
            raise ValidationError("Invalid tax amount format. Please enter a valid number.")
    
    # Parse dates with validation
    date_fields = ['income_date', 'due_date', 'payment_received_date', 'recurrence_end_date']
    for field in date_fields:
        if field in data and data[field]:
            date_value = data[field].strip()
            parsed_date = parse_date(date_value)
            if parsed_date:
                result[field] = parsed_date
            else:
                raise ValidationError(f"Invalid {field.replace('_', ' ')} format. Use YYYY-MM-DD.")
    
    # Parse booleans
    bool_fields = ['is_taxable', 'is_recurring']
    for field in bool_fields:
        if field in data:
            value = data.get(field)
            if isinstance(value, str):
                result[field] = value.lower() in ['true', '1', 'on', 'yes']
            else:
                result[field] = bool(value)
    
    # Parse integers (foreign keys)
    int_fields = ['customer_id', 'shipment_id', 'vehicle_id', 'service_id', 'invoice_id']
    for field in int_fields:
        if field in data and data[field]:
            try:
                result[field] = int(data[field])
            except (ValueError, TypeError):
                # If it's not a valid integer, set to None
                result[field] = None
    
    # Sanitize and copy text fields
    text_fields = [
        'description', 'category', 'subcategory', 'payment_method',
        'payment_reference', 'reference_number', 'customer_name', 'customer_contact',
        'customer_phone', 'customer_trn', 'customer_email', 'currency', 'status',
        'recurrence_pattern', 'invoice_url', 'receipt_url', 'revenue_category',
        'gl_account', 'accounting_period'
    ]
    
    for field in text_fields:
        if field in data:
            value = data.get(field)
            if value is not None:
                # Special handling for phone numbers
                if field == 'customer_phone':
                    result[field] = format_phone_number(str(value))
                else:
                    result[field] = sanitize_string(str(value), 255)
    
    # ===== CRITICAL FIX: Handle income_type separately =====
    if 'income_type' in data and data['income_type']:
        value = data.get('income_type')
        # Keep as-is (lowercase) for template compatibility
        # Will be converted to uppercase later for IncomeService
        result['income_type'] = sanitize_string(str(value), 255).lower()
    
    # Parse tags
    if 'tags' in data and data['tags']:
        tags = [tag.strip() for tag in data['tags'].split(',') if tag.strip()]
        if tags:
            result['tags'] = ','.join(tags[:10])  # Limit to 10 tags
    
    # Parse supporting docs
    if 'supporting_docs_url' in data and data['supporting_docs_url']:
        docs = [doc.strip() for doc in data['supporting_docs_url'].split(',') if doc.strip()]
        if docs:
            result['supporting_docs_url'] = ','.join(docs[:5])  # Limit to 5 docs
    
    # Set default currency if not provided
    if 'currency' not in result or not result['currency']:
        result['currency'] = 'AED'
    
    # Set default status for new incomes
    if not is_update and 'status' not in result:
        result['status'] = 'pending'
    
    # Set default exchange rate
    if 'exchange_rate' not in result:
        result['exchange_rate'] = 1.0
    
    # Calculate total amount if not provided
    if 'total_amount' not in result and 'amount' in result:
        tax = result.get('tax_amount', 0.0)
        result['total_amount'] = result['amount'] + tax
    
    return result

@income_bp.route('/incomes')
@login_required
def incomes():
    """
    Display all incomes with filtering options
    """
    try:
        models = get_models()
        Income = models['Income']
        Customer = models['Customer']
        Shipment = models['Shipment']
        Vehicle = models['Vehicle']
        Invoice = models['Invoice']
        db = models['db']
        
        # Get form data from session if available
        form_errors_raw = session.get('form_errors', {})
        
        # ===== FIX: Handle both list and dictionary errors =====
        if isinstance(form_errors_raw, list):
            form_errors = {'general': form_errors_raw}
        else:
            form_errors = form_errors_raw
        
        form_data = session.get('form_data', {})
        
        # Clear form data from session after retrieving (one-time use)
        if 'form_errors' in session:
            session.pop('form_errors', None)
        if 'form_data' in session:
            session.pop('form_data', None)
        if 'form_timestamp' in session:
            session.pop('form_timestamp', None)
        
        # Repair completed payments that were saved before their income row was created.
        # This keeps the tracking page consistent with the invoice payment ledger.
        repaired_income_count = 0
        for invoice in Invoice.query.all():
            for payment in invoice.payments:
                if payment.status == 'completed' and payment.income is None:
                    IncomeService.create_income_from_payment(
                        payment,
                        recorded_by=payment.recorded_by or current_user.id,
                    )
                    repaired_income_count += 1
        if repaired_income_count:
            db.session.commit()

        # Remove only income rows with no invoice relationship; legacy invoice income
        # may not have a payment_id and must remain visible.
        Income.query.filter(Income.invoice_id.is_(None)).delete(
            synchronize_session=False
        )
        db.session.commit()

        # Get query parameters for filtering
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        income_type = request.args.get('type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        customer_id = request.args.get('customer_id', type=int)
        
        # Display one row per invoice. Multiple partial payments can create
        # multiple income rows, but they must not appear as duplicate invoices.
        latest_income_per_invoice = db.session.query(
            db.func.max(Income.id).label('income_id')
        ).filter(
            Income.invoice_id.isnot(None)
        ).group_by(Income.invoice_id).subquery()
        query = Income.query.join(
            latest_income_per_invoice,
            Income.id == latest_income_per_invoice.c.income_id
        )
        
        # Apply filters
        if status and status != 'all':
            query = query.filter_by(status=status)
        if income_type and income_type != 'all':
            query = query.filter_by(income_type=income_type.upper())
        if start_date:
            query = query.filter(Income.income_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(Income.income_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        if customer_id:
            query = query.filter_by(customer_id=customer_id)
        
        # Order by creation date (newest first)
        incomes_paginated = query.order_by(Income.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # ===== FIXED: Get statistics the template expects =====
        today = date.today()
        
        # Get all incomes for statistics (unfiltered for overall stats)
        
        # Summary values are invoice-level, not payment-row-level.
        invoice_income_ids = db.session.query(
            Income.invoice_id
        ).filter(
            Income.invoice_id.isnot(None)
        ).distinct().subquery()
        total_amount = db.session.query(
            db.func.sum(Invoice.amount_paid)
        ).filter(Invoice.id.in_(db.select(invoice_income_ids.c.invoice_id))).scalar() or 0.0

        pending_count = query.filter(Income.status == 'pending').count()
        received_count = query.filter(Income.status == 'received').count()

        # Get overdue count (pending + due_date passed)
        overdue_count = query.filter(
            Income.status == 'pending',
            Income.due_date < today
        ).count()
        
        # Get form data for create form
        customers = Customer.query.filter_by(is_active=True).all() if Customer else []
        shipments = Shipment.query.filter_by(status='active').all() if Shipment else []
        vehicles = Vehicle.query.filter_by(status='active').all() if Vehicle else []
        
        # Get invoices for filter dropdown
        invoices = Invoice.query.filter(Invoice.status.in_(['sent', 'partial'])).all() if Invoice else []
        
        # Get income types - FIXED: Use lowercase for template compatibility
        try:
            from app.constants import IncomeType
            # Convert to lowercase for template
            income_types = {t.value.lower(): t.name.replace('_', ' ').title() for t in IncomeType}
        except ImportError:
            income_types = {
                'shipment': 'Shipment Revenue',
                'service': 'Service Revenue',
                'vehicle_rental': 'Vehicle Rental',
                'consultation': 'Consultation',
                'storage': 'Storage',
                'invoice_payment': 'Invoice Payment',
                'other': 'Other Income'
            }
        
        # Get status options for filter
        status_options = [
            ('all', 'All Statuses'),
            ('pending', 'Pending'),
            ('received', 'Received'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled')
        ]
        
        # DEBUG: Log what we're sending to template
        current_app.logger.debug(f"Total amount: {total_amount} (type: {type(total_amount)})")
        current_app.logger.debug(f"Pending count: {pending_count}")
        current_app.logger.debug(f"Received count: {received_count}")
        current_app.logger.debug(f"Overdue count: {overdue_count}")
        
        return render_template('income/incomes.html',
                             incomes=incomes_paginated,
                             # Template expects these exact variable names - pass as float, not string
                             total_amount=float(total_amount),  # Convert to float
                             pending_count=pending_count,
                             received_count=received_count,
                             overdue_count=overdue_count,
                             customers=customers,
                             shipments=shipments,
                             vehicles=vehicles,
                             invoices=invoices,
                             income_types=income_types,
                             status_options=status_options,
                             form_errors=form_errors,
                             form_data=form_data,
                             current_filters={
                                 'status': status,
                                 'type': income_type,
                                 'start_date': start_date,
                                 'end_date': end_date,
                                 'customer_id': customer_id
                             })
        
    except Exception as e:
        current_app.logger.error(f"Error in incomes route: {str(e)}\n{traceback.format_exc()}")
        flash(f'Error loading incomes: {str(e)}', 'danger')
        return render_template('income/incomes.html', 
                             incomes=[], 
                             total_amount=0.0,  # Pass as float, not string
                             pending_count=0,
                             received_count=0,
                             overdue_count=0,
                             customers=[],
                             shipments=[],
                             vehicles=[],
                             invoices=[],
                             income_types={},
                             status_options=[],
                             form_errors={},
                             form_data={},
                             current_filters={})

@income_bp.route('/incomes/from_invoice/<int:invoice_id>')
@login_required
def incomes_from_invoice(invoice_id):
    """
    Display incomes from a specific invoice
    """
    try:
        models = get_models()
        Income = models['Income']
        Invoice = models['Invoice']
        
        incomes = Income.query.filter_by(invoice_id=invoice_id).order_by(Income.created_at.desc()).all()
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            flash('Invoice not found', 'danger')
            return redirect(url_for('income.incomes'))
        
        total_amount = sum(inc.total_amount for inc in incomes)
        
        return render_template('income/incomes_from_invoice.html',
                             incomes=incomes,
                             invoice=invoice,
                             total_amount=format_amount(total_amount, 'AED'),
                             incomes_count=len(incomes))
        
    except Exception as e:
        current_app.logger.error(f"Error loading invoice incomes: {str(e)}")
        flash(f'Error loading invoice incomes: {str(e)}', 'danger')
        return redirect(url_for('income.incomes'))

@income_bp.route('/incomes/create', methods=['GET', 'POST'])
@login_required
def create_income():
    """
    Manual income entry is disabled.
    All income is created automatically from completed invoice payments.
    """
    flash(
        'Manual income recording is disabled. Income is created automatically when an invoice payment is completed.',
        'info'
    )
    return redirect(url_for('income.incomes'))

@income_bp.route('/incomes/<int:income_id>')
@login_required
def view_income(income_id):
    """
    View income details
    """
    try:
        models = get_models()
        Income = models['Income']
        
        income = Income.query.get_or_404(income_id)
        
        # Get related data
        related_entities = income.get_related_entities()
        
        # Format amounts for display
        formatted_amounts = {
            'amount': format_amount(income.amount, income.currency),
            'tax_amount': format_amount(income.tax_amount, income.currency),
            'total_amount': format_amount(income.total_amount, income.currency),
            'net_amount': format_amount(income.net_amount, income.currency)
        }
        
        # Check if overdue
        if income.is_overdue:
            flash('This income is overdue!', 'warning')
        
        return render_template('income/view_income.html', 
                             income=income,
                             formatted_amounts=formatted_amounts,
                             related_entities=related_entities)
        
    except Exception as e:
        current_app.logger.error(f"Error viewing income: {str(e)}")
        flash(f'Error loading income: {str(e)}', 'danger')
        return redirect(url_for('income.incomes'))

@income_bp.route('/incomes/<int:income_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_income(income_id):
    """
    Edit income details using IncomeService with validation
    """
    models = get_models()
    Income = models['Income']
    Customer = models['Customer']
    Shipment = models['Shipment']
    Vehicle = models['Vehicle']
    Service = models['Service']
    
    income = Income.query.get_or_404(income_id)
    
    # Check if income can be edited
    if income.status == 'received' and not current_user.has_role('admin'):
        flash('Cannot edit received income without admin privileges', 'warning')
        return redirect(url_for('income.view_income', income_id=income_id))
    
    if request.method == 'GET':
        try:
            customers = Customer.query.filter_by(is_active=True).all() if Customer else []
            shipments = Shipment.query.filter_by(status='active').all() if Shipment else []
            vehicles = Vehicle.query.filter_by(status='active').all() if Vehicle else []
            services = Service.query.filter_by(is_active=True).all() if Service else []
            
            # Get income types
            try:
                from app.constants import IncomeType
                income_types = {t.value: t.name.replace('_', ' ').title() for t in IncomeType}
            except ImportError:
                income_types = {
                    'SHIPMENT': 'Shipment',
                    'SERVICE': 'Service',
                    'VEHICLE_RENTAL': 'Vehicle Rental',
                    'CONSULTATION': 'Consultation',
                    'STORAGE': 'Storage',
                    'INVOICE_PAYMENT': 'Invoice Payment',
                    'OTHER': 'Other'
                }
            
            # Recurrence patterns
            recurrence_patterns = [
                ('', 'None'),
                ('daily', 'Daily'),
                ('weekly', 'Weekly'),
                ('monthly', 'Monthly'),
                ('quarterly', 'Quarterly'),
                ('yearly', 'Yearly')
            ]
            
            # Payment methods
            payment_methods = [
                ('', 'Select Payment Method'),
                ('cash', 'Cash'),
                ('bank_transfer', 'Bank Transfer'),
                ('card', 'Credit/Debit Card'),
                ('cheque', 'Cheque'),
                ('online', 'Online Payment'),
                ('other', 'Other')
            ]
            
            # Parse tags for display
            tags_list = income.tags.split(',') if income.tags else []
            
            return render_template('income/edit_income.html',
                                 income=income,
                                 customers=customers,
                                 shipments=shipments,
                                 vehicles=vehicles,
                                 services=services,
                                 income_types=income_types,
                                 recurrence_patterns=recurrence_patterns,
                                 payment_methods=payment_methods,
                                 tags_list=tags_list)
            
        except Exception as e:
            current_app.logger.error(f"Error loading edit form: {str(e)}")
            flash(f'Error loading form: {str(e)}', 'danger')
            return redirect(url_for('income.view_income', income_id=income_id))
    
    elif request.method == 'POST':
        try:
            # Prepare form data with validation
            form_data = prepare_income_form_data(request.form, is_update=True)
            
            # Remove fields that shouldn't be updated
            restricted_fields = ['id', 'income_number', 'created_at', 'recorded_by']
            for field in restricted_fields:
                form_data.pop(field, None)
            
            # Validate income data using validation utility
            is_valid, errors = validate_income_data(form_data, is_update=True)
            
            if not is_valid:
                for error in errors:
                    flash(error, 'danger')
                return redirect(request.url)
            
            # Update income using service
            income = IncomeService.update_income(
                income_id=income_id,
                update_data=form_data,
                updated_by=current_user.id
            )
            
            flash('Income updated successfully!', 'success')
            return redirect(url_for('income.view_income', income_id=income.id))
            
        except ValidationError as e:
            flash(f'Validation error: {str(e)}', 'danger')
            return redirect(request.url)
        except BusinessRuleError as e:
            flash(f'Business rule error: {str(e)}', 'warning')
            return redirect(request.url)
        except DatabaseError as e:
            flash(f'Database error: {str(e)}', 'danger')
            return redirect(request.url)
        except Exception as e:
            current_app.logger.error(f"Error updating income: {str(e)}\n{traceback.format_exc()}")
            flash(f'Error updating income: {str(e)}', 'danger')
            return redirect(request.url)

@income_bp.route('/incomes/<int:income_id>/delete', methods=['POST'])
@login_required
def delete_income(income_id):
    """
    Soft delete income (if model supports it)
    """
    try:
        models = get_models()
        Income = models['Income']
        db = models['db']
        
        income = Income.query.get_or_404(income_id)
        
        # Check if income can be deleted
        if income.status == 'received':
            flash('Cannot delete received income', 'warning')
            return redirect(url_for('income.view_income', income_id=income_id))
        
        # Soft delete if supported
        if hasattr(income, 'is_deleted'):
            income.is_deleted = True
            income.deleted_at = datetime.utcnow()
            income.deleted_by = current_user.id
            db.session.commit()
            flash('Income archived successfully!', 'success')
        else:
            # Hard delete with confirmation
            db.session.delete(income)
            db.session.commit()
            flash('Income deleted permanently!', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting income: {str(e)}")
        flash(f'Error deleting income: {str(e)}', 'danger')
    
    return redirect(url_for('income.incomes'))

# ==================== API ENDPOINTS ====================

@income_bp.route('/api/incomes/<int:income_id>/mark_received', methods=['POST'])
@login_required
def mark_income_received(income_id):
    """
    API endpoint to mark income as received
    """
    try:
        data = request.get_json() or {}
        
        # Parse payment data
        payment_date = None
        if data.get('payment_date'):
            try:
                payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid payment date format. Use YYYY-MM-DD'
                }), 400
        
        # Mark income as received using service
        income = IncomeService.mark_income_as_received(
            income_id=income_id,
            payment_date=payment_date,
            payment_method=data.get('payment_method'),
            payment_reference=data.get('payment_reference'),
            recorded_by=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': 'Income marked as received',
            'income': income.to_dict()
        })
        
    except ValidationError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except BusinessRuleError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except DatabaseError as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Error marking income received: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@income_bp.route('/api/incomes/summary', methods=['GET'])
@login_required
def income_summary():
    """
    Get income summary for dashboard (API endpoint)
    """
    try:
        # Parse date parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Default to current month if not specified
        today = date.today()
        
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid start date format. Use YYYY-MM-DD'
                }), 400
        else:
            start_date = date(today.year, today.month, 1)  # First day of current month
        
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid end date format. Use YYYY-MM-DD'
                }), 400
        else:
            end_date = today
        
        # Validate date range
        if start_date > end_date:
            return jsonify({
                'success': False,
                'message': 'Start date cannot be after end date'
            }), 400
        
        # Build filters
        filters = {}
        customer_id = request.args.get('customer_id', type=int)
        income_type = request.args.get('income_type')
        status = request.args.get('status')
        
        if customer_id:
            filters['customer_id'] = customer_id
        if income_type and income_type != 'all':
            filters['income_type'] = income_type
        if status and status != 'all':
            filters['status'] = status
        
        # Get summary using service
        summary = IncomeService.get_income_summary(
            start_date=start_date,
            end_date=end_date,
            filters=filters
        )
        
        # Get pending and overdue incomes
        models = get_models()
        Income = models['Income']
        
        pending_incomes = Income.query.filter_by(status='pending').count()
        overdue_incomes = Income.query.filter(
            Income.status.in_(['pending', 'overdue']),
            Income.due_date < today
        ).count()
        
        # Add counts to summary
        summary['overview']['pending_count'] = pending_incomes
        summary['overview']['overdue_count'] = overdue_incomes
        
        return jsonify({
            'success': True,
            'summary': summary,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in income summary API: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@income_bp.route('/api/incomes/forecast', methods=['GET'])
@login_required
def income_forecast():
    """
    Get income forecast (API endpoint)
    """
    try:
        # Parse parameters
        months = request.args.get('months', 6, type=int)
        include_recurring = request.args.get('include_recurring', 'true').lower() == 'true'
        
        # Validate months parameter
        if months < 1 or months > 36:
            return jsonify({
                'success': False,
                'message': 'Months must be between 1 and 36'
            }), 400
        
        # Calculate dates
        today = date.today()
        start_date = today
        
        # Calculate end date (today + X months)
        if today.month + months > 12:
            end_date = date(today.year + 1, today.month + months - 12, today.day)
        else:
            end_date = date(today.year, today.month + months, today.day)
        
        # Get forecast using service
        forecast = IncomeService.get_income_forecast(
            start_date=start_date,
            end_date=end_date,
            include_recurring=include_recurring
        )
        
        return jsonify({
            'success': True,
            'forecast': forecast
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in income forecast API: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@income_bp.route('/api/incomes/<int:income_id>', methods=['GET'])
@login_required
def get_income_api(income_id):
    """
    Get income details (API endpoint)
    """
    try:
        models = get_models()
        Income = models['Income']
        
        income = Income.query.get_or_404(income_id)
        
        return jsonify({
            'success': True,
            'income': income.to_dict(include_related=True)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting income API: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@income_bp.route('/api/incomes/batch/mark_received', methods=['POST'])
@login_required
def batch_mark_received():
    """
    Batch mark multiple incomes as received
    """
    try:
        data = request.get_json()
        
        if not data or 'income_ids' not in data:
            return jsonify({
                'success': False,
                'message': 'No income IDs provided'
            }), 400
        
        income_ids = data['income_ids']
        if not isinstance(income_ids, list) or len(income_ids) == 0:
            return jsonify({
                'success': False,
                'message': 'Invalid income IDs format'
            }), 400
        
        # Process each income
        results = []
        for income_id in income_ids:
            try:
                income = IncomeService.mark_income_as_received(
                    income_id=income_id,
                    payment_method=data.get('payment_method'),
                    payment_reference=data.get('payment_reference'),
                    recorded_by=current_user.id
                )
                results.append({
                    'income_id': income_id,
                    'success': True,
                    'income_number': income.income_number,
                    'message': 'Marked as received'
                })
            except ValidationError as e:
                results.append({
                    'income_id': income_id,
                    'success': False,
                    'error': str(e),
                    'message': 'Validation error'
                })
            except BusinessRuleError as e:
                results.append({
                    'income_id': income_id,
                    'success': False,
                    'error': str(e),
                    'message': 'Business rule error'
                })
            except Exception as e:
                results.append({
                    'income_id': income_id,
                    'success': False,
                    'error': str(e),
                    'message': 'Internal error'
                })
        
        # Count successes
        success_count = sum(1 for r in results if r['success'])
        
        return jsonify({
            'success': True,
            'message': f'Processed {len(results)} incomes, {success_count} successful',
            'results': results
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in batch mark received: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@income_bp.route('/api/incomes/reconcile', methods=['POST'])
@login_required
def reconcile_incomes():
    """
    Reconcile incomes with invoices (Admin only)
    """
    try:
        # Check if user is admin
        if not current_user.has_role('admin'):
            return jsonify({
                'success': False,
                'message': 'Admin privileges required'
            }), 403
        
        # Run reconciliation
        report = IncomeService.reconcile_incomes_with_invoices()
        
        return jsonify({
            'success': True,
            'message': 'Reconciliation completed',
            'report': report
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in reconciliation: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@income_bp.route('/api/incomes/from_invoice/<int:invoice_id>', methods=['POST'])
@login_required
def create_income_from_invoice_api(invoice_id):
    """
    Create income record from invoice (API endpoint)
    """
    try:
        income = IncomeService.create_income_from_invoice(
            invoice_id=invoice_id,
            recorded_by=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': 'Income created from invoice',
            'income': income.to_dict()
        })
        
    except ValidationError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except BusinessRuleError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except DatabaseError as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Error creating income from invoice: {str(e)}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@income_bp.route('/api/incomes/search', methods=['GET'])
@login_required
def search_incomes():
    """
    Search incomes by various criteria
    """
    try:
        models = get_models()
        Income = models['Income']
        
        query = Income.query
        
        # Apply search filters
        if request.args.get('q'):
            search_term = f"%{request.args.get('q')}%"
            query = query.filter(
                (Income.description.ilike(search_term)) |
                (Income.income_number.ilike(search_term)) |
                (Income.customer_name.ilike(search_term)) |
                (Income.reference_number.ilike(search_term))
            )
        
        if request.args.get('status'):
            query = query.filter_by(status=request.args.get('status'))
        
        if request.args.get('income_type'):
            query = query.filter_by(income_type=request.args.get('income_type'))
        
        if request.args.get('customer_id'):
            query = query.filter_by(customer_id=request.args.get('customer_id', type=int))
        
        # Date range
        if request.args.get('start_date'):
            try:
                start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
                query = query.filter(Income.income_date >= start_date)
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid start date format'
                }), 400
        
        if request.args.get('end_date'):
            try:
                end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
                query = query.filter(Income.income_date <= end_date)
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid end date format'
                }), 400
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        incomes = query.order_by(Income.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'incomes': [income.to_dict() for income in incomes.items],
            'total': incomes.total,
            'pages': incomes.pages,
            'current_page': incomes.page
        })
        
    except Exception as e:
        current_app.logger.error(f"Error searching incomes: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ==================== VALIDATION ENDPOINTS ====================

@income_bp.route('/api/incomes/validate', methods=['POST'])
@login_required
def validate_income_api():
    """
    Validate income data without creating it
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Validate income data
        is_valid, errors = validate_income_data(data, is_update=False)
        
        # Use Validator class for detailed validation
        validator_result = Validator.validate_financial_transaction(data)
        
        return jsonify({
            'success': True,
            'validation': {
                'is_valid': is_valid,
                'errors': errors,
                'has_warnings': validator_result['has_warnings'],
                'warnings': validator_result['warnings']
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error validating income: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Validation error'
        }), 500

@income_bp.route('/api/incomes/batch/validate', methods=['POST'])
@login_required
def validate_batch_incomes_api():
    """
    Validate batch of incomes
    """
    try:
        data = request.get_json()
        
        if not data or 'incomes' not in data:
            return jsonify({
                'success': False,
                'message': 'No incomes data provided'
            }), 400
        
        incomes_data = data['incomes']
        
        if not isinstance(incomes_data, list):
            return jsonify({
                'success': False,
                'message': 'Incomes data must be a list'
            }), 400
        
        # Validate each income
        validation_results = []
        all_valid = True
        
        for idx, income_data in enumerate(incomes_data):
            is_valid, errors = validate_income_data(income_data, is_update=False)
            
            validation_results.append({
                'index': idx,
                'is_valid': is_valid,
                'errors': errors,
                'description': income_data.get('description', f'Income {idx + 1}')
            })
            
            if not is_valid:
                all_valid = False
        
        return jsonify({
            'success': True,
            'all_valid': all_valid,
            'results': validation_results,
            'summary': {
                'total': len(incomes_data),
                'valid': sum(1 for r in validation_results if r['is_valid']),
                'invalid': sum(1 for r in validation_results if not r['is_valid'])
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error validating batch incomes: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Validation error'
        }), 500

# ==================== HELPER ROUTES ====================

@income_bp.route('/incomes/export', methods=['GET'])
@login_required
def export_incomes():
    """
    Export incomes to CSV/Excel
    """
    try:
        models = get_models()
        Income = models['Income']
        
        # Get filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status = request.args.get('status')
        income_type = request.args.get('type')
        customer_id = request.args.get('customer_id', type=int)
        
        query = Income.query
        
        if start_date:
            query = query.filter(Income.income_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(Income.income_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        if status and status != 'all':
            query = query.filter_by(status=status)
        if income_type and income_type != 'all':
            query = query.filter_by(income_type=income_type.upper())
        if customer_id:
            query = query.filter_by(customer_id=customer_id)
        
        incomes = query.order_by(Income.income_date.desc()).all()
        
        # Return JSON with export data
        return jsonify({
            'success': True,
            'message': f'Export ready for {len(incomes)} incomes',
            'count': len(incomes),
            'format': request.args.get('format', 'csv'),
            'data': [income.to_dict() for income in incomes]
        })
        
    except Exception as e:
        current_app.logger.error(f"Error exporting incomes: {str(e)}")
        flash(f'Error exporting incomes: {str(e)}', 'danger')
        return redirect(url_for('income.incomes'))

@income_bp.route('/incomes/generate_recurring', methods=['POST'])
@login_required
def generate_recurring_incomes():
    """
    Generate recurring incomes (Admin/Manual trigger)
    """
    try:
        # Check if user has permission
        if not current_user.has_role('admin') and not current_user.has_role('finance'):
            flash('Permission denied', 'danger')
            return redirect(url_for('income.incomes'))
        
        # Generate recurring incomes
        generated = IncomeService.generate_recurring_incomes()
        
        flash(f'Generated {len(generated)} recurring incomes', 'success')
        return redirect(url_for('income.incomes'))
        
    except Exception as e:
        current_app.logger.error(f"Error generating recurring incomes: {str(e)}")
        flash(f'Error generating recurring incomes: {str(e)}', 'danger')
        return redirect(url_for('income.incomes'))

@income_bp.route('/api/incomes/quick_validate', methods=['POST'])
@login_required
def quick_validate_api():
    """
    Quick validation for specific fields
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        results = {}
        
        # Validate email if present
        if 'email' in data:
            results['email'] = is_valid_email(data['email'])
        
        # Validate phone if present
        if 'phone' in data:
            results['phone'] = is_valid_phone(data['phone'])
        
        # Validate amount if present
        if 'amount' in data:
            results['amount'] = is_valid_amount(data['amount'])
        
        # Validate date if present
        if 'date' in data:
            from app.utils.validation import validate_date_string
            results['date'] = validate_date_string(data['date'])
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in quick validation: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@income_bp.route('/api/incomes/stats', methods=['GET'])
@login_required
def income_stats():
    """
    Get real-time income statistics
    """
    try:
        models = get_models()
        Income = models['Income']
        
        today = date.today()
        
        # Today's income
        today_income = Income.query.filter(
            Income.income_date == today,
            Income.status == 'received'
        ).all()
        today_total = sum(inc.total_amount for inc in today_income)
        
        # This month's income
        start_of_month = date(today.year, today.month, 1)
        month_income = Income.query.filter(
            Income.income_date >= start_of_month,
            Income.income_date <= today,
            Income.status == 'received'
        ).all()
        month_total = sum(inc.total_amount for inc in month_income)
        
        # Pending income
        pending_income = Income.query.filter_by(status='pending').all()
        pending_total = sum(inc.total_amount for inc in pending_income)
        pending_count = len(pending_income)
        
        # Overdue income
        overdue_income = Income.query.filter(
            Income.status.in_(['pending', 'overdue']),
            Income.due_date < today
        ).all()
        overdue_total = sum(inc.total_amount for inc in overdue_income)
        overdue_count = len(overdue_income)
        
        # Recent incomes
        recent_incomes = Income.query.order_by(Income.created_at.desc()).limit(5).all()
        
        return jsonify({
            'success': True,
            'stats': {
                'today_total': today_total,
                'month_total': month_total,
                'pending_total': pending_total,
                'pending_count': pending_count,
                'overdue_total': overdue_total,
                'overdue_count': overdue_count,
                'recent_incomes': [inc.to_dict() for inc in recent_incomes]
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting income stats: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500