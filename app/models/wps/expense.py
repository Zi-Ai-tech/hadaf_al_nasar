from app import db
from app.models.core.base import BaseModel
from app.constants import ExpenseType
from datetime import datetime, date, timedelta
from sqlalchemy.orm import relationship, validates
import re


class Expense(BaseModel):
    """
    Expense model for Workforce and Payroll System (WPS)
    Tracks all company expenses including operational, vehicle, employee, and administrative costs
    """
    __tablename__ = 'expense'

    # Expense Identification
    expense_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    reference_number = db.Column(db.String(100), nullable=True, index=True)

    # Expense Details
    expense_type = db.Column(
        db.Enum(
            ExpenseType,
            values_callable=lambda enum_type: [member.value for member in enum_type],
            name='expensetype',
        ),
        nullable=False,
    )
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='AED', nullable=False)
    exchange_rate = db.Column(db.Float, default=1.0)
    tax_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)

    # Description and Categorization
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=True)
    subcategory = db.Column(db.String(100), nullable=True)
    tags = db.Column(db.String(500), nullable=True)

    # Dates
    expense_date = db.Column(db.Date, nullable=False)
    payment_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)

    # Payment Information
    payment_method = db.Column(db.String(50), nullable=True)
    payment_reference = db.Column(db.String(100), nullable=True)
    bank_account = db.Column(db.String(100), nullable=True)
    cheque_number = db.Column(db.String(50), nullable=True)

    # Vendor/Supplier Information
    vendor_name = db.Column(db.String(200), nullable=True)
    vendor_contact = db.Column(db.String(100), nullable=True)
    vendor_phone = db.Column(db.String(20), nullable=True)
    vendor_trn = db.Column(db.String(50), nullable=True)

    # Status and Approval
    status = db.Column(db.String(20), default='pending', nullable=False)
    requires_approval = db.Column(db.Boolean, default=True, nullable=False)
    approved_date = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Recurring Expense
    is_recurring = db.Column(db.Boolean, default=False, nullable=False)
    recurrence_pattern = db.Column(db.String(50), nullable=True)
    recurrence_end_date = db.Column(db.Date, nullable=True)
    parent_expense_id = db.Column(db.Integer, db.ForeignKey('expense.id'), nullable=True)

    # Documentation
    receipt_url = db.Column(db.String(500), nullable=True)
    invoice_url = db.Column(db.String(500), nullable=True)
    supporting_docs_url = db.Column(db.String(500), nullable=True)

    # Budget and Accounting
    budget_category = db.Column(db.String(100), nullable=True)
    accounting_period = db.Column(db.String(10), nullable=True)
    gl_account = db.Column(db.String(50), nullable=True)

    # Foreign Keys
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationships
    employee = relationship('Employee', backref='expenses')
    vehicle = relationship('Vehicle', backref='wps_expenses')
    project = relationship('Project', back_populates='expenses')
    expense_recorder = relationship('User', backref='expense_recorded', foreign_keys=[recorded_by])
    expense_approver = relationship('User', backref='expense_approved', foreign_keys=[approved_by])
    recurring_children = relationship('Expense', backref=db.backref('parent', remote_side='Expense.id'))

    def __init__(self, **kwargs):
        if 'expense_number' not in kwargs:
            kwargs['expense_number'] = self.generate_expense_number()
        if 'total_amount' not in kwargs and 'amount' in kwargs:
            kwargs['total_amount'] = kwargs['amount'] + kwargs.get('tax_amount', 0)
        super().__init__(**kwargs)

    # ---------------- Validation ----------------
    @validates('amount')
    def validate_amount(self, key, amount):
        if amount is None or amount <= 0:
            raise ValueError("Expense amount must be positive")
        return float(amount)

    @validates('expense_type')
    def validate_expense_type(self, key, expense_type):
        try:
            return expense_type if isinstance(expense_type, ExpenseType) else ExpenseType(expense_type)
        except (TypeError, ValueError) as exc:
            valid_types = [expense_type.value for expense_type in ExpenseType]
            raise ValueError(f"Invalid expense type. Must be one of: {valid_types}") from exc

    # ---------------- Properties ----------------
    @property
    def is_approved(self):
        return self.status == 'approved'

    @property
    def is_paid(self):
        return self.status == 'paid'

    @property
    def is_pending(self):
        return self.status == 'pending'

    @property
    def is_rejected(self):
        return self.status == 'rejected'

    @property
    def amount_in_default_currency(self):
        return (self.amount or 0) * (self.exchange_rate or 1)

    @property
    def total_amount_in_default_currency(self):
        return (self.total_amount or 0) * (self.exchange_rate or 1)

    @property
    def tax_rate(self):
        if self.amount and self.amount > 0:
            return (self.tax_amount or 0) / self.amount * 100
        return 0

    @property
    def age_in_days(self):
        if self.expense_date:
            return (datetime.utcnow().date() - self.expense_date).days
        return 0

    @property
    def is_overdue(self):
        if self.due_date and self.status not in ['paid', 'cancelled']:
            return datetime.utcnow().date() > self.due_date
        return False

    @property
    def days_overdue(self):
        if self.is_overdue and self.due_date:
            return (datetime.utcnow().date() - self.due_date).days
        return 0

    # ---------------- Core Methods ----------------
    def generate_expense_number(self):
        from app.utils.expense_utils import generate_expense_number
        return generate_expense_number()

    def calculate_totals(self):
        self.total_amount = (self.amount or 0) + (self.tax_amount or 0)
        return self.save()

    def approve(self, approved_by_user_id, notes=None):
        if self.status != 'pending':
            raise ValueError("Expense is not pending approval")
        self.status = 'approved'
        self.approved_by = approved_by_user_id
        self.approved_date = datetime.utcnow()
        if notes:
            self.description = f"{self.description}\nApproval Notes: {notes}"
        return self.save()

    def reject(self, rejected_by_user_id, reason):
        if self.status != 'pending':
            raise ValueError("Expense is not pending approval")
        self.status = 'rejected'
        self.approved_by = rejected_by_user_id
        self.approved_date = datetime.utcnow()
        self.rejection_reason = reason
        return self.save()

    def mark_as_paid(self, payment_date=None, payment_method=None, payment_reference=None):
        if self.status not in ['approved', 'pending']:
            raise ValueError("Expense must be approved or pending to mark as paid")
        self.status = 'paid'
        self.payment_date = payment_date or datetime.utcnow().date()
        if payment_method:
            self.payment_method = payment_method
        if payment_reference:
            self.payment_reference = payment_reference
        return self.save()

    def add_tag(self, tag):
        current_tags = self.tags.split(',') if self.tags else []
        if tag not in current_tags:
            current_tags.append(tag)
            self.tags = ','.join(current_tags)
            return self.save()
        return False

    def remove_tag(self, tag):
        if self.tags:
            current_tags = self.tags.split(',')
            if tag in current_tags:
                current_tags.remove(tag)
                self.tags = ','.join(current_tags) if current_tags else None
                return self.save()
        return False

    # ---------------- Recurring Expense ----------------
    def create_recurring_template(self, recurrence_pattern, recurrence_end_date=None):
        valid_patterns = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
        if recurrence_pattern not in valid_patterns:
            raise ValueError(f"Invalid recurrence pattern. Must be one of: {valid_patterns}")
        self.is_recurring = True
        self.recurrence_pattern = recurrence_pattern
        self.recurrence_end_date = recurrence_end_date
        return self.save()

    def generate_next_recurrence(self):
        if not self.is_recurring:
            return None
        next_date = self.calculate_next_recurrence_date()
        if not next_date:
            return None
        next_expense = Expense(
            expense_type=self.expense_type,
            amount=self.amount,
            currency=self.currency,
            exchange_rate=self.exchange_rate,
            tax_amount=self.tax_amount,
            total_amount=self.total_amount,
            description=f"Recurring: {self.description}",
            category=self.category,
            subcategory=self.subcategory,
            expense_date=next_date,
            due_date=next_date,
            payment_method=self.payment_method,
            vendor_name=self.vendor_name,
            vendor_contact=self.vendor_contact,
            vendor_phone=self.vendor_phone,
            vendor_trn=self.vendor_trn,
            requires_approval=self.requires_approval,
            is_recurring=True,
            recurrence_pattern=self.recurrence_pattern,
            recurrence_end_date=self.recurrence_end_date,
            parent_expense_id=self.id,
            employee_id=self.employee_id,
            vehicle_id=self.vehicle_id,
            project_id=self.project_id,
            recorded_by=self.recorded_by,
            budget_category=self.budget_category,
            gl_account=self.gl_account
        )
        if next_expense.save():
            return next_expense
        return None

    def calculate_next_recurrence_date(self):
        if not self.is_recurring or not self.recurrence_pattern:
            return None
        last_date = self.expense_date
        if self.recurring_children:
            last_child = max(self.recurring_children, key=lambda x: x.expense_date or date.min)
            last_date = last_child.expense_date
        if self.recurrence_end_date and last_date >= self.recurrence_end_date:
            return None
        if self.recurrence_pattern == 'daily':
            return last_date + timedelta(days=1)
        elif self.recurrence_pattern == 'weekly':
            return last_date + timedelta(weeks=1)
        elif self.recurrence_pattern == 'monthly':
            next_month = last_date.month + 1
            next_year = last_date.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            return last_date.replace(year=next_year, month=next_month)
        elif self.recurrence_pattern == 'quarterly':
            return last_date + timedelta(days=90)
        elif self.recurrence_pattern == 'yearly':
            return last_date.replace(year=last_date.year + 1)
        return None

    # ---------------- Related Entities ----------------
    def get_related_entities(self):
        entities = {}
        if self.employee:
            entities['employee'] = {
                'id': self.employee.id,
                'name': self.employee.name,
                'employee_id': getattr(self.employee, 'employee_id', None),
                'type': 'employee'
            }
        if self.vehicle:
            entities['vehicle'] = {
                'id': self.vehicle.id,
                'name': self.vehicle.registration_number,
                'type': 'vehicle'
            }
        if self.project:
            entities['project'] = {
                'id': self.project.id,
                'name': self.project.name,
                'type': 'project'
            }
        return entities

    # ---------------- Serialization ----------------
    def to_dict(self, include_related=True, include_financial_details=True):
        data = super().to_dict()
        data.update({
            'is_approved': self.is_approved,
            'is_paid': self.is_paid,
            'is_pending': self.is_pending,
            'is_rejected': self.is_rejected,
            'amount_in_default_currency': self.amount_in_default_currency,
            'total_amount_in_default_currency': self.total_amount_in_default_currency,
            'tax_rate': self.tax_rate,
            'age_in_days': self.age_in_days,
            'is_overdue': self.is_overdue,
            'days_overdue': self.days_overdue
        })
        # Format dates
        for field in ['expense_date', 'payment_date', 'due_date', 'approved_date', 'recurrence_end_date']:
            val = getattr(self, field, None)
            if val:
                data[field] = val.isoformat()
        data['tags_list'] = self.tags.split(',') if self.tags else []
        data['supporting_docs_list'] = self.supporting_docs_url.split(',') if self.supporting_docs_url else []
        if include_related:
            data['related_entities'] = self.get_related_entities()
            data['recorded_by_name'] = self.expense_recorder.full_name if self.expense_recorder else None
            data['approved_by_name'] = self.expense_approver.full_name if self.expense_approver else None
            if self.is_recurring:
                data['recurring_children_count'] = len(self.recurring_children)
                next_date = self.calculate_next_recurrence_date()
                data['next_recurrence_date'] = next_date.isoformat() if next_date else None
        if include_financial_details:
            data['financial_summary'] = {
                'amount': self.amount,
                'tax_amount': self.tax_amount,
                'total_amount': self.total_amount,
                'currency': self.currency,
                'exchange_rate': self.exchange_rate,
                'amount_aed': self.amount_in_default_currency,
                'total_amount_aed': self.total_amount_in_default_currency
            }
        return data

    # ---------------- Class Methods ----------------
    @classmethod
    def get_by_number(cls, expense_number):
        return cls.query.filter_by(expense_number=expense_number).first()

    @classmethod
    def get_expenses_by_type(cls, expense_type, start_date=None, end_date=None):
        query = cls.query.filter_by(expense_type=expense_type)
        if start_date:
            query = query.filter(cls.expense_date >= start_date)
        if end_date:
            query = query.filter(cls.expense_date <= end_date)
        return query.order_by(cls.expense_date.desc()).all()

    @classmethod
    def get_expenses_by_status(cls, status, start_date=None, end_date=None):
        query = cls.query.filter_by(status=status)
        if start_date:
            query = query.filter(cls.expense_date >= start_date)
        if end_date:
            query = query.filter(cls.expense_date <= end_date)
        return query.order_by(cls.expense_date.desc()).all()

    @classmethod
    def get_pending_approval(cls):
        return cls.query.filter_by(status='pending', requires_approval=True).order_by(cls.expense_date).all()

    @classmethod
    def get_overdue_expenses(cls):
        return cls.query.filter(cls.status.in_(['pending', 'approved']),
                                cls.due_date < datetime.utcnow().date()).order_by(cls.due_date).all()

    @classmethod
    def get_recurring_expenses(cls):
        return cls.query.filter_by(is_recurring=True).order_by(cls.expense_date).all()

    @classmethod
    def get_total_expenses(cls, start_date, end_date, expense_type=None, status=None):
        query = cls.query.filter(cls.expense_date >= start_date, cls.expense_date <= end_date)
        if expense_type:
            query = query.filter_by(expense_type=expense_type)
        if status:
            query = query.filter_by(status=status)
        expenses = query.all()
        return sum(exp.total_amount_in_default_currency for exp in expenses)

    @classmethod
    def get_expense_summary(cls, start_date, end_date, group_by='expense_type'):
        expenses = cls.query.filter(cls.expense_date >= start_date, cls.expense_date <= end_date).all()
        summary = {}
        for exp in expenses:
            group_value = getattr(exp, group_by, 'Unknown')
            if group_value not in summary:
                summary[group_value] = {'count': 0, 'total_amount': 0, 'total_amount_aed': 0, 'expenses': []}
            summary[group_value]['count'] += 1
            summary[group_value]['total_amount'] += exp.total_amount
            summary[group_value]['total_amount_aed'] += exp.total_amount_in_default_currency
            summary[group_value]['expenses'].append(exp.to_dict())
        return summary

    def get_project_name(self):
        from app.models.wps.project import Project
        project = Project.query.get(self.project_id)
        return project.name if project else None

    def __repr__(self):
        return f'<Expense {self.expense_number} - {self.expense_type.value} - {self.total_amount} {self.currency}>'
