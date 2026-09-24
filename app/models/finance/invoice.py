from app import db
from app.models.core.base import BaseModel, SoftDeleteMixin
from datetime import datetime
from sqlalchemy.orm import relationship, validates
from decimal import Decimal
from sqlalchemy import text


class Invoice(BaseModel, SoftDeleteMixin):
    """
    Invoice model for financial transactions
    Handles both VAT and non-VAT invoices with itemized billing
    """
    __tablename__ = 'invoice'

    OUTSTANDING_STATUSES = ('pending', 'sent', 'partial', 'overdue')
    
    # Invoice Identification
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    invoice_type = db.Column(db.String(20), default='vat', nullable=False)  # vat, commercial, proforma
    reference_number = db.Column(db.String(100), nullable=True)  # External reference
    
    # Dates
    issue_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    due_date = db.Column(db.DateTime, nullable=True)
    
    # Financial Amounts
    amount = db.Column(db.Float, default=0.0, nullable=False)  # Subtotal without VAT
    vat_amount = db.Column(db.Float, default=0.0, nullable=False)
    total_amount = db.Column(db.Float, default=0.0, nullable=False)
    amount_paid = db.Column(db.Float, default=0.0, nullable=False)
    
    # Status and Tracking
    status = db.Column(db.String(20), default='draft', nullable=False)  # draft, pending, sent, partial, paid, overdue, cancelled
    payment_terms = db.Column(db.String(50), default='NET30')  # NET30, NET15, Due on receipt
    description = db.Column(db.Text, nullable=True)
    
    # Foreign Keys
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipment.id'), nullable=True)
    income_created = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relationships - SINGLE RELATIONSHIP PER FOREIGN KEY
    customer = relationship("Customer", back_populates="invoices")
    shipment = relationship("Shipment", uselist=False)
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")
    invoice_incomes = relationship("Income", back_populates="invoice", cascade="all, delete-orphan")
    
    def __init__(self, **kwargs):
        """
        Initialize invoice with automatic number generation if not provided
        """
        if 'invoice_number' not in kwargs:
            kwargs['invoice_number'] = self.generate_invoice_number()
        super().__init__(**kwargs)
    
    @validates('invoice_number')
    def validate_invoice_number(self, key, invoice_number):
        """Validate invoice number uniqueness"""
        if not invoice_number:
            raise ValueError("Invoice number cannot be empty")
        return invoice_number
    
    def generate_invoice_number(self):
        """
        Generate a unique invoice number in format: HNT-YYY-MMM-01
        Where:
        - HNT: Company short name
        - YYY: Last 3 digits of year (025 for 2025)
        - MMM: 3-letter month abbreviation (NOV for November)
        - 01: Sequence number (unique for each invoice in that month)
        """
        now = datetime.utcnow()
        
        # Format components
        company_short = "HNT"
        year_short = str(now.year)[-3:]  # Last 3 digits of year
        month_short = now.strftime('%b').upper()  # 3-letter month in uppercase
        
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
            # Extract the sequence number from the existing invoice number
            last_number = result[0]
            try:
                # Extract the last part after the last dash
                last_seq = int(last_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        # Format the sequence number with leading zeros (01, 02, ..., 10, 11, etc.)
        new_invoice_number = f"{base_number}-{next_seq:02d}"
        
        # Double-check it doesn't exist (race condition protection)
        check_result = db.session.execute(
            text("SELECT id FROM invoice WHERE invoice_number = :invoice_number"),
            {'invoice_number': new_invoice_number}
        ).fetchone()
        
        if check_result:
            # If it exists (unlikely), try next sequence
            return f"{base_number}-{next_seq + 1:02d}"
        
        print(f"=== DEBUG: Generated invoice number: {new_invoice_number} ===")
        return new_invoice_number
    
    @property
    def is_vat_invoice(self):
        """Check if this is a VAT invoice"""
        return self.invoice_type == 'vat'
    
    @property
    def is_paid(self):
        """Check if invoice is fully paid"""
        return self.status == 'paid' or self.amount_paid >= self.total_amount
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        if self.due_date and self.status not in ['paid', 'cancelled']:
            return datetime.utcnow() > self.due_date
        return False
    
    @property
    def balance_due(self):
        """Calculate remaining balance"""
        return max(0, self.total_amount - self.amount_paid)
    
    @property
    def days_overdue(self):
        """Calculate number of days overdue"""
        if self.is_overdue and self.due_date:
            return (datetime.utcnow() - self.due_date).days
        return 0
    
    def recalc_totals(self):
        """
        Recalculate invoice totals from items
        """
        subtotal = 0
        vat_total = 0
        
        for item in self.items:
            item_subtotal = item.quantity * item.unit_price
            subtotal += item_subtotal
            
            if item.is_vat and self.is_vat_invoice:
                vat_total += item_subtotal * 0.05  # UAE VAT rate 5%
        
        self.amount = subtotal
        self.vat_amount = vat_total
        self.total_amount = subtotal + vat_total
        
        # Update paid status
        if self.amount_paid >= self.total_amount and self.total_amount > 0:
            self.status = 'paid'
        elif self.is_overdue:
            self.status = 'overdue'
    
    def add_item(self, description, unit_price, quantity=1, is_vat=True):
        """
        Add item to invoice
        
        Args:
            description (str): Item description
            unit_price (float): Unit price
            quantity (int): Quantity
            is_vat (bool): Whether VAT applies
            
        Returns:
            InvoiceItem: Created item
        """
        item = InvoiceItem(
            invoice=self,
            description=description,
            unit_price=unit_price,
            quantity=quantity,
            is_vat=is_vat
        )
        
        self.items.append(item)
        self.recalc_totals()
        self.save()
        
        return item
    
    def remove_item(self, item_id):
        """
        Remove item from invoice
        
        Args:
            item_id (int): Item ID to remove
            
        Returns:
            bool: True if removed successfully
        """
        item = next((item for item in self.items if item.id == item_id), None)
        if item:
            db.session.delete(item)
            self.recalc_totals()
            return self.save()
        return False
    
    def mark_as_sent(self):
        """
        Mark invoice as sent to customer
        """
        if self.status == 'draft':
            self.status = 'sent'
            return self.save()
        return False
    
    def mark_as_paid(self, payment_method=None, payment_reference=None, recorded_by=None):
        """
        Record the remaining balance as one completed payment.
        """
        if self.status == 'paid':
            return True  # Already paid

        balance_due = self.balance_due
        if balance_due <= 0:
            self.status = 'paid'
            return self.save()

        self.add_payment(
            amount=balance_due,
            payment_method=payment_method or 'bank_transfer',
            reference_number=payment_reference or self.reference_number,
            recorded_by=recorded_by,
        )
        return True
    
    def add_payment(self, amount, payment_method, reference_number=None, notes=None, recorded_by=None):
        """
        Add a completed payment and its corresponding income record.
        """
        from app.models.finance.payment import Payment

        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        if amount > self.balance_due + 0.01:
            raise ValueError("Payment amount exceeds the invoice balance")

        # Create payment record
        payment = Payment(
            invoice_id=self.id,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes,
            payment_date=datetime.utcnow(),
            recorded_by=recorded_by,
            status='completed'
        )

        db.session.add(payment)
        db.session.flush()
        self.amount_paid += amount

        from app.services.income_service import IncomeService
        IncomeService.create_income_from_payment(payment, recorded_by=recorded_by)

        # Update invoice status
        if self.amount_paid >= self.total_amount:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        else:
            self.status = 'sent'

        self.income_created = self.amount_paid >= self.total_amount

        db.session.commit()
        return payment
    
    def cancel(self, reason=None):
        """
        Cancel invoice
        
        Args:
            reason (str): Cancellation reason
            
        Returns:
            bool: True if cancelled successfully
        """
        if self.status not in ['paid', 'cancelled']:
            self.status = 'cancelled'
            if reason:
                self.notes = f"{self.notes or ''}\nCancelled: {reason}".strip()
            return self.save()
        return False
    
    def get_payment_summary(self):
        """
        Get payment summary for the invoice
        
        Returns:
            dict: Payment summary
        """
        payment_percentage = 0
        if self.total_amount > 0:
            payment_percentage = (self.amount_paid / self.total_amount * 100)
        
        last_payment_date = None
        if self.payments:
            last_payment_date = max([p.payment_date for p in self.payments])
        
        return {
            'total_amount': self.total_amount,
            'amount_paid': self.amount_paid,
            'balance_due': self.balance_due,
            'payment_percentage': payment_percentage,
            'payments_count': len(self.payments),
            'last_payment_date': last_payment_date
        }
    
    def verify_income_records(self):
        """
        Verify and sync income records with payments
        Returns True if income records match payments
        """
        total_income_amount = sum(income.total_amount for income in self.invoice_incomes)
        total_payment_amount = sum(payment.amount for payment in self.payments if payment.is_completed)
    
        # Check if income matches payments
        if abs(total_income_amount - total_payment_amount) > 0.01:  # Allow small rounding differences
            return False
    
        # Check if income_created flag matches reality
        if self.amount_paid >= self.total_amount and not self.income_created:
            self.income_created = True
            self.save()
    
        return True

    def sync_income_from_payments(self, recorded_by=None):
        """
        Create missing income records from payments
        Useful for fixing historical data
        """
        from app.services.income_service import IncomeService
    
        created_count = 0
        if any(income.payment_id is None for income in self.invoice_incomes):
            return 0

        for payment in self.payments:
            if not payment.is_completed:
                continue
            
            if payment.income:
                continue

            IncomeService.create_income_from_payment(
                payment,
                recorded_by=recorded_by or payment.recorded_by,
            )
            created_count += 1
    
        if created_count > 0:
            db.session.commit()
    
        return created_count
    
    def to_dict(self, include_items=True, include_payments=False, include_income_info=True):
        """
        Convert invoice to dictionary
        
        Args:
            include_items (bool): Include invoice items
            include_payments (bool): Include payment details
            
        Returns:
            dict: Invoice data
        """
        data = super().to_dict()
        
        # Add computed properties
        data['is_vat_invoice'] = self.is_vat_invoice
        data['is_paid'] = self.is_paid
        data['is_overdue'] = self.is_overdue
        data['balance_due'] = self.balance_due
        data['days_overdue'] = self.days_overdue
        
        # Format dates
        if self.issue_date:
            data['issue_date'] = self.issue_date.isoformat()
        if self.due_date:
            data['due_date'] = self.due_date.isoformat()
        
        # Include related data
        if include_items:
            data['items'] = [item.to_dict() for item in self.items]
        
        if include_payments:
            data['payments'] = [payment.to_dict() for payment in self.payments]
            data['payment_summary'] = self.get_payment_summary()
        
        # Include income information
        if include_income_info:
            data['incomes'] = [income.to_dict() for income in self.invoice_incomes]
            data['total_income_received'] = sum(income.total_amount for income in self.invoice_incomes)
            data['income_created'] = self.income_created
        
        return data
        
        # Include customer basic info
        if self.customer:
            data['customer_name'] = self.customer.company_name
            data['customer_trn'] = self.customer.trn
        
        return data
    
    @classmethod
    def get_by_number(cls, invoice_number):
        """
        Get invoice by invoice number
        
        Args:
            invoice_number (str): Invoice number
            
        Returns:
            Invoice: Invoice instance or None
        """
        return cls.query.filter_by(invoice_number=invoice_number).first()
    
    @classmethod
    def get_overdue_invoices(cls):
        """
        Get all overdue invoices
        
        Returns:
            list: List of overdue invoices
        """
        return cls.query.filter(
            cls.status.notin_(['paid', 'cancelled']),
            cls.due_date < datetime.utcnow()
        ).all()

    @classmethod
    def sync_overdue_statuses(cls):
        """Persist overdue status for unpaid invoices past their due date."""
        overdue_invoices = cls.query.filter(
            cls.status.in_(['pending', 'sent', 'partial']),
            cls.due_date.isnot(None),
            cls.due_date < datetime.utcnow(),
        ).all()

        for invoice in overdue_invoices:
            invoice.status = 'overdue'

        if overdue_invoices:
            db.session.commit()

        return len(overdue_invoices)
    
    @classmethod
    def get_invoices_by_status(cls, status):
        """
        Get invoices by status
        
        Args:
            status (str): Invoice status
            
        Returns:
            list: List of invoices with specified status
        """
        return cls.query.filter_by(status=status).order_by(cls.issue_date.desc()).all()
    
    @classmethod
    def get_customer_invoices(cls, customer_id, status=None):
        """
        Get invoices for a specific customer
        
        Args:
            customer_id (int): Customer ID
            status (str): Filter by status
            
        Returns:
            list: List of customer invoices
        """
        query = cls.query.filter_by(customer_id=customer_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(cls.issue_date.desc()).all()
    
    @classmethod
    def get_total_outstanding(cls, customer_id=None):
        """
        Get total outstanding amount
        
        Args:
            customer_id (int): Optional customer filter
            
        Returns:
            float: Total outstanding amount
        """
        query = cls.query.filter(cls.status.in_(cls.OUTSTANDING_STATUSES))
        
        if customer_id:
            query = query.filter_by(customer_id=customer_id)
        
        invoices = query.all()
        return sum(invoice.balance_due for invoice in invoices)
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number} - {self.total_amount} AED>'


class InvoiceItem(BaseModel):
    """
    Invoice line items for detailed billing
    """
    __tablename__ = 'invoice_item'
    
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    is_vat = db.Column(db.Boolean, default=True, nullable=False)  # Whether VAT applies to this item
    
    # Single relationship to invoice
    invoice = relationship("Invoice", back_populates="items")
    
    @property
    def line_total(self):
        """Calculate line total without VAT"""
        return self.quantity * self.unit_price
    
    @property
    def line_total_with_vat(self):
        """Calculate line total with VAT if applicable"""
        total = self.line_total
        if self.is_vat:
            total *= 1.05  # UAE VAT rate 5%
        return total
    
    @property
    def vat_amount(self):
        """Calculate VAT amount for this line"""
        if self.is_vat:
            return self.line_total * 0.05
        return 0
    
    def to_dict(self):
        """
        Convert invoice item to dictionary
        
        Returns:
            dict: Item data
        """
        return {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'description': self.description,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'is_vat': self.is_vat,
            'line_total': self.line_total,
            'line_total_with_vat': self.line_total_with_vat,
            'vat_amount': self.vat_amount,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<InvoiceItem {self.description} - {self.quantity} x {self.unit_price}>'