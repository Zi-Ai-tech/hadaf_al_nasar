from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file, Response
from flask_login import login_required, current_user
from sqlalchemy import text
import traceback
import io
import os
import subprocess
import tempfile
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch
from datetime import datetime

def generate_invoice_number():
    """Generate invoice number in HNT-YYY-MMM-01 format"""
    from datetime import datetime
    from sqlalchemy import text
    from app import db
    
    now = datetime.utcnow()
    company_short = "HNT"
    year_short = str(now.year)[-3:]
    month_short = now.strftime('%b').upper()
    
    base_number = f"{company_short}-{year_short}-{month_short}"
    
    # Find the highest sequence number for this month and year
    result = db.session.execute(
        text("""
            SELECT invoice_number 
            FROM invoice 
            WHERE invoice_number LIKE :pattern 
            ORDER BY invoice_number DESC 
            LIMIT 1
        """),
        {'pattern': f'{base_number}-%'}
    ).fetchone()
    
    if result:
        last_number = result[0]
        try:
            last_seq = int(last_number.split('-')[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1
    
    return f"{base_number}-{next_seq:02d}"

invoices_bp = Blueprint('invoices', __name__)

@invoices_bp.route('/invoices', methods=['GET'])
@login_required
def list_invoices():
    """
    Display invoices with optional filtering
    """
    from app import db
    from app.models.finance.invoice import Invoice
    
    try:
        Invoice.sync_overdue_statuses()
        invoice_type = request.args.get('type')
        status_filter = request.args.get('status')
        valid_statuses = {'draft', 'pending', 'sent', 'partial', 'paid', 'overdue', 'cancelled', 'outstanding'}
        status_filter = status_filter if status_filter in valid_statuses else None
        
        # Build query with customer join to get company_name
        filters = []
        params = {}
        if invoice_type:
            filters.append('i.invoice_type = :invoice_type')
            params['invoice_type'] = invoice_type
        if status_filter:
            if status_filter == 'outstanding':
                filters.append("i.status IN ('pending', 'sent', 'partial', 'overdue')")
            else:
                filters.append('i.status = :status')
                params['status'] = status_filter

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ''
        result = db.session.execute(
            text(f"""
                SELECT i.*, c.company_name
                FROM invoice i
                LEFT JOIN customer c ON i.customer_id = c.id
                {where_clause}
            """),
            params
        )
        
        # Convert to list of dictionaries with proper structure
        invoices_list = []
        for row in result:
            invoice_dict = {}
            for key, value in row._mapping.items():
                if hasattr(value, 'isoformat'):
                    invoice_dict[key] = value
                else:
                    invoice_dict[key] = value
            invoices_list.append(invoice_dict)
        
        return render_template('accounts/invoices.html', invoices=invoices_list)
        
    except Exception as e:
        print(f"[Invoices Error] {e}")
        traceback.print_exc()
        flash('Error loading invoices', 'danger')
        return render_template('accounts/invoices.html', invoices=[])

@invoices_bp.route('/invoices/create', methods=['GET', 'POST'])
@login_required
def create_invoice():
    """
    Create new invoice with items
    """
    from app import db
    
    if request.method == 'GET':
        return show_create_invoice_form()
    
    return handle_invoice_creation(request)

def show_create_invoice_form():
    """
    Show invoice creation form
    """
    from app import db
    
    try:
        # Get active customers
        issuer_company_name = os.environ.get(
            'INVOICE_ISSUER_COMPANY_NAME', 'Hadaf Al Nasar Logistics'
        )
        result = db.session.execute(text("""
            SELECT id, company_name
            FROM customer
            WHERE is_active = true
              AND LOWER(company_name) <> LOWER(:issuer_company_name)
        """), {'issuer_company_name': issuer_company_name})
        customers = []
        for row in result:
            customers.append({
                'id': row.id,
                'company_name': row.company_name
            })
        
        # Generate suggested invoice number using the proper format
        suggested_number = generate_invoice_number()
        
        return render_template(
            'accounts/create_invoice_with_items.html', 
            customers=customers, 
            suggested_invoice_number=suggested_number
        )
    except Exception as e:
        print(f"Error loading create invoice form: {e}")
        flash('Error loading form', 'danger')
        return redirect(url_for('invoices.list_invoices'))

def handle_invoice_creation(request):
    """
    Handle invoice creation from form data with HNT format invoice numbers
    """
    from app import db
    from sqlalchemy import text
    
    try:
        invoice_data = extract_invoice_data(request.form)
        items_data = extract_items_data(request.form)
        
        print(f"=== DEBUG CREATE: invoice_data: {invoice_data} ===")
        print(f"=== DEBUG CREATE: items_data: {items_data} ===")
        
        validate_invoice_data(invoice_data, items_data)

        issuer_company_name = os.environ.get(
            'INVOICE_ISSUER_COMPANY_NAME', 'Hadaf Al Nasar Logistics'
        )
        issuer_customer = db.session.execute(text("""
            SELECT company_name
            FROM customer
            WHERE id = :customer_id
        """), {'customer_id': invoice_data['customer_id']}).scalar()
        if issuer_customer and issuer_customer.casefold() == issuer_company_name.casefold():
            raise ValueError('An invoice cannot be issued to Hadaf Al Nasar Logistics itself.')
        
        # Generate a unique invoice number in HNT-YYY-MMM-01 format
        if not invoice_data.get('invoice_number'):
            from app.models.finance.invoice import Invoice
            # Create a temporary invoice instance to use its method
            temp_invoice = Invoice()
            invoice_data['invoice_number'] = temp_invoice.generate_invoice_number()
        else:
            # If invoice number was provided, check if it's unique
            result = db.session.execute(
                text("SELECT id FROM invoice WHERE invoice_number = :invoice_number"),
                {'invoice_number': invoice_data['invoice_number']}
            ).fetchone()
            if result:
                # Generate a new one if the provided one exists
                from app.models.finance.invoice import Invoice
                temp_invoice = Invoice()
                invoice_data['invoice_number'] = temp_invoice.generate_invoice_number()
        
        print(f"=== DEBUG CREATE: Using invoice number: {invoice_data['invoice_number']} ===")
        
        # First, check what columns actually exist in the invoice table
        columns_result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'invoice' 
            ORDER BY ordinal_position
        """)).fetchall()
        
        existing_columns = [row[0] for row in columns_result]
        print(f"=== DEBUG: Existing columns: {existing_columns} ===")
        
        # Build dynamic SQL based on what columns exist
        columns = []
        values = []
        params = {
            'invoice_number': invoice_data['invoice_number'],
            'invoice_type': 'vat',
            'customer_id': int(invoice_data['customer_id']),
            'issue_date': datetime.strptime(invoice_data['issue_date'], '%Y-%m-%d'),
            'due_date': datetime.strptime(invoice_data['due_date'], '%Y-%m-%d'),
            'status': invoice_data['status'],
            'amount': 0,
            'vat_amount': 0,
            'total_amount': 0,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        # Required columns that should exist
        base_columns = [
            'invoice_number', 'invoice_type', 'customer_id', 'issue_date', 
            'due_date', 'status', 'amount', 'vat_amount', 'total_amount'
        ]
        
        # Optional columns that might exist
        optional_columns = [
            'amount_paid', 'payment_terms', 'reference_number', 
            'created_at', 'updated_at'
        ]
        
        # Add base columns that exist
        for col_name in base_columns:
            if col_name in existing_columns:
                columns.append(col_name)
                values.append(f":{col_name}")
        
        # Add optional columns if they exist
        for col_name in optional_columns:
            if col_name in existing_columns:
                columns.append(col_name)
                values.append(f":{col_name}")
                # Set default values for optional columns
                if col_name == 'amount_paid' and 'amount_paid' not in params:
                    params['amount_paid'] = 0
                elif col_name == 'payment_terms' and 'payment_terms' not in params:
                    params['payment_terms'] = 'NET30'
                elif col_name == 'reference_number' and 'reference_number' not in params:
                    params['reference_number'] = None
        
        # Build the final SQL
        columns_str = ", ".join(columns)
        values_str = ", ".join(values)
        
        sql = f"""
            INSERT INTO invoice ({columns_str})
            VALUES ({values_str})
            RETURNING id
        """
        
        print(f"=== DEBUG: Final SQL: {sql} ===")
        print(f"=== DEBUG: Params: {params} ===")
        
        # Create invoice
        result = db.session.execute(text(sql), params)
        invoice_id = result.fetchone()[0]
        print(f"=== DEBUG CREATE: Created invoice with ID: {invoice_id} ===")
        
        # Add invoice items
        total_amount = 0
        vat_amount = 0
        items_count = 0
        
        for i in range(len(items_data['descriptions'])):
            description = items_data['descriptions'][i].strip()
            if description:  # Only add if description exists and is not empty
                quantity = int(items_data['quantities'][i]) if items_data['quantities'][i] else 1
                unit_price = float(items_data['unit_prices'][i])
                is_vat = items_data['is_vat'][i] == 'true' if i < len(items_data['is_vat']) else True
                
                item_total = quantity * unit_price
                total_amount += item_total
                
                if is_vat:
                    item_vat = item_total * 0.05  # 5% VAT
                    vat_amount += item_vat
                
                print(f"=== DEBUG CREATE: Adding item {i+1}: {description}, qty: {quantity}, price: {unit_price}, vat: {is_vat} ===")
                
                # Check what columns exist in invoice_item table
                item_columns_result = db.session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'invoice_item' 
                    ORDER BY ordinal_position
                """)).fetchall()
                
                item_existing_columns = [row[0] for row in item_columns_result]
                
                # Build dynamic SQL for invoice_item
                item_columns = ['invoice_id', 'description', 'quantity', 'unit_price', 'is_vat']
                item_values = [':invoice_id', ':description', ':quantity', ':unit_price', ':is_vat']
                item_params = {
                    'invoice_id': invoice_id,
                    'description': description,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'is_vat': is_vat
                }
                
                # Add created_at if it exists
                if 'created_at' in item_existing_columns:
                    item_columns.append('created_at')
                    item_values.append(':created_at')
                    item_params['created_at'] = datetime.utcnow()
                
                # Add updated_at if it exists
                if 'updated_at' in item_existing_columns:
                    item_columns.append('updated_at')
                    item_values.append(':updated_at')
                    item_params['updated_at'] = datetime.utcnow()
                
                item_columns_str = ", ".join(item_columns)
                item_values_str = ", ".join(item_values)
                
                item_sql = f"""
                    INSERT INTO invoice_item ({item_columns_str})
                    VALUES ({item_values_str})
                """
                
                db.session.execute(text(item_sql), item_params)
                items_count += 1
        
        print(f"=== DEBUG CREATE: Added {items_count} items for invoice {invoice_id} ===")
        
        # Update invoice with calculated totals
        update_sql = """
            UPDATE invoice SET 
                amount = :amount,
                vat_amount = :vat_amount,
                total_amount = :total_amount,
                updated_at = :updated_at
            WHERE id = :invoice_id
        """
        
        # Add amount_paid to update if it exists
        if 'amount_paid' in existing_columns:
            update_sql = update_sql.replace(
                "updated_at = :updated_at",
                "amount_paid = :amount_paid, updated_at = :updated_at"
            )
            params['amount_paid'] = 0  # Initialize amount_paid to 0
        
        update_params = {
            'invoice_id': invoice_id,
            'amount': total_amount,
            'vat_amount': vat_amount,
            'total_amount': total_amount + vat_amount,
            'updated_at': datetime.utcnow()
        }
        
        if 'amount_paid' in existing_columns:
            update_params['amount_paid'] = 0
        
        db.session.execute(text(update_sql), update_params)
        
        db.session.commit()
        
        print(f"=== DEBUG CREATE: Successfully committed invoice {invoice_id} with {items_count} items ===")
        
        flash(f'Invoice created successfully! Invoice Number: {invoice_data["invoice_number"]}', 'success')
        return redirect(url_for('invoices.list_invoices'))
        
    except Exception as error:
        db.session.rollback()
        print(f"=== DEBUG CREATE ERROR: {error} ===")
        import traceback
        traceback.print_exc()
        flash(f'Error creating invoice: {str(error)}', 'danger')
        return show_create_invoice_form()

