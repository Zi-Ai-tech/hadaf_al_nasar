"""
Payment model for tracking financial transactions
Handles payments against invoices with multiple payment methods
"""
from app import db
from app.models.core.base import BaseModel
from datetime import datetime
from sqlalchemy.orm import relationship, validates
from decimal import Decimal


class Payment(BaseModel):
    """
    Payment model for tracking financial transactions
    Handles payments against invoices with multiple payment methods
    """
    __tablename__ = 'payment'

    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), nullable=True)
    
    # Payment Identification
    payment_reference = db.Column(db.String(100), unique=True, nullable=True, index=True)
    
    # Payment Details
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # cash, bank_transfer, card, cheque, online
    payment_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    currency = db.Column(db.String(3), default='AED', nullable=False)  # AED, USD, etc.
    exchange_rate = db.Column(db.Float, default=1.0)  # For foreign currency payments
    
    # Payment Status and Tracking
    status = db.Column(db.String(20), default='completed', nullable=False)  # pending, completed, failed, refunded, cancelled
    processed_date = db.Column(db.DateTime, nullable=True)  # When payment was actually processed
    
    # Reference Information
    reference_number = db.Column(db.String(100), nullable=True)  # Bank reference, transaction ID, etc.
    cheque_number = db.Column(db.String(50), nullable=True)  # For cheque payments
    bank_name = db.Column(db.String(100), nullable=True)  # For bank transfers
    card_last_four = db.Column(db.String(4), nullable=True)  # For card payments
    card_type = db.Column(db.String(20), nullable=True)  # visa, mastercard, etc.
    
    # Additional Information
    notes = db.Column(db.Text, nullable=True)
    attachment_url = db.Column(db.String(500), nullable=True)  # For payment proof/document
    
    # Foreign Keys
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Who recorded the payment
    
    # FIXED: Relationships
    invoice = relationship('Invoice', back_populates='payments')  # Fixed relationship
    income = relationship('Income', back_populates='payment', uselist=False)
    payment_recorder = relationship('User', 
                                backref='recorded_payments', 
                                foreign_keys=[recorded_by],
                                primaryjoin='Payment.recorded_by == User.id',
                                lazy='joined')
       
    def __init__(self, **kwargs):
        """
        Initialize payment with automatic reference generation if not provided
        """
        if 'payment_reference' not in kwargs:
            kwargs['payment_reference'] = self.generate_payment_reference()
        super().__init__(**kwargs)
    
    @validates('amount')
    def validate_amount(self, key, amount):
        """Validate payment amount"""
        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        return float(amount)
    
    @validates('payment_method')
    def validate_payment_method(self, key, method):
        """Validate payment method"""
        valid_methods = ['cash', 'bank_transfer', 'card', 'cheque', 'online', 'wallet']
        if method not in valid_methods:
            raise ValueError(f"Invalid payment method. Must be one of: {valid_methods}")
        return method
    
    @property
    def is_completed(self):
        """Check if payment is completed"""
        return self.status == 'completed'
    
    @property
    def is_pending(self):
        """Check if payment is pending"""
        return self.status == 'pending'
    
    @property
    def is_refunded(self):
        """Check if payment was refunded"""
        return self.status == 'refunded'
    
    @property
    def is_failed(self):
        """Check if payment failed"""
        return self.status == 'failed'
    
    @property
    def amount_in_default_currency(self):
        """Convert amount to default currency (AED)"""
        return self.amount * self.exchange_rate
    
    @property
    def payment_method_display(self):
        """Get display name for payment method"""
        method_names = {
            'cash': 'Cash',
            'bank_transfer': 'Bank Transfer',
            'cheque': 'Cheque',
            'card': 'Credit/Debit Card',
            'online': 'Online Payment',
            'wallet': 'Digital Wallet'
        }
        return method_names.get(self.payment_method, self.payment_method.title())
    
    def generate_payment_reference(self):
        """
        Generate automatic payment reference
        Format: PAY-YYYY-MM-DD-HHMMSSffffff
        """
        from datetime import datetime
        now = datetime.utcnow()
        return f"PAY-{now.strftime('%Y-%m-%d-%H%M%S%f')}"
    
    def mark_completed(self, processed_date=None):
        """
        Mark payment as completed
    
        Args:
            processed_date (datetime): When payment was processed
        
        Returns:
            bool: True if status was updated
        """
        if self.status == 'completed':
            return False

        self.status = 'completed'
        self.processed_date = processed_date or datetime.utcnow()

        if self.invoice:
            if self.amount > self.invoice.balance_due + 0.01:
                raise ValueError("Payment amount exceeds the invoice balance")
            self.invoice.amount_paid += self.amount
            from app.services.income_service import IncomeService
            IncomeService.create_income_from_payment(self, recorded_by=self.recorded_by)
            if self.invoice.amount_paid >= self.invoice.total_amount:
                self.invoice.status = 'paid'
                self.invoice.income_created = True
            else:
                self.invoice.status = 'partial'

        return self.save()
        return False
    
    def mark_failed(self, reason=None):
        """
        Mark payment as failed
        
        Args:
            reason (str): Failure reason
            
        Returns:
            bool: True if status was updated
        """
        was_completed = self.status == 'completed'
        if self.status not in ['completed', 'refunded']:
            self.status = 'failed'
            if reason:
                self.notes = f"{self.notes or ''}\nFailed: {reason}".strip()
            
            # Reverse invoice payment if it was previously applied
            if self.invoice and was_completed:
                self.invoice.amount_paid -= self.amount
                self.invoice.recalc_totals()
            
            return self.save()
        return False
    
    def refund(self, refund_amount=None, reason=None):
        """
        Process refund for this payment
        
        Args:
            refund_amount (float): Amount to refund (defaults to full amount)
            reason (str): Refund reason
            
        Returns:
            bool: True if refund was processed
        """
        if self.status != 'completed':
            return False
        
        refund_amount = refund_amount or self.amount
        
        if refund_amount > self.amount:
            raise ValueError("Refund amount cannot exceed original payment amount")
        
        # Create refund record
        refund = Refund(
            payment_id=self.id,
            amount=refund_amount,
            reason=reason or "Payment refund",
            refund_date=datetime.utcnow()
        )
        
        # Update payment status
        if refund_amount == self.amount:
            self.status = 'refunded'
        else:
            self.status = 'partial_refund'
        
        # Update invoice
        if self.invoice:
            self.invoice.amount_paid -= refund_amount
            self.invoice.recalc_totals()
        
        db.session.add(refund)
        return self.save()
    
    def update_invoice_status(self):
        """
        Update related invoice status based on this payment
        """
        if self.invoice and self.is_completed:
            self.invoice.amount_paid += self.amount
            
            if self.invoice.amount_paid >= self.invoice.total_amount:
                self.invoice.status = 'paid'
            elif self.invoice.amount_paid > 0:
                self.invoice.status = 'partial'
            
            self.invoice.save()
    
    def to_dict(self, include_invoice=False, include_refunds=False):
        """
        Convert payment to dictionary
        
        Args:
            include_invoice (bool): Include basic invoice info
            include_refunds (bool): Include refund history
            
        Returns:
            dict: Payment data
        """
        data = super().to_dict()
        
        # Add computed properties
        data['is_completed'] = self.is_completed
        data['is_pending'] = self.is_pending
        data['is_refunded'] = self.is_refunded
        data['is_failed'] = self.is_failed
        data['amount_in_default_currency'] = self.amount_in_default_currency
        data['payment_method_display'] = self.payment_method_display
        
        # Format dates
        if self.payment_date:
            data['payment_date'] = self.payment_date.isoformat()
        if self.processed_date:
            data['processed_date'] = self.processed_date.isoformat()
        
        # Include related data
        if include_invoice and self.invoice:
            data['invoice'] = {
                'id': self.invoice.id,
                'invoice_number': self.invoice.invoice_number,
                'total_amount': self.invoice.total_amount,
                'customer_name': self.invoice.customer.company_name if self.invoice.customer else None
            }
        
        if include_refunds:
            data['refunds'] = [refund.to_dict() for refund in self.refunds]
        
        # Include recorder info
        if self.payment_recorder:
           data['recorded_by_name'] = self.payment_recorder.full_name
        else:
            data['recorded_by_name'] = None
        return data
    
    def get_payment_proof_info(self):
        """
        Get payment proof information based on payment method
        
        Returns:
            dict: Payment proof details
        """
        proof_info = {
            'method': self.payment_method,
            'reference': self.reference_number,
            'amount': self.amount,
            'date': self.payment_date
        }
        
        if self.payment_method == 'bank_transfer':
            proof_info.update({
                'bank_name': self.bank_name,
                'reference_number': self.reference_number
            })
        elif self.payment_method == 'cheque':
            proof_info.update({
                'cheque_number': self.cheque_number,
                'bank_name': self.bank_name
            })
        elif self.payment_method == 'card':
            proof_info.update({
                'card_type': self.card_type,
                'card_last_four': self.card_last_four
            })
        
        return proof_info
    
    @classmethod
    def get_by_reference(cls, reference):
        """
        Get payment by reference number
        
        Args:
            reference (str): Payment reference
            
        Returns:
            Payment: Payment instance or None
        """
        return cls.query.filter_by(payment_reference=reference).first()
    
    @classmethod
    def get_payments_by_method(cls, method, start_date=None, end_date=None):
        """
        Get payments by payment method within date range
        
        Args:
            method (str): Payment method
            start_date (datetime): Start date filter
            end_date (datetime): End date filter
            
        Returns:
            list: List of payments
        """
        query = cls.query.filter_by(payment_method=method, status='completed')
        
        if start_date:
            query = query.filter(cls.payment_date >= start_date)
        if end_date:
            query = query.filter(cls.payment_date <= end_date)
        
        return query.order_by(cls.payment_date.desc()).all()
    
    @classmethod
    def get_payments_by_invoice(cls, invoice_id):
        """
        Get all payments for a specific invoice
        
        Args:
            invoice_id (int): Invoice ID
            
        Returns:
            list: List of payments for the invoice
        """
        return cls.query.filter_by(
            invoice_id=invoice_id
        ).order_by(cls.payment_date.desc()).all()
    
    @classmethod
    def get_total_payments(cls, start_date=None, end_date=None, method=None):
        """
        Get total payments amount within date range
        
        Args:
            start_date (datetime): Start date filter
            end_date (datetime): End date filter
            method (str): Payment method filter
            
        Returns:
            float: Total payments amount
        """
        query = cls.query.filter_by(status='completed')
        
        if method:
            query = query.filter_by(payment_method=method)
        if start_date:
            query = query.filter(cls.payment_date >= start_date)
        if end_date:
            query = query.filter(cls.payment_date <= end_date)
        
        payments = query.all()
        return sum(payment.amount_in_default_currency for payment in payments)
    
    @classmethod
    def get_payment_summary(cls, start_date, end_date):
        """
        Get payment summary by method for a date range
        
        Args:
            start_date (datetime): Start date
            end_date (datetime): End date
            
        Returns:
            dict: Payment summary by method
        """
        payments = cls.query.filter(
            cls.status == 'completed',
            cls.payment_date >= start_date,
            cls.payment_date <= end_date
        ).all()
        
        summary = {}
        for payment in payments:
            method = payment.payment_method
            if method not in summary:
                summary[method] = {
                    'count': 0,
                    'total_amount': 0,
                    'display_name': payment.payment_method_display
                }
            
            summary[method]['count'] += 1
            summary[method]['total_amount'] += payment.amount_in_default_currency
        
        return summary
    
    def __repr__(self):
        return f'<Payment {self.payment_reference} - {self.amount} AED>'


class Refund(BaseModel):
    """
    Refund model for tracking payment refunds
    """
    __tablename__ = 'refund'
    
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    refund_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reference_number = db.Column(db.String(100), nullable=True)
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # FIXED: Use string references
    payment = relationship('Payment', backref='refunds')
    refund_processor = relationship('User', 
                                backref='refunds_processed', 
                                foreign_keys=[processed_by],
                                primaryjoin='Refund.processed_by == User.id',
                                lazy='joined')
    
    @property
    def is_full_refund(self):
        """Check if this is a full refund"""
        if self.payment:
            return self.amount == self.payment.amount
        return False
    
    def to_dict(self):
        """
        Convert refund to dictionary
        
        Returns:
            dict: Refund data
        """
        return {
            'id': self.id,
            'payment_id': self.payment_id,
            'amount': self.amount,
            'reason': self.reason,
            'refund_date': self.refund_date.isoformat() if self.refund_date else None,
            'reference_number': self.reference_number,
            'is_full_refund': self.is_full_refund,
            'processed_by_name': self.refund_processor.full_name if self.refund_processor else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Refund {self.id} - {self.amount} AED for Payment {self.payment_id}>'