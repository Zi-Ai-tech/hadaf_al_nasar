from app import db
from app.models.core.base import BaseModel
from app.constants import IncomeType
from datetime import datetime
from sqlalchemy.orm import relationship, validates
import re

class Income(BaseModel):
    """
    Income model for Workforce and Payroll System (WPS)
    Tracks all company income including shipment revenues, services, and other revenue streams
    """
    __tablename__ = 'income'
    
    # Income Identification
    income_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    reference_number = db.Column(db.String(100), nullable=True, index=True)  # Invoice number, receipt number, etc.
    
    # Income Details
    income_type = db.Column(db.Enum(IncomeType), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='AED', nullable=False)
    exchange_rate = db.Column(db.Float, default=1.0)
    tax_amount = db.Column(db.Float, default=0.0)  # VAT or other taxes
    total_amount = db.Column(db.Float, nullable=False)  # Amount including tax
    
    # Description and Categorization
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=True)  # More detailed categorization
    subcategory = db.Column(db.String(100), nullable=True)
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags for searching
    
    # Dates
    income_date = db.Column(db.Date, nullable=False)
    payment_received_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)  # For credit income
    
    # Payment Information
    payment_method = db.Column(db.String(50), nullable=True)  # cash, bank_transfer, card, cheque
    payment_reference = db.Column(db.String(100), nullable=True)
    bank_account = db.Column(db.String(100), nullable=True)
    cheque_number = db.Column(db.String(50), nullable=True)
    
    # Customer/Client Information
    customer_name = db.Column(db.String(200), nullable=True)
    customer_contact = db.Column(db.String(100), nullable=True)
    customer_phone = db.Column(db.String(20), nullable=True)
    customer_trn = db.Column(db.String(50), nullable=True)  # Tax Registration Number
    customer_email = db.Column(db.String(100), nullable=True)
    
    # Status and Tracking
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, received, overdue, cancelled
    is_recurring = db.Column(db.Boolean, default=False, nullable=False)
    recurrence_pattern = db.Column(db.String(50), nullable=True)  # daily, weekly, monthly, quarterly, yearly
    recurrence_end_date = db.Column(db.Date, nullable=True)
    parent_income_id = db.Column(db.Integer, db.ForeignKey('income.id'), nullable=True)  # For recurring series
    
    # Documentation
    invoice_url = db.Column(db.String(500), nullable=True)
    receipt_url = db.Column(db.String(500), nullable=True)
    supporting_docs_url = db.Column(db.String(500), nullable=True)  # Comma-separated URLs
    
    # Budget and Accounting
    revenue_category = db.Column(db.String(100), nullable=True)
    accounting_period = db.Column(db.String(10), nullable=True)  # YYYY-MM format
    gl_account = db.Column(db.String(50), nullable=True)  # General Ledger account code
    is_taxable = db.Column(db.Boolean, default=True, nullable=False)
    
    # Foreign Keys
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipment.id'), nullable=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)  # If you have services
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=True, unique=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    customer = relationship('Customer', back_populates='customer_incomes')
    shipment = relationship('Shipment', backref='incomes')
    vehicle = relationship('Vehicle', backref='incomes')
    service = relationship('Service', backref='incomes')
    invoice = relationship('Invoice', back_populates='invoice_incomes')
    payment = relationship('Payment', back_populates='income', uselist=False)
    income_recorder = relationship('User', backref='incomes_recorded', foreign_keys=[recorded_by])
    recurring_children = relationship('Income', backref=db.backref('parent', remote_side='Income.id'))
    
    def __init__(self, **kwargs):
        """
        Initialize income with automatic number generation and calculations
        """
        if 'income_number' not in kwargs:
            kwargs['income_number'] = self.generate_income_number()
    
        # Convert income_type string to enum if needed
        if 'income_type' in kwargs and isinstance(kwargs['income_type'], str):
            kwargs['income_type'] = self.convert_income_type(kwargs['income_type'])
    
        # Calculate total amount if not provided
        if 'total_amount' not in kwargs and 'amount' in kwargs and 'tax_amount' in kwargs:
            kwargs['total_amount'] = kwargs['amount'] + kwargs.get('tax_amount', 0)
    
        super().__init__(**kwargs)
    
    @validates('amount')
    def validate_amount(self, key, amount):
        """Validate income amount"""
        if amount <= 0:
            raise ValueError("Income amount must be positive")
        return float(amount)
    
    @validates('income_type')
    def validate_income_type(self, key, income_type):
        """Validate income type"""
        # If it's already an enum instance, get its value
        if hasattr(income_type, 'value'):
            value = income_type.value
        else:
            value = str(income_type)
    
        # Convert to uppercase for comparison
        value_upper = value.upper()
    
        # Check if the uppercase value is valid
        valid_types = [t.value.upper() for t in IncomeType]
        if value_upper not in valid_types:
            raise ValueError(f"Invalid income type. Must be one of: {valid_types}")

        # Return the proper enum value (uppercase)
        # Find the enum member that matches the uppercase value
        for enum_member in IncomeType:
            if enum_member.value.upper() == value_upper:
                return enum_member
    
        # If we get here, something went wrong
        raise ValueError(f"Invalid income type: {value}")
    
    @property
    def is_received(self):
        """Check if income is received"""
        return self.status == 'received'
    
    @property
    def is_pending(self):
        """Check if income is pending"""
        return self.status == 'pending'
    
    @property
    def is_overdue(self):
        """Check if income payment is overdue"""
        if self.due_date and self.status not in ['received', 'cancelled']:
            return datetime.utcnow().date() > self.due_date
        return False
    
    @property
    def amount_in_default_currency(self):
        """Convert amount to default currency (AED)"""
        return self.amount * self.exchange_rate
    
    @property
    def total_amount_in_default_currency(self):
        """Convert total amount to default currency (AED)"""
        return self.total_amount * self.exchange_rate
    
    @property
    def tax_rate(self):
        """Calculate effective tax rate"""
        if self.amount > 0:
            return (self.tax_amount / self.amount) * 100
        return 0
    
    @property
    def age_in_days(self):
        """Calculate age of income in days"""
        if self.income_date:
            return (datetime.utcnow().date() - self.income_date).days
        return 0
    
    @property
    def days_overdue(self):
        """Calculate number of days overdue"""
        if self.is_overdue and self.due_date:
            return (datetime.utcnow().date() - self.due_date).days
        return 0
    
    @property
    def net_amount(self):
        """Calculate net amount (after tax)"""
        return self.amount - self.tax_amount
    
    def generate_income_number(self):
        """
        Generate automatic income number
        Format: INC-YYYY-MM-XXXX
        """
        from app.utils.income_utils import generate_income_number
        return generate_income_number()
    
    def calculate_totals(self):
        """
        Recalculate all financial totals
        """
        self.total_amount = self.amount + self.tax_amount
        return self.save()
    
    def mark_as_received(self, payment_date=None, payment_method=None, payment_reference=None):
        """
        Mark income as received (paid)
        
        Args:
            payment_date (date): Payment received date
            payment_method (str): Payment method used
            payment_reference (str): Payment reference number
            
        Returns:
            bool: True if marked as received successfully
        """
        if self.status == 'received':
            return True  # Already received
        
        self.status = 'received'
        self.payment_received_date = payment_date or datetime.utcnow().date()
        
        if payment_method:
            self.payment_method = payment_method
        if payment_reference:
            self.payment_reference = payment_reference
        
        return self.save()
    
    def mark_as_overdue(self):
        """
        Mark income as overdue
        
        Returns:
            bool: True if marked as overdue successfully
        """
        if self.status == 'pending' and self.is_overdue:
            self.status = 'overdue'
            return self.save()
        return False
    
    def add_tag(self, tag):
        """
        Add tag to income
        
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
        Remove tag from income
        
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
    
    def create_recurring_template(self, recurrence_pattern, recurrence_end_date=None):
        """
        Convert income to recurring template
        
        Args:
            recurrence_pattern (str): Recurrence pattern
            recurrence_end_date (date): End date for recurrence
            
        Returns:
            bool: True if converted successfully
        """
        valid_patterns = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
        if recurrence_pattern not in valid_patterns:
            raise ValueError(f"Invalid recurrence pattern. Must be one of: {valid_patterns}")
        
        self.is_recurring = True
        self.recurrence_pattern = recurrence_pattern
        self.recurrence_end_date = recurrence_end_date
        
        return self.save()
    
    def generate_next_recurrence(self):
        """
        Generate next recurrence of this income
        
        Returns:
            Income: Next recurring income or None
        """
        if not self.is_recurring:
            return None
        
        # Calculate next income date based on recurrence pattern
        next_date = self.calculate_next_recurrence_date()
        if not next_date:
            return None
        
        # Create new income based on this template
        next_income = Income(
            income_type=self.income_type,
            amount=self.amount,
            currency=self.currency,
            exchange_rate=self.exchange_rate,
            tax_amount=self.tax_amount,
            total_amount=self.total_amount,
            description=f"Recurring: {self.description}",
            category=self.category,
            subcategory=self.subcategory,
            income_date=next_date,
            due_date=next_date,  # Same as income date for simplicity
            payment_method=self.payment_method,
            customer_name=self.customer_name,
            customer_contact=self.customer_contact,
            customer_phone=self.customer_phone,
            customer_trn=self.customer_trn,
            customer_email=self.customer_email,
            is_recurring=True,
            recurrence_pattern=self.recurrence_pattern,
            recurrence_end_date=self.recurrence_end_date,
            parent_income_id=self.id,
            customer_id=self.customer_id,
            shipment_id=self.shipment_id,
            vehicle_id=self.vehicle_id,
            service_id=self.service_id,
            recorded_by=self.recorded_by,
            revenue_category=self.revenue_category,
            gl_account=self.gl_account,
            is_taxable=self.is_taxable
        )
        
        if next_income.save():
            return next_income
        return None
    
    def calculate_next_recurrence_date(self):
        """
        Calculate next recurrence date based on pattern
        
        Returns:
            date: Next recurrence date or None
        """
        if not self.is_recurring or not self.recurrence_pattern:
            return None
        
        from datetime import timedelta
        
        last_date = self.income_date
        if self.recurring_children:
            last_child = max(self.recurring_children, key=lambda x: x.income_date)
            last_date = last_child.income_date
        
        if self.recurrence_end_date and last_date >= self.recurrence_end_date:
            return None
        
        if self.recurrence_pattern == 'daily':
            return last_date + timedelta(days=1)
        elif self.recurrence_pattern == 'weekly':
            return last_date + timedelta(weeks=1)
        elif self.recurrence_pattern == 'monthly':
            # Simple monthly addition
            next_month = last_date.month + 1
            next_year = last_date.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            return last_date.replace(year=next_year, month=next_month)
        elif self.recurrence_pattern == 'quarterly':
            return last_date + timedelta(days=90)  # Approximately 3 months
        elif self.recurrence_pattern == 'yearly':
            return last_date.replace(year=last_date.year + 1)
        
        return None
    
    def calculate_tax(self, tax_rate=5.0):
        """
        Calculate tax amount based on tax rate
        
        Args:
            tax_rate (float): Tax rate percentage (default 5% for UAE VAT)
            
        Returns:
            float: Tax amount
        """
        if not self.is_taxable:
            return 0.0
        
        tax_amount = (self.amount * tax_rate) / 100
        self.tax_amount = tax_amount
        self.total_amount = self.amount + tax_amount
        
        return tax_amount
    
    def get_related_entities(self):
        """
        Get all related entities for this income
        
        Returns:
            dict: Related entities information
        """
        entities = {}
        
        if self.customer:
            entities['customer'] = {
                'id': self.customer.id,
                'name': self.customer.company_name,
                'contact': self.customer.contact_person,
                'type': 'customer'
            }
        
        if self.shipment:
            entities['shipment'] = {
                'id': self.shipment.id,
                'tracking_number': self.shipment.tracking_number,
                'route': f"{self.shipment.origin_city} to {self.shipment.destination_city}",
                'type': 'shipment'
            }
        
        if self.vehicle:
            entities['vehicle'] = {
                'id': self.vehicle.id,
                'registration_number': self.vehicle.registration_number,
                'type': 'vehicle'
            }
        
        if self.service:
            entities['service'] = {
                'id': self.service.id,
                'name': self.service.name,
                'type': 'service'
            }
        
        return entities
    
    def to_dict(self, include_related=True, include_financial_details=True):
        """
        Convert income to dictionary
        
        Args:
            include_related (bool): Include related entity information
            include_financial_details (bool): Include detailed financial info
            
        Returns:
            dict: Income data
        """
        data = super().to_dict()

        if hasattr(self, 'income_type'):
            data['income_type'] = self._convert_enum_value(self.income_type)
        
        # Add computed properties
        data['is_received'] = self.is_received
        data['is_pending'] = self.is_pending
        data['is_overdue'] = self.is_overdue
        data['amount_in_default_currency'] = self.amount_in_default_currency
        data['total_amount_in_default_currency'] = self.total_amount_in_default_currency
        data['tax_rate'] = self.tax_rate
        data['age_in_days'] = self.age_in_days
        data['days_overdue'] = self.days_overdue
        data['net_amount'] = self.net_amount
        
        # Format dates
        if self.income_date:
            data['income_date'] = self.income_date.isoformat()
        if self.payment_received_date:
            data['payment_received_date'] = self.payment_received_date.isoformat()
        if self.due_date:
            data['due_date'] = self.due_date.isoformat()
        if self.recurrence_end_date:
            data['recurrence_end_date'] = self.recurrence_end_date.isoformat()
        
        # Parse tags
        if self.tags:
            data['tags_list'] = self.tags.split(',')
        else:
            data['tags_list'] = []
        
        # Parse supporting documents
        if self.supporting_docs_url:
            data['supporting_docs_list'] = self.supporting_docs_url.split(',')
        else:
            data['supporting_docs_list'] = []
        
        # Include related data
        if include_related:
            data['related_entities'] = self.get_related_entities()
            
            if self.recorder:
                data['recorded_by_name'] = self.recorder.full_name
            
            # Include recurring children count
            if self.is_recurring:
                data['recurring_children_count'] = len(self.recurring_children)
                data['next_recurrence_date'] = self.calculate_next_recurrence_date().isoformat() if self.calculate_next_recurrence_date() else None
        
        # Include financial details
        if include_financial_details:
            data['financial_summary'] = {
                'amount': self.amount,
                'tax_amount': self.tax_amount,
                'total_amount': self.total_amount,
                'net_amount': self.net_amount,
                'currency': self.currency,
                'exchange_rate': self.exchange_rate,
                'amount_aed': self.amount_in_default_currency,
                'total_amount_aed': self.total_amount_in_default_currency,
                'net_amount_aed': self.net_amount * self.exchange_rate,
                'is_taxable': self.is_taxable
            }
        
        return data
    
    @classmethod
    def get_by_number(cls, income_number):
        """
        Get income by income number
        
        Args:
            income_number (str): Income number
            
        Returns:
            Income: Income instance or None
        """
        return cls.query.filter_by(income_number=income_number).first()
    
    @classmethod
    def get_incomes_by_type(cls, income_type, start_date=None, end_date=None):
        """
        Get incomes by type within date range
        
        Args:
            income_type (str): Income type
            start_date (date): Start date filter
            end_date (date): End date filter
            
        Returns:
            list: List of incomes
        """
        query = cls.query.filter_by(income_type=income_type)
        
        if start_date:
            query = query.filter(cls.income_date >= start_date)
        if end_date:
            query = query.filter(cls.income_date <= end_date)
        
        return query.order_by(cls.income_date.desc()).all()
    
    @classmethod
    def get_incomes_by_status(cls, status, start_date=None, end_date=None):
        """
        Get incomes by status within date range
        
        Args:
            status (str): Income status
            start_date (date): Start date filter
            end_date (date): End date filter
            
        Returns:
            list: List of incomes with specified status
        """
        query = cls.query.filter_by(status=status)
        
        if start_date:
            query = query.filter(cls.income_date >= start_date)
        if end_date:
            query = query.filter(cls.income_date <= end_date)
        
        return query.order_by(cls.income_date.desc()).all()
    
    @classmethod
    def get_pending_incomes(cls):
        """
        Get pending incomes (not yet received)
        
        Returns:
            list: List of pending incomes
        """
        return cls.query.filter_by(status='pending').order_by(cls.income_date).all()
    
    @classmethod
    def get_overdue_incomes(cls):
        """
        Get overdue incomes (not received with due date passed)
        
        Returns:
            list: List of overdue incomes
        """
        return cls.query.filter(
            cls.status.in_(['pending', 'overdue']),
            cls.due_date < datetime.utcnow().date()
        ).order_by(cls.due_date).all()
    
    @classmethod
    def get_recurring_incomes(cls):
        """
        Get all recurring income templates
        
        Returns:
            list: List of recurring incomes
        """
        return cls.query.filter_by(is_recurring=True).order_by(cls.income_date).all()
    
    @classmethod
    def get_total_income(cls, start_date, end_date, income_type=None, status=None):
        """
        Get total income amount within date range
        
        Args:
            start_date (date): Start date
            end_date (date): End date
            income_type (str): Filter by income type
            status (str): Filter by status
            
        Returns:
            float: Total income amount in AED
        """
        query = cls.query.filter(
            cls.income_date >= start_date,
            cls.income_date <= end_date
        )
        
        if income_type:
            query = query.filter_by(income_type=income_type)
        if status:
            query = query.filter_by(status=status)
        
        incomes = query.all()
        return sum(income.total_amount_in_default_currency for income in incomes)
    
    @classmethod
    def get_income_summary(cls, start_date, end_date, group_by='income_type'):
        """
        Get income summary for a date range
        
        Args:
            start_date (date): Start date
            end_date (date): End date
            group_by (str): Field to group by (income_type, category, status, etc.)
            
        Returns:
            dict: Income summary
        """
        incomes = cls.query.filter(
            cls.income_date >= start_date,
            cls.income_date <= end_date
        ).all()
        
        summary = {}
        
        for income in incomes:
            group_value = getattr(income, group_by, 'Unknown')
            
            if group_value not in summary:
                summary[group_value] = {
                    'count': 0,
                    'total_amount': 0,
                    'total_amount_aed': 0,
                    'net_amount': 0,
                    'tax_amount': 0,
                    'incomes': []
                }
            
            summary[group_value]['count'] += 1
            summary[group_value]['total_amount'] += income.total_amount
            summary[group_value]['total_amount_aed'] += income.total_amount_in_default_currency
            summary[group_value]['net_amount'] += income.net_amount
            summary[group_value]['tax_amount'] += income.tax_amount
            summary[group_value]['incomes'].append(income.to_dict())
        
        return summary
    
    @classmethod
    def get_customer_income_summary(cls, customer_id, start_date=None, end_date=None):
        """
        Get income summary for a specific customer
        
        Args:
            customer_id (int): Customer ID
            start_date (date): Start date filter
            end_date (date): End date filter
            
        Returns:
            dict: Customer income summary
        """
        query = cls.query.filter_by(customer_id=customer_id)
        
        if start_date:
            query = query.filter(cls.income_date >= start_date)
        if end_date:
            query = query.filter(cls.income_date <= end_date)
        
        incomes = query.all()
        
        total_income = sum(income.total_amount_in_default_currency for income in incomes)
        received_income = sum(income.total_amount_in_default_currency for income in incomes if income.is_received)
        pending_income = sum(income.total_amount_in_default_currency for income in incomes if income.is_pending)
        overdue_income = sum(income.total_amount_in_default_currency for income in incomes if income.is_overdue)
        
        return {
            'customer_id': customer_id,
            'total_income': total_income,
            'received_income': received_income,
            'pending_income': pending_income,
            'overdue_income': overdue_income,
            'total_transactions': len(incomes),
            'collection_rate': (received_income / total_income * 100) if total_income > 0 else 0,
            'period': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None
            }
        }
    
    @classmethod
    def convert_income_type(cls, income_type_str):
        """
        Convert string income type to proper enum value
    
        Args:
            income_type_str: String income type
        
        Returns:
            IncomeType: Proper enum value
        """
        if not income_type_str:
            return IncomeType.OTHER
    
        # Convert to uppercase and find matching enum
        value_upper = str(income_type_str).upper()
    
        for enum_member in IncomeType:
            if enum_member.value.upper() == value_upper:
                return enum_member
    
        # Default to OTHER if not found
        return IncomeType.OTHER
    
    @staticmethod
    def _convert_enum_value(value):
        """
        Helper method to convert enum values, handling both cases
        """
        if hasattr(value, 'value'):
            return value.value
    
        value_str = str(value)
    
        # Map to lowercase for template compatibility
        mapping = {
            'SHIPMENT': 'shipment',
            'SERVICE': 'service',
            'VEHICLE_RENTAL': 'vehicle_rental',
            'VEHICLE_REN..': 'vehicle_rental',  # Handle truncated value from error
            'CONSULTATION': 'consultation',
            'STORAGE': 'storage',
            'INVOICE_PAYMENT': 'invoice_payment',
            'OTHER': 'other'
        }
    
        return mapping.get(value_str.upper(), 'other')
    
    def __repr__(self):
        return f'<Income {self.income_number} - {self.income_type.value} - {self.total_amount} {self.currency}>'


class Service(BaseModel):
    """
    Service model for income categorization and service tracking
    """
    __tablename__ = 'service'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    service_type = db.Column(db.String(50), nullable=False)  # transportation, storage, customs, etc.
    base_price = db.Column(db.Float, default=0.0, nullable=False)
    currency = db.Column(db.String(3), default='AED', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    tax_rate = db.Column(db.Float, default=5.0, nullable=False)  # Default 5% VAT for UAE
    unit = db.Column(db.String(20), nullable=True)  # per_kg, per_km, per_hour, fixed
    min_quantity = db.Column(db.Float, default=1.0, nullable=False)
    max_quantity = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def price_with_tax(self):
        """Calculate price including tax"""
        return self.base_price * (1 + self.tax_rate / 100)
    
    def calculate_total_price(self, quantity=1):
        """
        Calculate total price for given quantity
        
        Args:
            quantity (float): Quantity of service
            
        Returns:
            dict: Price calculation
        """
        if quantity < self.min_quantity:
            raise ValueError(f"Minimum quantity required: {self.min_quantity}")
        
        if self.max_quantity and quantity > self.max_quantity:
            raise ValueError(f"Maximum quantity allowed: {self.max_quantity}")
        
        base_amount = self.base_price * quantity
        tax_amount = base_amount * (self.tax_rate / 100)
        total_amount = base_amount + tax_amount
        
        return {
            'base_amount': base_amount,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            'quantity': quantity,
            'unit_price': self.base_price,
            'tax_rate': self.tax_rate
        }
    
    def to_dict(self):
        """Convert service to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'service_type': self.service_type,
            'base_price': self.base_price,
            'price_with_tax': self.price_with_tax,
            'currency': self.currency,
            'is_active': self.is_active,
            'tax_rate': self.tax_rate,
            'unit': self.unit,
            'min_quantity': self.min_quantity,
            'max_quantity': self.max_quantity,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Service {self.code} - {self.name}>'