def extract_invoice_data(form_data):
    """
    Extract basic invoice data from form
    """
    return {
        'customer_id': form_data.get('customer_id'),
        'invoice_number': form_data.get('invoice_number'),
        'issue_date': form_data.get('issue_date'),
        'due_date': form_data.get('due_date'),
        # New invoices must always start as 'pending'. Status must never be
        # taken from client input here: it can only change to 'paid' (or
        # 'partial') through an actual payment being recorded, via
        # Invoice.add_payment()/mark_as_paid(), which also updates
        # amount_paid and creates the matching income record. Trusting a
        # client-supplied 'status' field let invoices be created already
        # marked 'paid' with amount_paid = 0 and no income recorded.
        'status': 'pending'
    }

def extract_items_data(form_data):
    """
    Extract invoice items data from form
    """
    return {
        'descriptions': form_data.getlist('item_description[]'),
        'quantities': form_data.getlist('item_quantity[]'),
        'unit_prices': form_data.getlist('item_unit_price[]'),
        'is_vat': form_data.getlist('item_is_vat[]')
    }

def validate_invoice_data(invoice_data, items_data):
    """
    Validate invoice data
    """
    # Validate required fields
    required_fields = ['customer_id', 'invoice_number', 'issue_date', 'due_date']
    missing_fields = []
    
    for field in required_fields:
        if not invoice_data[field]:
            missing_fields.append(field.replace('_', ' ').title())
    
    if missing_fields:
        raise Exception(f'Missing required fields: {", ".join(missing_fields)}')
    
    # Validate at least one item
    if not items_data['descriptions'] or not any(items_data['descriptions']):
        raise Exception('Please add at least one invoice item')

@invoices_bp.route('/invoices/<int:invoice_id>', methods=['GET'])
@login_required
def view_invoice_details(invoice_id):
    """
    View invoice details - UPDATED VERSION
    """
    from app import db
    from sqlalchemy import text
    
    try:
        # Get invoice with customer
        from app.models.finance.invoice import Invoice
        Invoice.sync_overdue_statuses()
        invoice_result = db.session.execute(
            text("""
                SELECT 
                    i.*, 
                    c.company_name, 
                    c.trn, 
                    c.contact_person, 
                    c.phone,
                    c.email,
                    c.address,
                    c.city,
                    c.emirate
                FROM invoice i 
                LEFT JOIN customer c ON i.customer_id = c.id 
                WHERE i.id = :invoice_id
            """),
            {'invoice_id': invoice_id}
        ).fetchone()
        
        if not invoice_result:
            flash('Invoice not found', 'danger')
            return redirect(url_for('invoices.list_invoices'))
        
        # Convert to dict
        invoice_dict = {}
        for key, value in invoice_result._mapping.items():
            invoice_dict[key] = value
        
        # Get invoice items
        items_list = []
        try:
            items_result = db.session.execute(
                text("""
                    SELECT 
                        id, description, quantity, unit_price, is_vat
                    FROM invoice_item 
                    WHERE invoice_id = :invoice_id
                    ORDER BY id
                """),
                {'invoice_id': invoice_id}
            ).fetchall()
            
            for row in items_result:
                item_dict = dict(row._mapping)
                items_list.append(item_dict)
                
        except Exception as e:
            print(f"Error getting items: {e}")
        
        invoice_dict['invoice_items'] = items_list  # Changed from 'items' to 'invoice_items'
        
        # Get payments for this invoice
        payments_list = []
        try:
            payments_result = db.session.execute(
                text("""
                    SELECT 
                        id, amount, payment_method, reference_number,
                        payment_date, status
                    FROM payment 
                    WHERE invoice_id = :invoice_id
                    ORDER BY payment_date DESC
                """),
                {'invoice_id': invoice_id}
            ).fetchall()
            
            for row in payments_result:
                payment_dict = dict(row._mapping)
                payments_list.append(payment_dict)
                
        except Exception as e:
            print(f"Error getting payments: {e}")
        
        invoice_dict['invoice_payments'] = payments_list  # Changed from 'payments' to 'invoice_payments'
        
        return render_template('accounts/view_invoice.html', invoice=invoice_dict)
        
    except Exception as e:
        print(f"Error viewing invoice: {e}")
        flash(f'Error loading invoice: {e}', 'danger')
        return redirect(url_for('invoices.list_invoices'))
    
