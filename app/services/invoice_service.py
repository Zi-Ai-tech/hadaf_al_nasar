from app import db
from app.models import Invoice, Customer
from app.schemas import InvoiceSchema
from app.exceptions import ValidationError, DatabaseError
from app.constants import VAT_PERCENTAGE
from datetime import datetime

invoice_schema = InvoiceSchema()

class InvoiceService:
    @staticmethod
    def get_all_invoices(invoice_type=None):
        """Get all invoices, optionally filtered by type"""
        try:
            query = Invoice.query
            if invoice_type in ['vat', 'non_vat']:
                query = query.filter_by(invoice_type=invoice_type)
            return query.all()
        except Exception as e:
            raise DatabaseError(f"Error retrieving invoices: {str(e)}")

    @staticmethod
    def get_invoice_by_id(invoice_id):
        """Get invoice by ID"""
        try:
            return Invoice.query.get_or_404(invoice_id)
        except Exception as e:
            raise DatabaseError(f"Error retrieving invoice: {str(e)}")

from datetime import datetime

class InvoiceService:
    @staticmethod
    def generate_invoice_number():
        """Generate unique invoice number in format: HNT-DDD-MMM-YYY with counter if needed"""
        now = datetime.now()
    
        # Day of year (001-366)
        day_of_year = now.timetuple().tm_yday
        day_str = f"{day_of_year:03d}"
    
        # Month abbreviation
        month_abbr = now.strftime('%b').upper()
    
        # Last 3 digits of year
        year_short = now.strftime('%y')  # Gets '25' for 2025
        year_str = f"0{year_short}" if len(year_short) == 2 else year_short
    
        base_number = f"HNT-{day_str}-{month_abbr}-{year_str}"
    
        # Check if base number already exists
        existing_invoice = Invoice.query.filter(Invoice.invoice_number.like(f"{base_number}%")).first()
    
        if not existing_invoice:
            return base_number
    
        # If base number exists, find the highest counter and increment
        existing_numbers = Invoice.query.filter(Invoice.invoice_number.like(f"{base_number}%")).all()
    
        counters = []
        for invoice in existing_numbers:
            if invoice.invoice_number == base_number:
                counters.append(0)  # No counter means counter 0
            else:
            # Extract counter from numbers like HNT-308-NOV-025-1, HNT-308-NOV-025-2, etc.
                try:
                    counter_part = invoice.invoice_number.replace(f"{base_number}-", "")
                    counter = int(counter_part)
                    counters.append(counter)
                except (ValueError, AttributeError):
                    counters.append(0)
    
        next_counter = max(counters) + 1 if counters else 1
        return f"{base_number}-{next_counter}"


    @staticmethod
    def create_invoice(data):
        """Create a new invoice with validation"""
        try:
            # Check if customer exists
            customer = Customer.query.get(data['customer_id'])
            if not customer:
                raise ValidationError("Customer does not exist")

            # Generate unique invoice number
            invoice_number = InvoiceService.generate_invoice_number()
            
            # Check if this invoice number already exists (unlikely but safe)
            existing_invoice = Invoice.query.filter_by(invoice_number=invoice_number).first()
            if existing_invoice:
                # If by chance it exists, add a suffix
                counter = 1
                while existing_invoice:
                    new_number = f"{invoice_number}-{counter:02d}"
                    existing_invoice = Invoice.query.filter_by(invoice_number=new_number).first()
                    if not existing_invoice:
                        invoice_number = new_number
                    counter += 1

            # Calculate amounts
            amount = float(data['amount'])
            if data['invoice_type'] == 'vat':
                vat_amount = amount * 0.05  # 5% VAT
                total_amount = amount + vat_amount
            else:
                vat_amount = 0
                total_amount = amount

            # Create invoice
            invoice = Invoice(
                customer_id=data['customer_id'],
                invoice_number=invoice_number,  # Use auto-generated number
                invoice_type=data['invoice_type'],
                description=data.get('description', ''),
                issue_date=datetime.strptime(data['issue_date'], '%Y-%m-%d'),
                due_date=datetime.strptime(data['due_date'], '%Y-%m-%d'),
                # New invoices must always start as 'pending', regardless of
                # what the caller passes in. Status can only move to 'paid'
                # (or 'partial') through an actual payment action, which is
                # also responsible for updating amount_paid and recording
                # income. Accepting a client-supplied status here allowed
                # invoices to be created already 'paid' with amount_paid = 0
                # and no income recorded.
                status='pending',
                amount=amount,
                vat_amount=vat_amount,
                total_amount=total_amount
            )
            
            db.session.add(invoice)
            db.session.commit()
            return invoice
            
        except Exception as e:
            db.session.rollback()
            raise DatabaseError(f"Error creating invoice: {str(e)}")
    
    @staticmethod
    def update_invoice(invoice_id, data):
        """Update invoice details"""
        invoice = Invoice.query.get_or_404(invoice_id)
        
        # Validate input data
        errors = invoice_schema.validate(data, partial=True)
        if errors:
            raise ValidationError(f"Invalid invoice data: {errors}")

        try:
            for key, value in data.items():
                if hasattr(invoice, key):
                    setattr(invoice, key, value)
            
            # Recalculate VAT if amount changed
            if 'amount' in data and invoice.invoice_type == 'vat':
                invoice.vat_amount = invoice.amount * (VAT_PERCENTAGE / 100)
                invoice.total_amount = invoice.amount + invoice.vat_amount
            
            db.session.commit()
            return invoice
        except Exception as e:
            db.session.rollback()
            raise DatabaseError(f"Error updating invoice: {str(e)}")

    @staticmethod
    def mark_invoice_paid(invoice_id):
        """Mark invoice as paid"""
        try:
            invoice = Invoice.query.get_or_404(invoice_id)
            invoice.status = 'paid'
            db.session.commit()
            return invoice
        except Exception as e:
            db.session.rollback()
            raise DatabaseError(f"Error marking invoice as paid: {str(e)}")

    @staticmethod
    def delete_invoice(invoice_id):
        """Delete an invoice"""
        try:
            invoice = Invoice.query.get_or_404(invoice_id)
            
            # Check for related payments
            from app.models import Payment
            has_payments = db.session.query(Payment.query.filter_by(invoice_id=invoice_id).exists()).scalar()
            
            if has_payments:
                raise ValidationError("Cannot delete invoice with existing payments")
            
            db.session.delete(invoice)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            if isinstance(e, ValidationError):
                raise e
            raise DatabaseError(f"Error deleting invoice: {str(e)}")