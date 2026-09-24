from app import db
from app.models.core.base import BaseModel
from app.constants import ExpenseType, IncomeType
from datetime import datetime
from sqlalchemy.orm import relationship, validates
from decimal import Decimal
from enum import Enum
try:
    from app.models.wps.employee import Employee
except ImportError:
    # Use string reference if circular import occurs
    pass

try:
    from app.models.logistics.shipment import Shipment
except ImportError:
    pass

try:
    from app.models.finance.invoice import Invoice
except ImportError:
    pass


class TransactionType(Enum):
    """Transaction type enumeration"""
    INCOME = 'income'
    EXPENSE = 'expense'
    SALARY = 'salary'
    TRANSFER = 'transfer'
    ADJUSTMENT = 'adjustment'

class TransactionStatus(Enum):
    """Transaction status enumeration"""
    PENDING = 'pending'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    FAILED = 'failed'
    RECONCILED = 'reconciled'

class Transaction(BaseModel):
    """
    Comprehensive transaction model for all financial transactions
    Unified model for incomes, expenses, salaries, and other financial activities
    """
    __tablename__ = 'transaction'
    
    # Transaction Identification
    transaction_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    transaction_type = db.Column(db.String(20), nullable=False)  # income, expense, salary, transfer, adjustment
    reference_number = db.Column(db.String(100), nullable=True, index=True)
    
    # Financial Details
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='AED', nullable=False)
    exchange_rate = db.Column(db.Float, default=1.0)
    tax_amount = db.Column(db.Float, default=0.0)  # VAT or other taxes
    net_amount = db.Column(db.Float, nullable=False)  # Amount after tax
    
    # Dates
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    value_date = db.Column(db.DateTime, nullable=True)  # When transaction actually affects accounts
    due_date = db.Column(db.DateTime, nullable=True)  # For credit transactions
    
    # Categorization
    category = db.Column(db.String(50), nullable=False)  # Main category
    subcategory = db.Column(db.String(50), nullable=True)  # Detailed category
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags for searching
    
    # Parties Involved
    payer = db.Column(db.String(200), nullable=True)  # Who paid (for income) or who we paid (for expense)
    payee = db.Column(db.String(200), nullable=True)  # Who received payment
    
    # Description and Details
    description = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    attachment_url = db.Column(db.String(500), nullable=True)  # Receipt, invoice, document
    
    # Status and Tracking
    status = db.Column(db.String(20), default=TransactionStatus.PENDING.value, nullable=False)
    is_reconciled = db.Column(db.Boolean, default=False, nullable=False)
    reconciled_date = db.Column(db.DateTime, nullable=True)
    requires_approval = db.Column(db.Boolean, default=False, nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_date = db.Column(db.DateTime, nullable=True)
    
    # Payment Method
    payment_method = db.Column(db.String(50), nullable=True)  # cash, bank_transfer, card, cheque
    bank_account = db.Column(db.String(100), nullable=True)  # Bank account used
    cheque_number = db.Column(db.String(50), nullable=True)
    
    # Foreign Keys (flexible relationships)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipment.id'), nullable=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=True)
    
    # Budget and Accounting
    budget_category = db.Column(db.String(100), nullable=True)
    accounting_period = db.Column(db.String(10), nullable=True)  # YYYY-MM format
    gl_account = db.Column(db.String(50), nullable=True)  # General Ledger account code
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    customer = relationship('Customer', backref='customer_transactions')
    supplier = relationship('Supplier', backref='supplier_transactions')
    employee = relationship('Employee', backref='employee_transactions')
    vehicle = relationship('Vehicle', backref='vehicle_transactions')
    shipment = relationship('Shipment', backref='shipment_transactions')
    invoice = relationship('Invoice', backref='invoice_transactions')
    payment = relationship('Payment', backref='payment_transactions')
    transaction_approver = relationship('User', backref='transactions_approved', foreign_keys=[approved_by])
    
    def __init__(self, **kwargs):
        """
        Initialize transaction with automatic number generation and calculations
        """
        if 'transaction_number' not in kwargs:
            kwargs['transaction_number'] = self.generate_transaction_number()
        
        # Calculate net amount if not provided
        if 'net_amount' not in kwargs and 'amount' in kwargs and 'tax_amount' in kwargs:
            kwargs['net_amount'] = kwargs['amount'] - kwargs.get('tax_amount', 0)
        
        super().__init__(**kwargs)
    
    @validates('amount')
    def validate_amount(self, key, amount):
        """Validate transaction amount"""
        if amount <= 0:
            raise ValueError("Transaction amount must be positive")
        return float(amount)
    
    @validates('transaction_type')
    def validate_transaction_type(self, key, transaction_type):
        """Validate transaction type"""
        valid_types = [t.value for t in TransactionType]
        if transaction_type not in valid_types:
            raise ValueError(f"Invalid transaction type. Must be one of: {valid_types}")
        return transaction_type
    
    @property
    def is_income(self):
        """Check if this is an income transaction"""
        return self.transaction_type == TransactionType.INCOME.value
    
    @property
    def is_expense(self):
        """Check if this is an expense transaction"""
        return self.transaction_type == TransactionType.EXPENSE.value
    
    @property
    def is_salary(self):
        """Check if this is a salary transaction"""
        return self.transaction_type == TransactionType.SALARY.value
    
    @property
    def is_completed(self):
        """Check if transaction is completed"""
        return self.status == TransactionStatus.COMPLETED.value
    
    @property
    def is_pending(self):
        """Check if transaction is pending"""
        return self.status == TransactionStatus.PENDING.value
    
    @property
    def amount_in_default_currency(self):
        """Convert amount to default currency (AED)"""
        return self.amount * self.exchange_rate
    
    @property
    def tax_rate(self):
        """Calculate effective tax rate"""
        if self.amount > 0:
            return (self.tax_amount / self.amount) * 100
        return 0
    
    @property
    def age_in_days(self):
        """Calculate age of transaction in days"""
        if self.transaction_date:
            return (datetime.utcnow() - self.transaction_date).days
        return 0
    
    def generate_transaction_number(self):
        """
        Generate automatic transaction number
        Format: TRX-YYYY-MM-XXXX
        """
        from app.utils.transaction_utils import generate_transaction_number
        return generate_transaction_number()
    
    def calculate_totals(self):
        """
        Recalculate all financial totals
        """
        self.net_amount = self.amount - self.tax_amount
        return self.save()
    
    def mark_completed(self, value_date=None):
        """
        Mark transaction as completed
        
        Args:
            value_date (datetime): When transaction takes effect
            
        Returns:
            bool: True if status was updated
        """
        if self.status != TransactionStatus.COMPLETED.value:
            self.status = TransactionStatus.COMPLETED.value
            self.value_date = value_date or datetime.utcnow()
            return self.save()
        return False
    
    def mark_reconciled(self):
        """
        Mark transaction as reconciled with bank statement
        
        Returns:
            bool: True if reconciled successfully
        """
        if not self.is_reconciled:
            self.is_reconciled = True
            self.reconciled_date = datetime.utcnow()
            return self.save()
        return False
    
    def approve(self, approved_by_user_id):
        """
        Approve transaction (for transactions requiring approval)
        
        Args:
            approved_by_user_id (int): User ID who approved
            
        Returns:
            bool: True if approved successfully
        """
        if self.requires_approval and not self.approved_by:
            self.approved_by = approved_by_user_id
            self.approved_date = datetime.utcnow()
            return self.save()
        return False
    
    def add_tag(self, tag):
        """
        Add tag to transaction
        
        Args:
            tag (str): Tag to add
            
        Returns:
            bool: True if tag was added
        """
        current_tags = self.tags.split(',') if self.tags else []
        if tag not in current_tags:
            current_tags.append(tag)
            self.tags = ','.join(current_tags)
            return self.save()
        return False
    
    def remove_tag(self, tag):
        """
        Remove tag from transaction
        
        Args:
            tag (str): Tag to remove
            
        Returns:
            bool: True if tag was removed
        """
        if self.tags:
            current_tags = self.tags.split(',')
            if tag in current_tags:
                current_tags.remove(tag)
                self.tags = ','.join(current_tags) if current_tags else None
                return self.save()
        return False
    
    def get_related_entities(self):
        """
        Get all related entities for this transaction
        
        Returns:
            dict: Related entities information
        """
        entities = {}
        
        if self.customer:
            entities['customer'] = {
                'id': self.customer.id,
                'name': self.customer.company_name,
                'type': 'customer'
            }
        
        if self.supplier:
            entities['supplier'] = {
                'id': self.supplier.id,
                'name': self.supplier.name,
                'type': 'supplier'
            }
        
        if self.employee:
            entities['employee'] = {
                'id': self.employee.id,
                'name': self.employee.name,
                'type': 'employee'
            }
        
        if self.vehicle:
            entities['vehicle'] = {
                'id': self.vehicle.id,
                'name': self.vehicle.registration_number,
                'type': 'vehicle'
            }
        
        if self.shipment:
            entities['shipment'] = {
                'id': self.shipment.id,
                'name': self.shipment.tracking_number,
                'type': 'shipment'
            }
        
        return entities
    
    def to_dict(self, include_related=True, include_financial_details=True):
        """
        Convert transaction to dictionary
        
        Args:
            include_related (bool): Include related entity information
            include_financial_details (bool): Include detailed financial info
            
        Returns:
            dict: Transaction data
        """
        data = super().to_dict()
        
        # Add computed properties
        data['is_income'] = self.is_income
        data['is_expense'] = self.is_expense
        data['is_salary'] = self.is_salary
        data['is_completed'] = self.is_completed
        data['is_pending'] = self.is_pending
        data['amount_in_default_currency'] = self.amount_in_default_currency
        data['tax_rate'] = self.tax_rate
        data['age_in_days'] = self.age_in_days
        
        # Format dates
        if self.transaction_date:
            data['transaction_date'] = self.transaction_date.isoformat()
        if self.value_date:
            data['value_date'] = self.value_date.isoformat()
        if self.due_date:
            data['due_date'] = self.due_date.isoformat()
        if self.approved_date:
            data['approved_date'] = self.approved_date.isoformat()
        if self.reconciled_date:
            data['reconciled_date'] = self.reconciled_date.isoformat()
        
        # Parse tags
        if self.tags:
            data['tags_list'] = self.tags.split(',')
        else:
            data['tags_list'] = []
        
        # Include related data
        if include_related:
            data['related_entities'] = self.get_related_entities()
            
            if self.approver:
                data['approved_by_name'] = self.approver.full_name
        
        # Include financial details
        if include_financial_details:
            data['financial_summary'] = {
                'gross_amount': self.amount,
                'tax_amount': self.tax_amount,
                'net_amount': self.net_amount,
                'currency': self.currency,
                'exchange_rate': self.exchange_rate
            }
        
        return data
    
    def create_reversal_transaction(self, reason=None):
        """
        Create a reversal transaction for this transaction
        
        Args:
            reason (str): Reason for reversal
            
        Returns:
            Transaction: Reversal transaction or None
        """
        try:
            reversal = Transaction(
                transaction_type=self.transaction_type,
                amount=self.amount,
                currency=self.currency,
                exchange_rate=self.exchange_rate,
                tax_amount=self.tax_amount,
                net_amount=self.net_amount,
                category=f"Reversal: {self.category}",
                description=f"Reversal of {self.transaction_number}" + (f" - {reason}" if reason else ""),
                transaction_date=datetime.utcnow(),
                status=TransactionStatus.COMPLETED.value,
                payment_method=self.payment_method,
                # Link to original transaction
                reference_number=f"REV-{self.transaction_number}",
                notes=reason
            )
            
            if reversal.save():
                # Mark original as cancelled
                self.status = TransactionStatus.CANCELLED.value
                self.save()
                
                return reversal
            return None
            
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error creating reversal transaction: {str(e)}")
            return None
    
    @classmethod
    def get_by_number(cls, transaction_number):
        """
        Get transaction by transaction number
        
        Args:
            transaction_number (str): Transaction number
            
        Returns:
            Transaction: Transaction instance or None
        """
        return cls.query.filter_by(transaction_number=transaction_number).first()
    
    @classmethod
    def get_transactions_by_type(cls, transaction_type, start_date=None, end_date=None):
        """
        Get transactions by type within date range
        
        Args:
            transaction_type (str): Transaction type
            start_date (datetime): Start date filter
            end_date (datetime): End date filter
            
        Returns:
            list: List of transactions
        """
        query = cls.query.filter_by(transaction_type=transaction_type)
        
        if start_date:
            query = query.filter(cls.transaction_date >= start_date)
        if end_date:
            query = query.filter(cls.transaction_date <= end_date)
        
        return query.order_by(cls.transaction_date.desc()).all()
    
    @classmethod
    def get_transactions_by_category(cls, category, subcategory=None, start_date=None, end_date=None):
        """
        Get transactions by category and optional subcategory
        
        Args:
            category (str): Main category
            subcategory (str): Optional subcategory
            start_date (datetime): Start date filter
            end_date (datetime): End date filter
            
        Returns:
            list: List of transactions
        """
        query = cls.query.filter_by(category=category)
        
        if subcategory:
            query = query.filter_by(subcategory=subcategory)
        if start_date:
            query = query.filter(cls.transaction_date >= start_date)
        if end_date:
            query = query.filter(cls.transaction_date <= end_date)
        
        return query.order_by(cls.transaction_date.desc()).all()
    
    @classmethod
    def get_pending_approval(cls):
        """
        Get transactions pending approval
        
        Returns:
            list: List of pending approval transactions
        """
        return cls.query.filter_by(
            requires_approval=True,
            approved_by=None
        ).order_by(cls.transaction_date).all()
    
    @classmethod
    def get_unreconciled_transactions(cls, start_date=None, end_date=None):
        """
        Get unreconciled transactions
        
        Args:
            start_date (datetime): Start date filter
            end_date (datetime): End date filter
            
        Returns:
            list: List of unreconciled transactions
        """
        query = cls.query.filter_by(is_reconciled=False)
        
        if start_date:
            query = query.filter(cls.transaction_date >= start_date)
        if end_date:
            query = query.filter(cls.transaction_date <= end_date)
        
        return query.order_by(cls.transaction_date).all()
    
    @classmethod
    def get_financial_summary(cls, start_date, end_date, group_by='category'):
        """
        Get financial summary for a date range
        
        Args:
            start_date (datetime): Start date
            end_date (datetime): End date
            group_by (str): Field to group by (category, type, etc.)
            
        Returns:
            dict: Financial summary
        """
        transactions = cls.query.filter(
            cls.transaction_date >= start_date,
            cls.transaction_date <= end_date,
            cls.status == TransactionStatus.COMPLETED.value
        ).all()
        
        summary = {}
        
        for transaction in transactions:
            group_value = getattr(transaction, group_by, 'Unknown')
            
            if group_value not in summary:
                summary[group_value] = {
                    'count': 0,
                    'total_amount': 0,
                    'total_tax': 0,
                    'total_net': 0,
                    'transactions': []
                }
            
            summary[group_value]['count'] += 1
            summary[group_value]['total_amount'] += transaction.amount
            summary[group_value]['total_tax'] += transaction.tax_amount
            summary[group_value]['total_net'] += transaction.net_amount
            summary[group_value]['transactions'].append(transaction.to_dict())
        
        return summary
    
    @classmethod
    def get_cash_flow(cls, start_date, end_date, period='daily'):
        """
        Get cash flow analysis for a date range
        
        Args:
            start_date (datetime): Start date
            end_date (datetime): End date
            period (str): Period for grouping (daily, weekly, monthly)
            
        Returns:
            dict: Cash flow analysis
        """
        transactions = cls.query.filter(
            cls.transaction_date >= start_date,
            cls.transaction_date <= end_date,
            cls.status == TransactionStatus.COMPLETED.value
        ).order_by(cls.transaction_date).all()
        
        cash_flow = {}
        
        for transaction in transactions:
            if period == 'daily':
                period_key = transaction.transaction_date.strftime('%Y-%m-%d')
            elif period == 'weekly':
                period_key = transaction.transaction_date.strftime('%Y-W%U')
            else:  # monthly
                period_key = transaction.transaction_date.strftime('%Y-%m')
            
            if period_key not in cash_flow:
                cash_flow[period_key] = {
                    'income': 0,
                    'expense': 0,
                    'net_cash_flow': 0,
                    'date': period_key
                }
            
            if transaction.is_income:
                cash_flow[period_key]['income'] += transaction.net_amount
            elif transaction.is_expense:
                cash_flow[period_key]['expense'] += transaction.net_amount
            
            cash_flow[period_key]['net_cash_flow'] = (
                cash_flow[period_key]['income'] - cash_flow[period_key]['expense']
            )
        
        return cash_flow
    
    def __repr__(self):
        return f'<Transaction {self.transaction_number} - {self.transaction_type} - {self.amount} {self.currency}>'


class Supplier(BaseModel):
    """
    Supplier model for expense transactions
    """
    __tablename__ = 'supplier'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    trn = db.Column(db.String(50), nullable=True)  # Tax Registration Number
    payment_terms = db.Column(db.String(50), default='NET30')
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert supplier to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'contact_person': self.contact_person,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'trn': self.trn,
            'payment_terms': self.payment_terms,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Supplier {self.name}>'