# Disabled: diagnostic endpoint must not be exposed through the web application.
@login_required
def debug_invoice_db(invoice_id):
    """
    Debug route to check database directly
    """
    from app import db
    
    try:
        # Check invoice exists
        invoice = db.session.execute(
            text("SELECT * FROM invoice WHERE id = :invoice_id"),
            {'invoice_id': invoice_id}
        ).fetchone()
        
        # Check items exist
        items = db.session.execute(
            text("SELECT * FROM invoice_item WHERE invoice_id = :invoice_id"),
            {'invoice_id': invoice_id}
        ).fetchall()
        
        return jsonify({
            'invoice_exists': bool(invoice),
            'invoice': dict(invoice._mapping) if invoice else None,
            'items_count': len(items),
            'items': [dict(item._mapping) for item in items] if items else []
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

@invoices_bp.route('/invoices/<int:invoice_id>/delete', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    """
    Delete invoice using raw SQL
    """
    from app import db
    
    try:
        # First delete invoice items
        db.session.execute(
            text("DELETE FROM invoice_item WHERE invoice_id = :invoice_id"),
            {'invoice_id': invoice_id}
        )
        
        # Then delete invoice
        db.session.execute(
            text("DELETE FROM invoice WHERE id = :invoice_id"),
            {'invoice_id': invoice_id}
        )
        
        db.session.commit()
        flash('Invoice deleted successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting invoice: {e}', 'danger')
    
    return redirect(url_for('invoices.list_invoices'))

@invoices_bp.route('/invoices/<int:invoice_id>/mark_paid', methods=['POST'])
@login_required
def mark_invoice_paid(invoice_id):
    """
    Mark invoice as paid using the fixed model method
    """
    from app import db
    from app.models.finance.invoice import Invoice
    
    try:
        # Get invoice using model
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            flash('Invoice not found', 'danger')
            return redirect(url_for('invoices.list_invoices'))
        
        # Use the model's mark_as_paid method
        invoice.mark_as_paid(
            payment_method='bank_transfer',
            payment_reference=f'MANUAL-{datetime.utcnow().strftime("%Y%m%d")}',
            recorded_by=current_user.id
        )
        
        db.session.commit()
        flash('Invoice marked as paid successfully! Income created.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking invoice as paid: {str(e)}', 'danger')
    
    return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))

# Add a simple edit route to avoid template errors
@invoices_bp.route('/invoices/<int:invoice_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    """
    Edit existing invoice - FIXED COLUMN NAMES
    """
    from app import db
    
    if request.method == 'GET':
        return show_edit_invoice_form(invoice_id)
    
    # Handle POST request
    try:
        invoice_data = extract_invoice_data(request.form)
        items_data = extract_items_data(request.form)
        
        print(f"=== DEBUG EDIT POST: Starting update for invoice {invoice_id} ===")
        print(f"=== DEBUG EDIT POST: invoice_data: {invoice_data} ===")
        print(f"=== DEBUG EDIT POST: items count: {len(items_data['descriptions'])} ===")
        
        validate_invoice_data(invoice_data, items_data)
        
        # First verify invoice exists using raw SQL
        invoice_check = db.session.execute(
            text("SELECT id FROM invoice WHERE id = :invoice_id"),
            {'invoice_id': invoice_id}
        ).fetchone()
        
        if not invoice_check:
            flash('Invoice not found', 'danger')
            return redirect(url_for('invoices.list_invoices'))
        
        # Update invoice basic info using raw SQL
        db.session.execute(
            text("""
                UPDATE invoice 
                SET invoice_number = :invoice_number,
                    customer_id = :customer_id,
                    issue_date = :issue_date,
                    due_date = :due_date,
                    status = :status,
                    updated_at = :updated_at
                WHERE id = :invoice_id
            """),
            {
                'invoice_id': invoice_id,
                'invoice_number': invoice_data['invoice_number'],
                'customer_id': invoice_data['customer_id'],
                'issue_date': datetime.strptime(invoice_data['issue_date'], '%Y-%m-%d'),
                'due_date': datetime.strptime(invoice_data['due_date'], '%Y-%m-%d'),
                'status': invoice_data['status'],
                'updated_at': datetime.utcnow()
            }
        )
        
        # Delete existing items
        db.session.execute(
            text("DELETE FROM invoice_item WHERE invoice_id = :invoice_id"),
            {'invoice_id': invoice_id}
        )
        
        # Add new invoice items - FIXED: Use correct column names from your model
        total_amount = 0
        vat_amount = 0
        items_count = 0
        
        for i in range(len(items_data['descriptions'])):
            description = items_data['descriptions'][i].strip()
            if description:  # Only add if description exists and is not empty
                quantity = int(items_data['quantities'][i]) if items_data['quantities'][i] else 1
                unit_price = float(items_data['unit_prices'][i])
                is_vat = items_data['is_vat'][i] == 'true' if i < len(items_data['is_vat']) else False
                
                item_total = quantity * unit_price
                total_amount += item_total
                
                if is_vat:
                    item_vat = item_total * 0.05  # 5% VAT
                    vat_amount += item_vat
                
                print(f"=== DEBUG EDIT POST: Adding item {i+1}: {description}, qty: {quantity}, price: {unit_price}, vat: {is_vat} ===")
                
                # FIXED: Use correct column names that match your database table
                db.session.execute(
                    text("""
                        INSERT INTO invoice_item (
                            invoice_id, description, quantity, unit_price, is_vat,
                            created_at
                        ) VALUES (
                            :invoice_id, :description, :quantity, :unit_price, :is_vat,
                            :created_at
                        )
                    """),
                    {
                        'invoice_id': invoice_id,
                        'description': description,
                        'quantity': quantity,
                        'unit_price': unit_price,
                        'is_vat': is_vat,
                        'created_at': datetime.utcnow()
                        # Removed updated_at since it doesn't exist in your table
                    }
                )
                items_count += 1
        
        print(f"=== DEBUG EDIT POST: Added {items_count} items ===")
        
        # Update invoice with calculated totals
        db.session.execute(
            text("""
                UPDATE invoice SET 
                    amount = :amount,
                    vat_amount = :vat_amount,
                    total_amount = :total_amount,
                    updated_at = :updated_at
                WHERE id = :invoice_id
            """),
            {
                'invoice_id': invoice_id,
                'amount': total_amount,
                'vat_amount': vat_amount,
                'total_amount': total_amount + vat_amount,
                'updated_at': datetime.utcnow()
            }
        )
        
        db.session.commit()
        
        print(f"=== DEBUG EDIT POST: Successfully updated invoice {invoice_id} ===")
        
        flash(f'Invoice updated successfully! Invoice Number: {invoice_data["invoice_number"]}', 'success')
        return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
        
    except Exception as error:
        db.session.rollback()
        print(f"=== DEBUG EDIT POST ERROR: {error} ===")
        traceback.print_exc()
        flash(f'Error updating invoice: {str(error)}', 'danger')
        return show_edit_invoice_form(invoice_id)

def show_edit_invoice_form(invoice_id):
    """
    Show edit invoice form - FINAL FIXED VERSION
    """
    from app import db
    
    try:
        print(f"=== DEBUG EDIT: Starting edit form for invoice {invoice_id} ===")
        
        # Get invoice data
        invoice_result = db.session.execute(
            text("SELECT * FROM invoice WHERE id = :invoice_id"),
            {'invoice_id': invoice_id}
        ).fetchone()
        
        if not invoice_result:
            flash('Invoice not found', 'danger')
            return redirect(url_for('invoices.list_invoices'))
        
        # Convert to simple dictionary
        invoice_data = {}
        if hasattr(invoice_result, '_mapping'):
            invoice_data = dict(invoice_result._mapping)
        elif hasattr(invoice_result, '_asdict'):
            invoice_data = invoice_result._asdict()
        else:
            # Fallback: manual conversion
            invoice_data = {
                'id': invoice_result[0],
                'invoice_number': invoice_result[1],
                'customer_id': invoice_result[2],
                # ... add other fields as needed
            }
        
        # Get items
        items_result = db.session.execute(
            text("SELECT * FROM invoice_item WHERE invoice_id = :invoice_id"),
            {'invoice_id': invoice_id}
        ).fetchall()
        
        invoice_items = []
        for item in items_result:
            if hasattr(item, '_mapping'):
                invoice_items.append(dict(item._mapping))
            elif hasattr(item, '_asdict'):
                invoice_items.append(item._asdict())
            else:
                invoice_items.append({
                    'id': item[0],
                    'description': item[1],
                    'quantity': item[2],
                    'unit_price': float(item[3]),
                    'is_vat': bool(item[4])
                })
        
        # Get customers
        customers_result = db.session.execute(
                text("""
                    SELECT id, company_name
                    FROM customer
                    WHERE is_active = true
                      AND LOWER(company_name) <> LOWER(:issuer_company_name)
                """),
                {
                    'issuer_company_name': os.environ.get(
                        'INVOICE_ISSUER_COMPANY_NAME', 'Hadaf Al Nasar Logistics'
                    )
                }
        ).fetchall()
        
        customers_list = []
        for customer in customers_result:
            if hasattr(customer, '_mapping'):
                customers_list.append(dict(customer._mapping))
            elif hasattr(customer, '_asdict'):
                customers_list.append(customer._asdict())
            else:
                customers_list.append({
                    'id': customer[0],
                    'company_name': customer[1]
                })
        
        print(f"=== DEBUG EDIT: Ready to render template ===")
        print(f"=== DEBUG EDIT: Invoice ID: {invoice_data.get('id')} ===")
        print(f"=== DEBUG EDIT: Items count: {len(invoice_items)} ===")
        
        return render_template(
            'accounts/edit_invoice.html', 
            invoice=invoice_data, 
            invoice_items=invoice_items,  # Separate variable for items
            customers=customers_list
        )
        
    except Exception as e:
        print(f"=== DEBUG EDIT: Error: {e} ===")
        traceback.print_exc()
        flash('Error loading edit form', 'danger')
        return redirect(url_for('invoices.list_invoices'))

@invoices_bp.route('/invoices/<int:invoice_id>/download', methods=['GET'])
@login_required
def download_invoice_pdf(invoice_id):
    """
    Download invoice as PDF with fixed duplicate description header
    """
    try:
        from app import db
        
        # Get invoice data from database
        invoice_result = db.session.execute(
            text("""
                SELECT 
                    i.*, 
                    c.company_name, 
                    c.trn, 
                    c.contact_person,
                    c.email,
                    c.phone,
                    c.address
                FROM invoice i 
                LEFT JOIN customer c ON i.customer_id = c.id 
                WHERE i.id = :invoice_id
            """),
            {'invoice_id': invoice_id}
        ).fetchone()
        
        if not invoice_result:
            flash('Invoice not found', 'danger')
            return redirect(url_for('invoices.list_invoices'))
        
        # Convert to dict
        invoice_dict = {}
        for key, value in invoice_result._mapping.items():
            invoice_dict[key] = value
        
        # Get invoice items
        items_result = db.session.execute(
            text("""
                SELECT 
                    description, quantity, unit_price, is_vat
                FROM invoice_item 
                WHERE invoice_id = :invoice_id
            """),
            {'invoice_id': invoice_id}
        )
        
        items_list = []
        for row in items_result:
            item_dict = {}
            for key, value in row._mapping.items():
                item_dict[key] = value
            items_list.append(item_dict)

        invoice_dict['invoice_items'] = items_list

        # Use the same HTML invoice as the browser and let Chrome produce a
        # real vector PDF, avoiding ReportLab layout drift and raster blur.
        chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
        if not os.path.exists(chrome_path):
            raise RuntimeError('Google Chrome is required to generate the invoice PDF')

        with tempfile.TemporaryDirectory() as temp_dir:
            html_path = os.path.join(temp_dir, 'invoice.html')
            pdf_path = os.path.join(temp_dir, 'invoice.pdf')
            html_content = render_template('accounts/view_invoice.html', invoice=invoice_dict)
            with open(html_path, 'w', encoding='utf-8') as html_file:
                html_file.write(html_content)

            subprocess.run(
                [
                    chrome_path,
                    '--headless=new',
                    '--disable-gpu',
                    '--no-sandbox',
                    '--no-first-run',
                    '--disable-extensions',
                    f'--user-data-dir={os.path.join(temp_dir, "chrome-profile")}',
                    '--no-pdf-header-footer',
                    f'--print-to-pdf={pdf_path}',
                    f'file:///{html_path.replace(os.sep, "/")}',
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )

            with open(pdf_path, 'rb') as pdf_file:
                pdf_data = pdf_file.read()

        filename = f"HADAF_AL_NASAR_Invoice_{invoice_dict.get('invoice_number', 'unknown')}.pdf"
        return send_file(
            io.BytesIO(pdf_data),
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

        # Generate PDF
        buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=22,
            spaceAfter=4,
            alignment=1,
            textColor=colors.HexColor('#1a237e'),
            fontName='Helvetica-Bold',
        )
        
        section_header_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=8,
            textColor=colors.HexColor('#2c3e50'),
            fontName='Helvetica-Bold',
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4,
        )
        
        bold_style = ParagraphStyle(
            'CustomBold',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4,
            fontName='Helvetica-Bold',
        )
        
        footer_style = ParagraphStyle(
            'CustomFooter',
            parent=styles['Normal'],
            fontSize=8,
            spaceAfter=6,
            textColor=colors.HexColor('#666666'),
            alignment=1,
        )
        
        # Title
        title = Paragraph("HADAF AL NASAR CARGO TRANSPORT", title_style)
        elements.append(title)
        elements.append(Paragraph("Transportation & Logistics Services", normal_style))
        elements.append(Paragraph("INVOICE", title_style))
        elements.append(Spacer(1, 10))
        
        # Create two separate sections for Invoice Details and Bill To
        # Left side - INVOICE DETAILS
        invoice_details_elements = []
        invoice_details_elements.append(Paragraph("INVOICE DETAILS", section_header_style))
        invoice_details_elements.append(Paragraph(f"<b>Issue Date:</b> {invoice_dict.get('issue_date').strftime('%d %b %Y') if invoice_dict.get('issue_date') else 'N/A'}", normal_style))
        invoice_details_elements.append(Paragraph(f"<b>Due Date:</b> {invoice_dict.get('due_date').strftime('%d %b %Y') if invoice_dict.get('due_date') else 'N/A'}", normal_style))
        invoice_details_elements.append(Paragraph(f"<b>Status:</b> {invoice_dict.get('status', 'N/A').upper()}", normal_style))
        
        # Right side - BILL TO (with company name)
        bill_to_elements = []
        bill_to_elements.append(Paragraph("BILL TO", section_header_style))
        bill_to_elements.append(Paragraph(f"<b>Company:</b> {invoice_dict.get('company_name', 'N/A')}", normal_style))
        bill_to_elements.append(Paragraph(f"<b>TRN:</b> {invoice_dict.get('trn', 'N/A')}", normal_style))
        bill_to_elements.append(Paragraph(f"<b>Contact:</b> {invoice_dict.get('contact_person', 'N/A')}", normal_style))
        bill_to_elements.append(Paragraph(f"<b>Address:</b> {invoice_dict.get('address', 'N/A')}", normal_style))
        
        # Create a two-column table for the header sections
        header_table_data = [
            [invoice_details_elements, bill_to_elements]
        ]
        
        header_table = Table(header_table_data, colWidths=[3.2*inch, 3.2*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, 0), 'TOP'),
            ('PADDING', (0, 0), (-1, 0), 8),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 15))
        
        # Divider line
        divider = Table([['']], colWidths=[6.4*inch])
        divider.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (0, 0), 1, colors.HexColor('#999999')),
        ]))
        elements.append(divider)
        elements.append(Spacer(1, 12))
        
        # REMOVED: The extra "DESCRIPTION" section header that was causing duplication
        # The table header row will serve as the section header
        
        # Services Data Table
        services_data = [['DESCRIPTION', 'QTY', 'UNIT PRICE (AED)', 'VAT', 'AMOUNT (AED)']]
        
        subtotal = 0
        total_vat = 0
        
        for item in items_list:
            description = item.get('description', '')
            quantity = item.get('quantity', 1)
            unit_price = float(item.get('unit_price', 0))
            is_vat = item.get('is_vat', False)
            
            line_total = quantity * unit_price
            subtotal += line_total
            
            vat_rate = "5%" if is_vat else "0%"
            vat_amount = line_total * 0.05 if is_vat else 0
            total_vat += vat_amount
            
            services_data.append([
                description,
                str(quantity),
                f"{unit_price:.2f}",
                vat_rate,
                f"{line_total:.2f}"
            ])
        
        # Services table - Make the header row more prominent
        services_table = Table(services_data, colWidths=[2.8*inch, 0.6*inch, 1.0*inch, 0.8*inch, 1.2*inch])
        services_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dddddd')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(services_table)
        elements.append(Spacer(1, 20))
        
        # Divider line
        elements.append(divider)
        elements.append(Spacer(1, 15))
        
        # Summary Section - Clean and simple
        total_amount = float(invoice_dict.get('total_amount') or (subtotal + total_vat))
        amount_paid = float(invoice_dict.get('amount_paid') or 0)
        balance_due = max(0, total_amount - amount_paid)
        
        # Create summary as individual tables for better control
        summary_elements = []
        
        # Subtotal
        subtotal_table = Table([
            [Paragraph('<b>Subtotal (Excluding VAT):</b>', bold_style), Paragraph(f'<b>AED {subtotal:,.2f}</b>', bold_style)]
        ], colWidths=[4.0*inch, 2.4*inch])
        subtotal_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        summary_elements.append(subtotal_table)
        summary_elements.append(Spacer(1, 5))
        
        # VAT
        vat_table = Table([
            [Paragraph('<b>VAT (5%):</b>', bold_style), Paragraph(f'<b>AED {float(invoice_dict.get("vat_amount") or total_vat):,.2f}</b>', bold_style)]
        ], colWidths=[4.0*inch, 2.4*inch])
        vat_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        summary_elements.append(vat_table)
        summary_elements.append(Spacer(1, 10))
        
        # Total Amount
        total_table = Table([
            [Paragraph('<b>Total Amount:</b>', bold_style), Paragraph(f'<b>AED {total_amount:,.2f}</b>', bold_style)]
        ], colWidths=[4.0*inch, 2.4*inch])
        total_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#2c3e50')),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ]))
        summary_elements.append(total_table)

        paid_table = Table([
            [Paragraph('<b>Amount Paid:</b>', bold_style), Paragraph(f'<b>AED {amount_paid:,.2f}</b>', bold_style)]
        ], colWidths=[4.0*inch, 2.4*inch])
        paid_table.setStyle(TableStyle([('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        summary_elements.append(paid_table)

        balance_table = Table([
            [Paragraph('<b>Balance Due:</b>', bold_style), Paragraph(f'<b>AED {balance_due:,.2f}</b>', bold_style)]
        ], colWidths=[4.0*inch, 2.4*inch])
        balance_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#2c3e50')),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ]))
        summary_elements.append(balance_table)
        
        # Wrap all summary elements in a right-aligned table
        wrapper_table = Table([[summary_elements]], colWidths=[6.4*inch])
        wrapper_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
        ]))
        
        elements.append(wrapper_table)
        elements.append(Spacer(1, 25))
        
        # Footer
        footer_text = f"""
        Thank you for choosing HADAF AL NASAR CARGO TRANSPORT. For any inquiries, please contact us at the information provided above.
        <br/><br/>
        <b>Generated on:</b> {datetime.now().strftime('%d %b %Y at %H:%M')}
        """
        
        footer = Paragraph(footer_text, footer_style)
        elements.append(footer)
        
        # Build PDF
        doc.build(elements)
        
        # Prepare response
        buffer.seek(0)
        
        filename = f"HADAF_AL_NASAR_Invoice_{invoice_dict.get('invoice_number', 'unknown')}.pdf"
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        traceback.print_exc()
        flash('Error generating PDF invoice', 'danger')
        return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
    
# Disabled: database diagnostics belong in a controlled maintenance workflow.
def diagnose_database():
    from app import db
    try:
        # Check all tables
        tables_result = db.session.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        ).fetchall()
        
        tables = [table[0] for table in tables_result]
        
        # Check if invoice_item table exists
        invoice_item_exists = 'invoice_item' in tables
        invoice_items_exists = 'invoice_items' in tables
        
        # Check structure of related tables
        invoice_columns = []
        if 'invoice' in tables:
            invoice_columns_result = db.session.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'invoice'")
            ).fetchall()
            invoice_columns = [col[0] for col in invoice_columns_result]
        
        return jsonify({
            'all_tables': tables,
            'invoice_item_exists': invoice_item_exists,
            'invoice_items_exists': invoice_items_exists,
            'invoice_columns': invoice_columns,
            'tables_count': len(tables)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})
    
# Disabled: schema inspection belongs in migration validation tooling.
def check_invoice_item_structure():
    from app import db
    try:
        # Check the columns of invoice_item table
        columns_result = db.session.execute(
            text("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'invoice_item' ORDER BY ordinal_position")
        ).fetchall()
        
        columns = [{'column_name': col[0], 'data_type': col[1], 'is_nullable': col[2]} for col in columns_result]
        
        return jsonify({
            'invoice_item_columns': columns
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})
    
# Disabled: schema changes must be implemented through Alembic migrations.
def fix_all_invoice_columns():
    """
    Quick fix to add ALL missing columns to invoice table
    """
    from app import db
    from sqlalchemy import text
    
    try:
        # Check and add each missing column
        columns_to_add = [
            ('amount_paid', 'FLOAT DEFAULT 0.0 NOT NULL'),
            ('payment_terms', 'VARCHAR(50) DEFAULT \'NET30\''),
            ('reference_number', 'VARCHAR(100)'),
            ('created_at', 'TIMESTAMP DEFAULT NOW()')
        ]
        
        results = []
        for column_name, column_def in columns_to_add:
            # Check if column exists
            result = db.session.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'invoice' AND column_name = :column_name"),
                {'column_name': column_name}
            ).fetchone()
            
            if not result:
                print(f"=== Adding {column_name} column to invoice table ===")
                db.session.execute(text(f"ALTER TABLE invoice ADD COLUMN {column_name} {column_def}"))
                results.append(f"Added {column_name} column")
            else:
                results.append(f"{column_name} column already exists")
        
        # Also rename description to notes to match the model
        desc_result = db.session.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'invoice' AND column_name = 'description'")
        ).fetchone()
        
        notes_result = db.session.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'invoice' AND column_name = 'notes'")
        ).fetchone()
        
        if desc_result and not notes_result:
            print("=== Renaming description column to notes ===")
            db.session.execute(text("ALTER TABLE invoice RENAME COLUMN description TO notes"))
            results.append("Renamed description to notes")
        
        db.session.commit()
        return jsonify({"results": results})
            
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)})
    
# Disabled: schema changes must be implemented through Alembic migrations.
def final_database_fix():
    """
    Final manual fix for database schema - uses pure SQL
    """
    from app import db
    from sqlalchemy import text
    
    try:
        results = []
        
        # 1. Fix invoice table - only add missing columns
        columns_to_check = [
            ('amount_paid', 'ALTER TABLE invoice ADD COLUMN IF NOT EXISTS amount_paid FLOAT DEFAULT 0.0 NOT NULL'),
            ('payment_terms', 'ALTER TABLE invoice ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(50) DEFAULT \'NET30\''),
            ('reference_number', 'ALTER TABLE invoice ADD COLUMN IF NOT EXISTS reference_number VARCHAR(100)'),
        ]
        
        for column_name, sql in columns_to_check:
            try:
                db.session.execute(text(sql))
                results.append(f"Checked/added {column_name}")
            except Exception as e:
                results.append(f"Column {column_name}: {str(e)}")
        
        # 2. Fix invoice_item table
        try:
            db.session.execute(text('ALTER TABLE invoice_item ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()'))
            results.append("Checked/added updated_at to invoice_item")
        except Exception as e:
            results.append(f"invoice_item updated_at: {str(e)}")
        
        db.session.commit()
        
        # 3. Verify the current schema
        schema_result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'invoice' 
            ORDER BY ordinal_position
        """)).fetchall()
        
        current_columns = [row[0] for row in schema_result]
        
        return jsonify({
            "status": "success",
            "results": results,
            "current_columns": current_columns
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)})
    
@invoices_bp.route('/invoices/<int:invoice_id>/add_payment', methods=['POST'])
@login_required
def add_invoice_payment(invoice_id):
    """
    Add payment to invoice and create income record using the fixed model method
    """
    from app import db
    from app.models.finance.invoice import Invoice
    
    try:
        # Get invoice using model
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            flash('Invoice not found', 'danger')
            return redirect(url_for('invoices.list_invoices'))
        
        # Get payment data from form
        amount = float(request.form.get('amount', 0))
        payment_method = request.form.get('payment_method', 'bank_transfer').lower()
        reference_number = request.form.get('reference_number')
        notes = request.form.get('notes', '')
        
        # Validate amount
        if amount <= 0:
            flash('Payment amount must be greater than 0', 'danger')
            return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
        
        # Validate payment method
        valid_methods = ['cash', 'bank_transfer', 'card', 'cheque', 'online', 'wallet']
        if payment_method not in valid_methods:
            flash(f'Invalid payment method. Please use one of: {", ".join(valid_methods)}', 'danger')
            return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
        
        # Check if payment exceeds balance
        balance_due = invoice.balance_due
        if amount > balance_due:
            flash(f'Payment amount exceeds balance due (AED {balance_due:.2f})', 'danger')
            return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
        
        # Use the fixed model method to add payment
        try:
            payment = invoice.add_payment(
                amount=amount,
                payment_method=payment_method,
                reference_number=reference_number,
                notes=notes,
                recorded_by=current_user.id  # Use current_user.id
            )
            
            db.session.commit()
            
            flash(f'Payment of AED {amount:.2f} recorded successfully! Income created.', 'success')
            
        except ValueError as e:
            if "Invalid payment method" in str(e):
                flash(f'Error: {str(e)}', 'danger')
            else:
                flash(f'Error recording payment: {str(e)}', 'danger')
            return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording payment: {str(e)}', 'danger')
            return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing payment: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))

@invoices_bp.route('/invoices/<int:invoice_id>/mark_paid_full', methods=['POST'])
@login_required
def mark_invoice_paid_full(invoice_id):
    """
    Mark invoice as fully paid and create income record using the fixed model method
    """
    from app import db
    from app.models.finance.invoice import Invoice
    
    try:
        # Get invoice using model
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            flash('Invoice not found', 'danger')
            return redirect(url_for('invoices.list_invoices'))
        
        # Check if already paid
        if invoice.is_paid:
            flash('Invoice is already paid', 'warning')
            return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
        
        # Calculate balance due
        balance_due = invoice.balance_due
        
        # Use the model's mark_as_paid method
        try:
            invoice.mark_as_paid(
                payment_method='bank_transfer',
                payment_reference=f'FULL-{datetime.utcnow().strftime("%Y%m%d")}',
                recorded_by=current_user.id  # Use current_user.id
            )
            
            db.session.commit()
            flash(f'Invoice marked as fully paid! Income of AED {invoice.total_amount:.2f} created.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error marking invoice as paid: {str(e)}', 'danger')
            return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing full payment: {str(e)}', 'danger')
    
    return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))

@invoices_bp.route('/invoices/<int:invoice_id>/verify_income', methods=['GET'])
@login_required
def verify_invoice_income(invoice_id):
    """
    Verify and show income record details for an invoice
    """
    from app import db
    from app.models.finance.invoice import Invoice
    from app.models.wps.income import Income
    
    try:
        # Get invoice with payments and incomes
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            flash('Invoice not found', 'danger')
            return redirect(url_for('invoices.list_invoices'))
        
        # Get all payments for this invoice
        payments = invoice.payments
        
        # Get all incomes for this invoice
        incomes = invoice.invoice_incomes
        
        # Calculate totals
        total_payments = sum(p.amount for p in payments if p.status == 'completed')
        total_income = sum(i.total_amount for i in incomes if i.status == 'received')
        
        # Check for discrepancies
        discrepancy = total_payments - total_income
        has_discrepancy = abs(discrepancy) > 0.01  # Allow small rounding differences
        
        # Get payment-income mapping
        payment_income_map = []
        for payment in payments:
            if payment.status == 'completed':
                # Find income with matching reference
                matching_income = None
                if payment.reference_number:
                    matching_income = next((i for i in incomes if i.reference_number == payment.reference_number), None)
                if not matching_income and payment.payment_reference:
                    matching_income = next((i for i in incomes if i.payment_reference == payment.payment_reference), None)
                
                payment_income_map.append({
                    'payment': payment,
                    'income': matching_income,
                    'has_income': matching_income is not None
                })
        
        return render_template('accounts/verify_income.html',
                             invoice=invoice,
                             payments=payments,
                             incomes=incomes,
                             total_payments=total_payments,
                             total_income=total_income,
                             discrepancy=discrepancy,
                             has_discrepancy=has_discrepancy,
                             payment_income_map=payment_income_map)
        
    except Exception as e:
        flash(f'Error verifying income: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()
        return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))

@invoices_bp.route('/invoices/<int:invoice_id>/fix_income', methods=['POST'])
@login_required
def fix_invoice_income(invoice_id):
    """
    Fix income records for a specific invoice
    """
    from app import db
    from app.models.finance.invoice import Invoice
    
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            flash('Invoice not found', 'danger')
            return redirect(url_for('invoices.list_invoices'))
        
        # Sync income from existing payments
        fixed_count = invoice.sync_income_from_payments(recorded_by=current_user.id)
        
        # Update income_created flag
        if invoice.amount_paid >= invoice.total_amount:
            invoice.income_created = True
        
        db.session.commit()
        
        if fixed_count > 0:
            flash(f'Fixed {fixed_count} income records for invoice {invoice.invoice_number}', 'success')
        else:
            flash('All income records are already in sync', 'info')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error fixing income records: {str(e)}', 'danger')
    
    return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))

@invoices_bp.route('/invoices/fix_all_income', methods=['POST'])
@login_required
def fix_all_invoice_income():
    """
    Fix income records for all invoices (admin only)
    """
    from app.utils.invoice_income_sync import fix_all_invoice_income_records
    
    try:
        fixed_count = fix_all_invoice_income_records()
        flash(f'Fixed income records for {fixed_count} invoices', 'success')
    except Exception as e:
        flash(f'Error fixing income records: {str(e)}', 'danger')
    
    return redirect(url_for('invoices.list_invoices'))

# Disabled: test endpoint must not be exposed through the web application.
@login_required
def test_income_creation(invoice_id):
    """
    Test income creation for an invoice
    """
    from app import db
    from app.models.finance.invoice import Invoice
    from app.models.wps.income import Income
    
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({"error": "Invoice not found"})
        
        # Test creating a simple payment with VALID payment method
        payment_data = {
            'amount': min(100.0, invoice.balance_due) if invoice.balance_due > 0 else 100.0,
            'payment_method': 'cash',  # Changed from 'test' to valid method
            'reference_number': f'TEST-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
            'notes': 'Test payment for income creation',
            'recorded_by': current_user.id if current_user else 1
        }
        
        # Create payment using the model method
        payment = invoice.add_payment(**payment_data)
        
        # Check if income was created
        incomes = Income.query.filter_by(invoice_id=invoice_id).all()
        
        return jsonify({
            "success": True,
            "invoice_id": invoice_id,
            "invoice_number": invoice.invoice_number,
            "balance_due_before": invoice.balance_due + payment_data['amount'],  # Before payment
            "balance_due_after": invoice.balance_due,
            "payment_created": {
                'id': payment.id if payment else None,
                'amount': payment.amount if payment else None,
                'method': payment.payment_method if payment else None
            },
            "incomes_created": len(incomes),
            "incomes": [{
                'id': inc.id,
                'reference_number': inc.reference_number,
                'total_amount': inc.total_amount,
                'status': inc.status,
                'created_at': inc.created_at.isoformat() if inc.created_at else None
            } for inc in incomes]
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        })
    
# Disabled: diagnostic endpoint must not be exposed through the web application.
@login_required
def diagnose_invoice(invoice_id):
    """
    Comprehensive diagnosis for an invoice
    """
    from app import db
    from app.models.finance.invoice import Invoice
    from app.models.wps.income import Income
    from app.models.finance.payment import Payment
    
    try:
        # Get invoice using model
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({"error": "Invoice not found"})
        
        # Get all payments for this invoice
        payments = Payment.query.filter_by(invoice_id=invoice_id).all()
        
        # Get all incomes for this invoice
        incomes = Income.query.filter_by(invoice_id=invoice_id).all()
        
        # Calculate totals
        total_payments = sum(p.amount for p in payments if p.status == 'completed')
        total_income = sum(i.total_amount for i in incomes if i.status == 'received')
        
        # Check for missing database columns
        column_check = {
            'invoice': [],
            'invoice_item': [],
            'income': []
        }
        
        # Check invoice table columns
        try:
            invoice_cols = db.session.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'invoice'
            """)).fetchall()
            column_check['invoice'] = [dict(col) for col in invoice_cols]
        except:
            column_check['invoice'] = "Error checking columns"
        
        # Check if invoice_item table exists and has data
        try:
            item_count = db.session.execute(text("""
                SELECT COUNT(*) FROM invoice_item WHERE invoice_id = :invoice_id
            """), {'invoice_id': invoice_id}).scalar()
            
            items = db.session.execute(text("""
                SELECT * FROM invoice_item WHERE invoice_id = :invoice_id
            """), {'invoice_id': invoice_id}).fetchall()
        except:
            item_count = 0
            items = []
        
        # Return comprehensive diagnosis
        return jsonify({
            "invoice": {
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "status": invoice.status,
                "amount": invoice.amount,
                "vat_amount": invoice.vat_amount,
                "total_amount": invoice.total_amount,
                "amount_paid": invoice.amount_paid,
                "balance_due": invoice.balance_due,
                "income_created": invoice.income_created,
                "customer_id": invoice.customer_id,
                "customer_name": invoice.customer.company_name if invoice.customer else None
            },
            "payments": {
                "count": len(payments),
                "total_amount": total_payments,
                "list": [{
                    'id': p.id,
                    'amount': p.amount,
                    'method': p.payment_method,
                    'reference': p.reference_number,
                    'status': p.status,
                    'date': p.payment_date.isoformat() if p.payment_date else None
                } for p in payments]
            },
            "incomes": {
                "count": len(incomes),
                "total_amount": total_income,
                "list": [{
                    'id': i.id,
                    'amount': i.amount,
                    'total_amount': i.total_amount,
                    'reference': i.reference_number,
                    'payment_reference': i.payment_reference,
                    'status': i.status,
                    'created_at': i.created_at.isoformat() if i.created_at else None
                } for i in incomes]
            },
            "discrepancy": {
                "payment_income_difference": total_payments - total_income,
                "invoice_payment_difference": invoice.amount_paid - total_payments,
                "is_balanced": abs(total_payments - total_income) < 0.01 and abs(invoice.amount_paid - total_payments) < 0.01
            },
            "database": {
                "invoice_items_count": item_count,
                "invoice_items": [dict(item._mapping) for item in items] if items else [],
                "column_check": column_check
            }
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        })

@invoices_bp.route('/invoices/<int:invoice_id>/fix-income-records', methods=['POST'])
@login_required
def fix_single_invoice_income(invoice_id):
    """
    Fix income records for a single invoice
    """
    from app import db
    from app.models.finance.invoice import Invoice
    from app.models.wps.income import Income
    from app.models.finance.payment import Payment
    
    try:
        # Get invoice
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({"error": "Invoice not found"})
        
        # Get all completed payments
        payments = Payment.query.filter_by(
            invoice_id=invoice_id, 
            status='completed'
        ).all()
        
        # Get existing incomes
        existing_incomes = Income.query.filter_by(invoice_id=invoice_id).all()
        
        fixed_count = 0
        created_incomes = []
        
        # For each payment, check if income exists
        for payment in payments:
            # Check if income already exists for this payment
            income_exists = False
            
            # Check by reference number
            if payment.reference_number:
                existing = Income.query.filter_by(
                    reference_number=payment.reference_number,
                    invoice_id=invoice_id
                ).first()
                if existing:
                    income_exists = True
            
            # Check by payment_reference
            if not income_exists and payment.payment_reference:
                existing = Income.query.filter_by(
                    payment_reference=payment.payment_reference,
                    invoice_id=invoice_id
                ).first()
                if existing:
                    income_exists = True
            
            # If no income exists, create one
            if not income_exists and payment.amount > 0:
                try:
                    # Calculate VAT proportion
                    if invoice.total_amount > 0:
                        payment_ratio = payment.amount / invoice.total_amount
                        vat_amount = invoice.vat_amount * payment_ratio
                        base_amount = payment.amount - vat_amount
                    else:
                        base_amount = payment.amount
                        vat_amount = 0
                    
                    # Create income reference
                    income_reference = payment.reference_number or f"{invoice.invoice_number}-PAY-{payment.id}"
                    
                    income = Income(
                        income_type='invoice_payment',
                        amount=base_amount,
                        tax_amount=vat_amount,
                        total_amount=payment.amount,
                        currency='AED',
                        income_date=payment.payment_date.date() if payment.payment_date else datetime.utcnow().date(),
                        payment_received_date=payment.payment_date.date() if payment.payment_date else datetime.utcnow().date(),
                        description=f"Payment for Invoice {invoice.invoice_number}",
                        category='invoice',
                        payment_method=payment.payment_method,
                        payment_reference=payment.reference_number,
                        customer_id=invoice.customer_id,
                        customer_name=invoice.customer.company_name if invoice.customer else None,
                        customer_contact=invoice.customer.contact_person if invoice.customer else None,
                        status='received',
                        invoice_id=invoice_id,
                        recorded_by=current_user.id if current_user else payment.recorded_by or 1,
                        reference_number=income_reference
                    )
                    
                    db.session.add(income)
                    created_incomes.append({
                        'payment_id': payment.id,
                        'income_id': income.id,
                        'amount': payment.amount,
                        'reference': income_reference
                    })
                    fixed_count += 1
                    
                except Exception as e:
                    print(f"Error creating income for payment {payment.id}: {e}")
        
        # Update invoice's income_created flag if all payments have incomes
        if payments and fixed_count == len(payments):
            invoice.income_created = True
        
        # Update amount_paid if it doesn't match sum of payments
        total_payments = sum(p.amount for p in payments)
        if abs(invoice.amount_paid - total_payments) > 0.01:
            invoice.amount_paid = total_payments
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "invoice_id": invoice_id,
            "invoice_number": invoice.invoice_number,
            "fixed_count": fixed_count,
            "created_incomes": created_incomes,
            "payments_count": len(payments),
            "existing_incomes_count": len(existing_incomes),
            "total_amount_paid": invoice.amount_paid,
            "income_created_flag": invoice.income_created
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        })
    
@invoices_bp.route('/invoices/<int:invoice_id>/create-missing-income', methods=['POST'])
@login_required
def create_missing_income(invoice_id):
    """
    Create missing income record for an invoice
    """
    from app import db
    from app.models.finance.invoice import Invoice
    from app.models.wps.income import Income
    
    try:
        # Get invoice
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({"error": "Invoice not found"})
        
        # Check if income already exists
        existing_incomes = Income.query.filter_by(invoice_id=invoice_id).all()
        
        if existing_incomes:
            return jsonify({
                "warning": f"Income already exists. Count: {len(existing_incomes)}",
                "incomes": [{
                    'id': inc.id,
                    'amount': inc.amount,
                    'total_amount': inc.total_amount,
                    'reference': inc.reference_number
                } for inc in existing_incomes]
            })
        
        # Create income record from invoice
        income = Income(
            income_type='invoice_payment',
            amount=invoice.amount,  # Base amount without VAT
            tax_amount=invoice.vat_amount,  # VAT amount
            total_amount=invoice.total_amount,  # Total with VAT
            currency='AED',
            income_date=invoice.issue_date.date() if invoice.issue_date else datetime.utcnow().date(),
            payment_received_date=datetime.utcnow().date(),
            description=f"Payment for Invoice {invoice.invoice_number}: {invoice.description or 'Invoice payment'}",
            category='invoice',
            payment_method='bank_transfer',  # Default to bank transfer
            payment_reference=f'MANUAL-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
            customer_id=invoice.customer_id,
            customer_name=invoice.customer.company_name if invoice.customer else None,
            customer_contact=invoice.customer.contact_person if invoice.customer else None,
            customer_phone=invoice.customer.phone if invoice.customer else None,
            customer_trn=invoice.customer.trn if invoice.customer else None,
            customer_email=invoice.customer.email if invoice.customer else None,
            status='received',
            invoice_id=invoice_id,
            recorded_by=current_user.id if current_user else 1,
            reference_number=f"{invoice.invoice_number}-INCOME-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )
        
        # Set relationships
        income.customer = invoice.customer
        income.invoice = invoice
        
        db.session.add(income)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Income record created for invoice {invoice.invoice_number}",
            "income": {
                "id": income.id,
                "reference_number": income.reference_number,
                "amount": income.amount,
                "total_amount": income.total_amount,
                "status": income.status
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        })

# Disabled: destructive schema changes must never be exposed through HTTP.
def final_database_fix_v2():
    """
    Final manual fix for database schema - improved version
    """
    from app import db
    from sqlalchemy import text
    
    try:
        results = []
        
        # 1. Fix invoice table
        try:
            # First, let's see what columns exist
            columns_result = db.session.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'invoice'
                ORDER BY ordinal_position
            """)).fetchall()
            
            existing_columns = [row[0] for row in columns_result]
            results.append(f"Existing invoice columns: {existing_columns}")
            
            # Check and add missing columns
            columns_to_add = [
                ('amount_paid', 'FLOAT DEFAULT 0.0'),
                ('income_created', 'BOOLEAN DEFAULT FALSE'),
                ('payment_terms', 'VARCHAR(50) DEFAULT \'NET30\''),
                ('reference_number', 'VARCHAR(100)'),
                ('description', 'TEXT')
            ]
            
            for column_name, column_def in columns_to_add:
                if column_name not in existing_columns:
                    try:
                        db.session.execute(text(f"ALTER TABLE invoice ADD COLUMN {column_name} {column_def}"))
                        results.append(f"Added column: {column_name}")
                    except Exception as e:
                        results.append(f"Failed to add {column_name}: {str(e)}")
                else:
                    results.append(f"Column {column_name} already exists")
        
        except Exception as e:
            results.append(f"Error with invoice table: {str(e)}")
        
        # 2. Fix invoice_item table
        try:
            db.session.execute(text('ALTER TABLE invoice_item ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'))
            results.append("Checked/added created_at to invoice_item")
        except Exception as e:
            results.append(f"invoice_item created_at: {str(e)}")
        
        # 3. Create or fix income table
        try:
            # Drop and recreate income table to ensure proper schema
            db.session.execute(text("DROP TABLE IF EXISTS income CASCADE"))
            
            db.session.execute(text("""
                CREATE TABLE income (
                    id SERIAL PRIMARY KEY,
                    income_type VARCHAR(50),
                    amount DECIMAL(15,2) NOT NULL,
                    tax_amount DECIMAL(15,2) DEFAULT 0,
                    total_amount DECIMAL(15,2) NOT NULL,
                    currency VARCHAR(10) DEFAULT 'AED',
                    income_date DATE NOT NULL,
                    payment_received_date DATE,
                    description TEXT,
                    category VARCHAR(50),
                    payment_method VARCHAR(50),
                    payment_reference VARCHAR(100),
                    customer_id INTEGER,
                    customer_name VARCHAR(255),
                    customer_contact VARCHAR(255),
                    customer_phone VARCHAR(50),
                    customer_trn VARCHAR(50),
                    customer_email VARCHAR(255),
                    status VARCHAR(50) DEFAULT 'received',
                    invoice_id INTEGER REFERENCES invoice(id),
                    recorded_by INTEGER,
                    reference_number VARCHAR(100) UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            results.append("Created income table")
        except Exception as e:
            results.append(f"Error creating income table: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "results": results
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)})
    
@invoices_bp.route('/invoices/<int:invoice_id>/complete-fix', methods=['POST'])
@login_required
def complete_invoice_fix(invoice_id):
    """
    Complete fix for all invoice issues
    """
    from app import db
    from app.models.finance.invoice import Invoice
    from app.models.wps.income import Income
    from app.models.finance.payment import Payment
    
    try:
        results = []
        
        # 1. Get invoice
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return jsonify({"error": "Invoice not found"})
        
        results.append(f"Working on invoice: {invoice.invoice_number}")
        
        # 2. Fix payments (add reference if missing)
        payments = Payment.query.filter_by(invoice_id=invoice_id).all()
        for payment in payments:
            if not payment.reference_number or payment.reference_number == "":
                payment.reference_number = f"PAY-{payment.id}-{datetime.utcnow().strftime('%Y%m%d')}"
                results.append(f"Fixed payment {payment.id} reference: {payment.reference_number}")
        
        # 3. Create income from total invoice amount
        existing_incomes = Income.query.filter_by(invoice_id=invoice_id).all()
        
        if not existing_incomes and invoice.amount_paid > 0:
            # Create income record
            income = Income(
                income_type='invoice_payment',
                amount=invoice.amount,
                tax_amount=invoice.vat_amount,
                total_amount=invoice.total_amount,
                currency='AED',
                income_date=invoice.issue_date.date() if invoice.issue_date else datetime.utcnow().date(),
                payment_received_date=datetime.utcnow().date(),
                description=f"Payment for Invoice {invoice.invoice_number}",
                category='invoice',
                payment_method='bank_transfer',
                payment_reference=f'FIXED-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
                customer_id=invoice.customer_id,
                customer_name=invoice.customer.company_name if invoice.customer else None,
                customer_contact=invoice.customer.contact_person if invoice.customer else None,
                customer_phone=invoice.customer.phone if invoice.customer else None,
                customer_trn=invoice.customer.trn if invoice.customer else None,
                customer_email=invoice.customer.email if invoice.customer else None,
                status='received',
                invoice_id=invoice_id,
                recorded_by=current_user.id if current_user else 1,
                reference_number=f"{invoice.invoice_number}-FULL-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            )
            
            db.session.add(income)
            invoice.income_created = True
            results.append(f"Created income record: {income.reference_number}")
        
        # 4. Verify and update invoice status
        if invoice.amount_paid >= invoice.total_amount and invoice.status != 'paid':
            invoice.status = 'paid'
            results.append("Updated invoice status to 'paid'")
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Complete fix applied",
            "results": results,
            "invoice": {
                "id": invoice.id,
                "number": invoice.invoice_number,
                "status": invoice.status,
                "amount_paid": invoice.amount_paid,
                "total_amount": invoice.total_amount,
                "income_created": invoice.income_created
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        })
    
# Disabled: debug endpoint must not be exposed through the web application.
def debug_invoice_1():
    """
    Simple debug route for invoice 1
    """
    from app import db
    from sqlalchemy import text
    
    try:
        # Check invoice
        invoice_result = db.session.execute(
            text("SELECT id, invoice_number, total_amount, amount_paid, status FROM invoice WHERE id = 1")
        ).fetchone()
        
        # Check invoice items
        items_result = db.session.execute(
            text("SELECT id, description, quantity, unit_price FROM invoice_item WHERE invoice_id = 1")
        ).fetchall()
        
        # Check payments
        payments_result = db.session.execute(
            text("SELECT id, amount, payment_method FROM payment WHERE invoice_id = 1")
        ).fetchall()
        
        # Check income (if table exists)
        try:
            income_result = db.session.execute(
                text("SELECT id, total_amount, reference_number FROM income WHERE invoice_id = 1")
            ).fetchall()
        except:
            income_result = []
        
        return jsonify({
            "invoice": dict(invoice_result._mapping) if invoice_result else None,
            "items": [dict(item._mapping) for item in items_result],
            "payments": [dict(payment._mapping) for payment in payments_result],
            "incomes": [dict(income._mapping) for income in income_result],
            "tables_exist": {
                "invoice": invoice_result is not None,
                "invoice_item": len(items_result) > 0,
                "payment": len(payments_result) > 0,
                "income": len(income_result) > 0
            }
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        })
    
# Disabled: schema changes must be implemented through Alembic migrations.
def direct_fix_income_table():
    """
    Direct fix for income table with minimal columns
    """
    from app import db
    from sqlalchemy import text
    
    try:
        # First, let's check what income table exists
        try:
            db.session.execute(text("SELECT 1 FROM income LIMIT 1"))
            return jsonify({"info": "Income table already exists"})
        except:
            pass
        
        # Create simple income table with only necessary columns
        create_sql = """
        CREATE TABLE IF NOT EXISTS income (
            id SERIAL PRIMARY KEY,
            income_number VARCHAR(100),
            reference_number VARCHAR(100),
            income_type VARCHAR(50),
            amount DECIMAL(15,2),
            total_amount DECIMAL(15,2),
            description TEXT,
            income_date DATE,
            payment_received_date DATE,
            payment_method VARCHAR(50),
            customer_name VARCHAR(255),
            status VARCHAR(50),
            invoice_id INTEGER,
            recorded_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        db.session.execute(text(create_sql))
        
        # Create indexes
        index_sqls = [
            "CREATE INDEX IF NOT EXISTS idx_income_invoice_id ON income(invoice_id)",
            "CREATE INDEX IF NOT EXISTS idx_income_income_date ON income(income_date)"
        ]
        
        for sql in index_sqls:
            try:
                db.session.execute(text(sql))
            except:
                pass
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Simple income table created"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)})
    
# Disabled: data repair must use a reviewed maintenance command or service.
def direct_create_income_1():
    """
    Direct SQL to create income for invoice 1
    """
    from app import db
    from sqlalchemy import text
    
    try:
        # First, let's check if income table exists
        try:
            db.session.execute(text("SELECT 1 FROM income LIMIT 1"))
        except:
            # Create the table first
            db.session.execute(text("""
                CREATE TABLE income (
                    id SERIAL PRIMARY KEY,
                    income_number VARCHAR(100),
                    reference_number VARCHAR(100),
                    income_type VARCHAR(50),
                    amount DECIMAL(15,2),
                    total_amount DECIMAL(15,2),
                    description TEXT,
                    income_date DATE,
                    payment_received_date DATE,
                    payment_method VARCHAR(50),
                    customer_name VARCHAR(255),
                    status VARCHAR(50),
                    invoice_id INTEGER,
                    recorded_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        
        # Check if income already exists for invoice 1
        existing = db.session.execute(
            text("SELECT COUNT(*) as count FROM income WHERE invoice_id = 1")
        ).scalar()
        
        if existing and existing > 0:
            return jsonify({
                "info": f"Income already exists for invoice 1 (count: {existing})",
                "incomes": [
                    dict(row._mapping) for row in 
                    db.session.execute(text("SELECT * FROM income WHERE invoice_id = 1")).fetchall()
                ]
            })
        
        # Get invoice details
        invoice = db.session.execute(
            text("SELECT i.*, c.company_name FROM invoice i LEFT JOIN customer c ON i.customer_id = c.id WHERE i.id = 1")
        ).fetchone()
        
        if not invoice:
            return jsonify({"error": "Invoice 1 not found"})
        
        # Create income record
        income_sql = """
        INSERT INTO income (
            income_number, reference_number, income_type, amount, total_amount,
            description, income_date, payment_received_date, payment_method,
            customer_name, status, invoice_id, recorded_by
        ) VALUES (
            :income_number, :reference_number, :income_type, :amount, :total_amount,
            :description, :income_date, :payment_received_date, :payment_method,
            :customer_name, :status, :invoice_id, :recorded_by
        ) RETURNING id
        """
        
        params = {
            'income_number': f'INC-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
            'reference_number': f'INV-{invoice.invoice_number}',
            'income_type': 'invoice_payment',
            'amount': float(invoice.amount),
            'total_amount': float(invoice.total_amount),
            'description': f'Payment for Invoice {invoice.invoice_number}',
            'income_date': invoice.issue_date,
            'payment_received_date': datetime.utcnow().date(),
            'payment_method': 'bank_transfer',
            'customer_name': invoice.company_name or 'Unknown',
            'status': 'received',
            'invoice_id': 1,
            'recorded_by': 1
        }
        
        result = db.session.execute(text(income_sql), params)
        income_id = result.fetchone()[0]
        
        # Update invoice to mark income as created
        db.session.execute(
            text("UPDATE invoice SET income_created = TRUE WHERE id = 1")
        )
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Income record created with ID: {income_id}",
            "income_id": income_id,
            "invoice": {
                "id": invoice.id,
                "number": invoice.invoice_number,
                "amount": invoice.total_amount,
                "income_created": True
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        })
    
# Disabled: debug endpoint must not be exposed through the web application.
def view_invoice_1_debug():
    """
    Debug view for invoice 1 to check template rendering
    """
    from app import db
    from sqlalchemy import text
    
    try:
        # Get invoice with customer
        invoice_result = db.session.execute(
            text("""
                SELECT i.*, c.company_name, c.contact_person, c.trn 
                FROM invoice i 
                LEFT JOIN customer c ON i.customer_id = c.id 
                WHERE i.id = 1
            """)
        ).fetchone()
        
        if not invoice_result:
            return "Invoice not found"
        
        invoice_dict = dict(invoice_result._mapping)
        
        # Get items
        items_result = db.session.execute(
            text("SELECT * FROM invoice_item WHERE invoice_id = 1")
        ).fetchall()
        
        items_list = []
        for item in items_result:
            item_dict = dict(item._mapping)
            # Add calculated fields
            item_dict['line_total'] = float(item_dict['quantity']) * float(item_dict['unit_price'])
            items_list.append(item_dict)
        
        invoice_dict['items'] = items_list
        
        # Create a simple HTML output to see what we have
        html = f"""
        <html>
        <head>
            <title>Invoice Debug</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .success {{ color: green; }}
                .error {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>Invoice Debug</h1>
            
            <h2>Invoice Details</h2>
            <table>
                <tr><th>Field</th><th>Value</th></tr>
                <tr><td>ID</td><td>{invoice_dict.get('id')}</td></tr>
                <tr><td>Invoice Number</td><td>{invoice_dict.get('invoice_number')}</td></tr>
                <tr><td>Total Amount</td><td>AED {invoice_dict.get('total_amount', 0):,.2f}</td></tr>
                <tr><td>Status</td><td>{invoice_dict.get('status')}</td></tr>
            </table>
            
            <h2>Invoice Items (Count: {len(items_list)})</h2>
            """
        
        if items_list:
            html += """
            <table>
                <tr>
                    <th>Description</th>
                    <th>Quantity</th>
                    <th>Unit Price</th>
                    <th>Line Total</th>
                </tr>
            """
            
            for item in items_list:
                html += f"""
                <tr>
                    <td>{item.get('description', 'N/A')}</td>
                    <td>{item.get('quantity', 0)}</td>
                    <td>AED {item.get('unit_price', 0):,.2f}</td>
                    <td>AED {item.get('line_total', 0):,.2f}</td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += "<p class='error'>No items found!</p>"
            html += "<p>Checking database directly...</p>"
            
            # Try to see what's in the invoice_item table
            try:
                all_items = db.session.execute(
                    text("SELECT id, invoice_id, description FROM invoice_item LIMIT 10")
                ).fetchall()
                
                if all_items:
                    html += "<h3>First 10 items in invoice_item table:</h3>"
                    html += "<ul>"
                    for item in all_items:
                        html += f"<li>ID: {item.id}, Invoice: {item.invoice_id}, Desc: {item.description[:50]}...</li>"
                    html += "</ul>"
                else:
                    html += "<p>No items in invoice_item table at all!</p>"
            except:
                html += "<p class='error'>Error reading invoice_item table</p>"
        
        html += """
        </body>
        </html>
        """
        
        return html
        
    except Exception as e:
        return f"""
        <html>
        <body>
            <h1>Error</h1>
            <pre>{str(e)}</pre>
            <pre>{traceback.format_exc()}</pre>
        </body>
        </html>
        """
# Disabled: test endpoint must not be exposed through the web application.
def check_template_structure():
    """
    Check the current template structure
    """
    import os
    
    template_path = 'accounts/view_invoice.html'
    template_full_path = os.path.join(os.getcwd(), 'app', 'templates', template_path)
    
    try:
        with open(template_full_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Create a simple HTML response
        html_content = f"""
        <html>
        <head>
            <title>Template Check</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                pre {{ background: #f5f5f5; padding: 10px; border: 1px solid #ddd; overflow-x: auto; }}
                .success {{ color: green; }}
                .error {{ color: red; }}
                .warning {{ color: orange; }}
            </style>
        </head>
        <body>
            <h1>Template Structure Check</h1>
            <p><strong>Template path:</strong> {template_path}</p>
            <p><strong>Full path:</strong> {template_full_path}</p>
            
            <h2>Template Content Preview (first 3000 characters):</h2>
            <pre>{template_content[:3000]}</pre>
            
            <h2>Analysis:</h2>
            <ul>
        """
        
        # Check for common patterns
        checks = [
            ('invoice.items', 'invoice.items' in template_content),
            ('invoice[\'items\']', 'invoice[\'items\']' in template_content or 'invoice["items"]' in template_content),
            ('for item in', 'for item in' in template_content),
            ('item.description', 'item.description' in template_content),
            ('item.quantity', 'item.quantity' in template_content),
        ]
        
        for check_name, check_result in checks:
            status = '✓ Found' if check_result else '✗ Not found'
            color_class = 'success' if check_result else 'error'
            html_content += f'<li><span class="{color_class}">{status}: {check_name}</span></li>'
        
        html_content += """
            </ul>
            
            <h2>Quick Fix:</h2>
            <p>If items aren't showing, make sure your template contains code like this:</p>
            <pre>
{% if invoice.items %}
  {% for item in invoice.items %}
    <tr>
      <td>{{ item.description }}</td>
      <td>{{ item.quantity }}</td>
      <td>{{ item.unit_price }}</td>
    </tr>
  {% endfor %}
{% else %}
  <tr><td colspan="4">No items found</td></tr>
{% endif %}
            </pre>
            
            <h2>Actions:</h2>
            <ul>
                <li><a href="/invoices/1" target="_blank">View Invoice 1</a></li>
                <li><a href="/view-invoice-1-debug" target="_blank">Debug View</a></li>
                <li><a href="/debug-invoice-1" target="_blank">Debug Data</a></li>
            </ul>
        </body>
        </html>
        """
        
        return html_content
        
    except Exception as e:
        return f"""
        <html>
        <body>
            <h1>Error reading template</h1>
            <pre>{str(e)}</pre>
            <p>Full path: {template_full_path}</p>
        </body>
        </html>
        """
    
# Disabled: test endpoint must not be exposed through the web application.
def test_invoice_1_raw():
    """
    Show raw invoice 1 data in a simple table
    """
    from app import db
    from sqlalchemy import text
    
    try:
        # Get invoice data
        invoice_result = db.session.execute(
            text("SELECT * FROM invoice WHERE id = 1")
        ).fetchone()
        
        # Get items
        items_result = db.session.execute(
            text("SELECT * FROM invoice_item WHERE invoice_id = 1")
        ).fetchall()
        
        # Build HTML
        html = """
        <html>
        <head>
            <title>Invoice 1 Raw Data</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .data { background: #e8f4f8; padding: 10px; margin: 10px 0; }
            </style>
        </head>
        <body>
            <h1>Invoice 1 Raw Data Test</h1>
        """
        
        if invoice_result:
            invoice_dict = dict(invoice_result._mapping)
            html += f"""
            <h2>Invoice Data:</h2>
            <div class="data">
                <p><strong>Invoice Number:</strong> {invoice_dict.get('invoice_number', 'N/A')}</p>
                <p><strong>Status:</strong> {invoice_dict.get('status', 'N/A')}</p>
                <p><strong>Total Amount:</strong> {invoice_dict.get('total_amount', 'N/A')}</p>
                <p><strong>Items Count in DB:</strong> {len(items_result)}</p>
            </div>
            """
        else:
            html += "<p class='error'>Invoice not found!</p>"
        
        html += "<h2>Database Items:</h2>"
        if items_result:
            html += """
            <table>
                <tr>
                    <th>ID</th>
                    <th>Description</th>
                    <th>Quantity</th>
                    <th>Unit Price</th>
                    <th>VAT</th>
                </tr>
            """
            
            for item in items_result:
                item_dict = dict(item._mapping)
                html += f"""
                <tr>
                    <td>{item_dict.get('id', 'N/A')}</td>
                    <td>{item_dict.get('description', 'N/A')}</td>
                    <td>{item_dict.get('quantity', 'N/A')}</td>
                    <td>{item_dict.get('unit_price', 'N/A')}</td>
                    <td>{'Yes' if item_dict.get('is_vat') else 'No'}</td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += "<p class='error'>No items found in database!</p>"
        
        html += """
        <h2>What to check in your template:</h2>
        <ol>
            <li>Make sure you're using <code>invoice.items</code> (not <code>invoice['items']</code>)</li>
            <li>Check if there's a typo in your template variable names</li>
            <li>Try clearing browser cache (Ctrl+F5)</li>
            <li>Check Flask console for any errors</li>
        </ol>
        
        <h2>Quick Test Links:</h2>
        <ul>
            <li><a href="/invoices/1">View Invoice 1 Normally</a></li>
            <li><a href="/invoices/1?cache=clear">View with cache clear</a></li>
            <li><a href="/view-invoice-1-debug">Debug View</a></li>
        </ul>
        </body>
        </html>
        """
        
        return html
        
    except Exception as e:
        return f"""
        <html>
        <body>
            <h1>Error</h1>
            <pre>{str(e)}</pre>
        </body>
        </html>
        """

@invoices_bp.route('/invoices/<int:invoice_id>/record-income', methods=['GET', 'POST'])
@login_required
def record_invoice_income(invoice_id):
    """
    Record income for an invoice (one-time operation)
    GET: Show confirmation page
    POST: Record income
    """
    flash('Invoice income is created automatically when a payment is completed.', 'info')
    return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))

    # Retained below only as historical reference; direct invoice income is disabled.
    from app import db
    from app.models.finance.invoice import Invoice
    from app.models.wps.income import Income
    
    if request.method == 'GET':
        # Show confirmation page
        return render_template('accounts/confirm_record_income.html', invoice_id=invoice_id)
    
    # POST request - process income recording
    try:
        # Get invoice
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            flash('Invoice not found', 'danger')
            return redirect(url_for('invoices.list_invoices'))
        
        # Check if invoice is paid
        if invoice.status != 'paid' and invoice.amount_paid < invoice.total_amount:
            flash(f'Cannot record income for unpaid invoice (Status: {invoice.status}, Paid: {invoice.amount_paid}/{invoice.total_amount})', 'warning')
            return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
        
        # Check if income already exists
        existing_income = Income.query.filter_by(invoice_id=invoice_id).first()
        if existing_income:
            flash(f'Income already recorded for this invoice (Income ID: {existing_income.id})', 'info')
            return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
        
        # Create income record - FIXED: Use valid income type
        income = Income(
            income_type='other',  # Changed from 'invoice_payment' to 'other'
            amount=invoice.amount,
            tax_amount=invoice.vat_amount,
            total_amount=invoice.total_amount,
            currency='AED',
            income_date=invoice.issue_date.date() if invoice.issue_date else datetime.utcnow().date(),
            payment_received_date=datetime.utcnow().date(),
            description=f"Invoice Payment: {invoice.invoice_number} - {invoice.description or 'Transportation services'}",
            category='invoice',
            payment_method='bank_transfer',  # Default
            payment_reference=f'INV-{invoice.invoice_number}',
            customer_id=invoice.customer_id,
            customer_name=invoice.customer.company_name if invoice.customer else None,
            customer_contact=invoice.customer.contact_person if invoice.customer else None,
            customer_phone=invoice.customer.phone if invoice.customer else None,
            customer_trn=invoice.customer.trn if invoice.customer else None,
            customer_email=invoice.customer.email if invoice.customer else None,
            status='received',
            invoice_id=invoice_id,
            recorded_by=current_user.id if current_user else 1,
            reference_number=f"INV-{invoice.invoice_number}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )
        
        income.customer = invoice.customer
        income.invoice = invoice
        
        db.session.add(income)
        
        # Update invoice to mark income as created
        invoice.income_created = True
        db.session.commit()
        
        flash(f'Income recorded successfully for invoice {invoice.invoice_number} (Income ID: {income.id})', 'success')
        return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording income: {str(e)}', 'danger')
        return redirect(url_for('invoices.view_invoice_details', invoice_id=invoice_id))

@invoices_bp.route('/invoices/record-all-income', methods=['GET', 'POST'])
@login_required
def record_all_invoice_income():
    """
    Record income for all paid invoices that don't have income records
    GET: Show confirmation page
    POST: Process batch recording
    """
    flash('Invoice income is created automatically when payments are completed.', 'info')
    return redirect(url_for('invoices.list_invoices'))

    # Retained below only as historical reference; direct invoice income is disabled.
    from app import db
    from app.models.finance.invoice import Invoice
    from app.models.wps.income import Income
    
    if request.method == 'GET':
        # Show confirmation page
        return render_template('accounts/confirm_record_all_income.html')
    
    # POST request - process batch recording
    try:
        # Get all paid invoices without income records
        invoices = Invoice.query.filter(
            Invoice.status == 'paid',
            Invoice.income_created == False,
            Invoice.total_amount > 0
        ).all()
        
        results = {
            "total_invoices": len(invoices),
            "processed": 0,
            "created": 0,
            "skipped": 0,
            "errors": 0,
            "details": []
        }
        
        for invoice in invoices:
            try:
                # Check if income already exists
                existing_income = Income.query.filter_by(invoice_id=invoice.id).first()
                if existing_income:
                    # Update the invoice flag
                    invoice.income_created = True
                    results["skipped"] += 1
                    results["details"].append({
                        "invoice": invoice.invoice_number,
                        "status": "skipped",
                        "reason": "Income already exists",
                        "income_id": existing_income.id
                    })
                    continue
                
                # Create income record - FIXED: Use valid income type
                income = Income(
                    income_type='other',  # Changed from 'invoice_payment' to 'other'
                    amount=invoice.amount,
                    tax_amount=invoice.vat_amount,
                    total_amount=invoice.total_amount,
                    currency='AED',
                    income_date=invoice.issue_date.date() if invoice.issue_date else datetime.utcnow().date(),
                    payment_received_date=datetime.utcnow().date(),
                    description=f"Invoice Payment: {invoice.invoice_number}",
                    category='invoice',
                    payment_method='bank_transfer',
                    payment_reference=f'BATCH-INV-{invoice.invoice_number}',
                    customer_id=invoice.customer_id,
                    customer_name=invoice.customer.company_name if invoice.customer else None,
                    customer_contact=invoice.customer.contact_person if invoice.customer else None,
                    status='received',
                    invoice_id=invoice.id,
                    recorded_by=current_user.id if current_user else 1,
                    reference_number=f"INV-{invoice.invoice_number}-BATCH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                )
                
                income.customer = invoice.customer
                income.invoice = invoice
                
                db.session.add(income)
                invoice.income_created = True
                
                results["created"] += 1
                results["details"].append({
                    "invoice": invoice.invoice_number,
                    "status": "created",
                    "income_id": income.id,
                    "amount": income.total_amount
                })
                
            except Exception as e:
                results["errors"] += 1
                results["details"].append({
                    "invoice": invoice.invoice_number,
                    "status": "error",
                    "error": str(e)
                })
                print(f"Error processing invoice {invoice.invoice_number}: {e}")
        
        db.session.commit()
        results["processed"] = results["created"] + results["skipped"] + results["errors"]
        
        flash(f'Processed {results["processed"]} invoices. Created {results["created"]} income records.', 'success')
        
        # Show detailed results
        return render_template('accounts/batch_income_results.html', results=results)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error in batch income recording: {str(e)}', 'danger')
        return redirect(url_for('invoices.list_invoices'))

@invoices_bp.route('/invoices/<int:invoice_id>/check-income-status', methods=['GET'])
@login_required
def check_income_status(invoice_id):
    """
    Check income status for an invoice (GET only)
    """
    from app import db
    from app.models.finance.invoice import Invoice
    from app.models.wps.income import Income
    
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({"error": "Invoice not found"}), 404
        
        # Get existing incomes
        existing_incomes = Income.query.filter_by(invoice_id=invoice_id).all()
        
        return jsonify({
            "invoice": {
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "status": invoice.status,
                "amount_paid": invoice.amount_paid,
                "total_amount": invoice.total_amount,
                "income_created": invoice.income_created,
                "is_fully_paid": invoice.amount_paid >= invoice.total_amount
            },
            "existing_incomes": [{
                "id": inc.id,
                "reference_number": inc.reference_number,
                "total_amount": inc.total_amount,
                "status": inc.status,
                "created_at": inc.created_at.isoformat() if inc.created_at else None
            } for inc in existing_incomes],
            "can_record_income": invoice.amount_paid >= invoice.total_amount and not invoice.income_created,
            "reason": "Invoice is not fully paid" if invoice.amount_paid < invoice.total_amount 
                     else "Income already recorded" if invoice.income_created 
                     else "Income can be recorded"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Disabled: test endpoint must not be exposed through the web application.
@login_required
def test_income_logic(invoice_id):
    """
    Test income creation logic for an invoice
    """
    from app import db
    from app.models.finance.invoice import Invoice
    
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({"error": "Invoice not found"})
        
        # Test data
        test_data = {
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
            "amount_paid": invoice.amount_paid,
            "total_amount": invoice.total_amount,
            "income_created": invoice.income_created,
            "can_record_income": False,
            "reason": ""
        }
        
        # Check if income can be recorded
        if invoice.income_created:
            test_data["can_record_income"] = False
            test_data["reason"] = "Income already recorded"
        elif invoice.status == 'paid' or invoice.amount_paid >= invoice.total_amount:
            test_data["can_record_income"] = True
            test_data["reason"] = "Invoice is paid and income not recorded"
        else:
            test_data["can_record_income"] = False
            test_data["reason"] = "Invoice is not fully paid"
        
        return jsonify({
            "test_results": test_data,
            "action": "To record income, use: POST /invoices/{}/record-income".format(invoice_id)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})