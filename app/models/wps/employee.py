from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
import re

from sqlalchemy.orm import relationship, validates, joinedload
from app import db
from app.models.core.base import BaseModel, SoftDeleteMixin
from sqlalchemy import and_
from sqlalchemy.ext.hybrid import hybrid_property

class Employee(BaseModel, SoftDeleteMixin):
    __tablename__ = 'employee'

    id: int = db.Column(db.Integer, primary_key=True)
    employee_code: str = db.Column(db.String(20), unique=True, nullable=False, index=True)

    name: str = db.Column(db.String(100), nullable=False)
    emirates_id: str = db.Column(db.String(50), unique=True, nullable=False, index=True)
    passport_number: Optional[str] = db.Column(db.String(50), nullable=True)
    nationality: Optional[str] = db.Column(db.String(50), nullable=True)
    date_of_birth: Optional[date] = db.Column(db.Date, nullable=True)
    gender: Optional[str] = db.Column(db.String(10), nullable=True)
    marital_status: Optional[str] = db.Column(db.String(20), nullable=True)

    phone_number: str = db.Column(db.String(20), nullable=False)
    email: Optional[str] = db.Column(db.String(100), nullable=True)
    address: Optional[str] = db.Column(db.Text, nullable=True)
    emergency_contact_name: Optional[str] = db.Column(db.String(100), nullable=True)
    emergency_contact_phone: Optional[str] = db.Column(db.String(20), nullable=True)
    emergency_contact_relation: Optional[str] = db.Column(db.String(50), nullable=True)

    position: str = db.Column(db.String(100), nullable=False)
    department: str = db.Column(db.String(50), nullable=False)
    employment_type: str = db.Column(db.String(20), default='full_time')
    join_date: date = db.Column(db.Date, default=lambda: datetime.utcnow().date(), nullable=False)
    probation_period_end: Optional[date] = db.Column(db.Date, nullable=True)
    employment_contract_url: Optional[str] = db.Column(db.String(500), nullable=True)

    basic_salary: float = db.Column(db.Float, nullable=False)
    housing_allowance: float = db.Column(db.Float, default=0.0, nullable=False)
    transportation_allowance: float = db.Column(db.Float, default=0.0, nullable=False)
    other_allowances: float = db.Column(db.Float, default=0.0, nullable=False)
    overtime_rate: float = db.Column(db.Float, default=0.0, nullable=False)

    bank_name: Optional[str] = db.Column(db.String(100), nullable=True)
    bank_account: Optional[str] = db.Column(db.String(100), nullable=True)
    bank_iban: Optional[str] = db.Column(db.String(50), nullable=True)
    bank_branch: Optional[str] = db.Column(db.String(100), nullable=True)

    annual_leave_balance: float = db.Column(db.Float, default=0.0, nullable=False)
    sick_leave_balance: float = db.Column(db.Float, default=0.0, nullable=False)
    last_leave_update: Optional[date] = db.Column(db.Date, nullable=True)

    passport_copy_url: Optional[str] = db.Column(db.String(500), nullable=True)
    emirates_id_copy_url: Optional[str] = db.Column(db.String(500), nullable=True)
    photo_url: Optional[str] = db.Column(db.String(500), nullable=True)
    visa_copy_url: Optional[str] = db.Column(db.String(500), nullable=True)
    labor_card_url: Optional[str] = db.Column(db.String(500), nullable=True)

    qualifications: Optional[str] = db.Column(db.Text, nullable=True)
    skills: Optional[str] = db.Column(db.Text, nullable=True)
    languages: Optional[str] = db.Column(db.String(200), nullable=True)
    medical_conditions: Optional[str] = db.Column(db.Text, nullable=True)
    blood_group: Optional[str] = db.Column(db.String(5), nullable=True)

    employment_status: str = db.Column(db.String(20), default='active', nullable=False)
    last_promotion_date: Optional[date] = db.Column(db.Date, nullable=True)
    next_review_date: Optional[date] = db.Column(db.Date, nullable=True)

    # ---------------------------
    # Relationships
    # ---------------------------
    salaries = relationship('Salary', back_populates='employee', lazy='joined', cascade='all, delete-orphan')
    leave_records = relationship('EmployeeLeave', back_populates='employee', lazy='joined', cascade='all, delete-orphan')
    attendance_records = relationship('Attendance', back_populates='employee', lazy='joined', cascade='all, delete-orphan')

    # ---------------------------
    # Properties
    # ---------------------------
    @property
    def employee_id(self) -> int:
        return self.id

    @property
    def full_name(self) -> str:
        return self.name

    @property
    def total_salary(self) -> float:
        return self.basic_salary + self.housing_allowance + self.transportation_allowance + self.other_allowances

    @hybrid_property
    def is_active(self):
        return self.employment_status == 'active' and self.deleted_at is None

    @is_active.expression
    def is_active(cls):
        return and_(
            cls.employment_status == 'active',
            cls.deleted_at.is_(None)
        )



    @property
    def is_on_probation(self) -> bool:
        if self.probation_period_end:
            return datetime.utcnow().date() <= self.probation_period_end
        return False

    @property
    def age(self) -> Optional[int]:
        if self.date_of_birth:
            today = datetime.utcnow().date()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None

    @property
    def experience_years(self) -> int:
        if self.join_date:
            today = datetime.utcnow().date()
            return today.year - self.join_date.year - ((today.month, today.day) < (self.join_date.month, self.join_date.day))
        return 0

    @property
    def daily_rate(self) -> float:
        return self.total_salary / 30

    @property
    def hourly_rate(self) -> float:
        return self.daily_rate / 8

    # ---------------------------
    # Initialization
    # ---------------------------
        # ---------------------------
    # Initialization
    # ---------------------------
    def __init__(self, **kwargs: Any) -> None:
        # Convert string dates to date objects
        date_fields = ['join_date', 'date_of_birth', 'probation_period_end', 
                      'last_leave_update', 'last_promotion_date', 'next_review_date']
        for field in date_fields:
            if field in kwargs and isinstance(kwargs[field], str):
                try:
                    kwargs[field] = datetime.strptime(kwargs[field], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    # If conversion fails, set to None
                    kwargs[field] = None
        
        if 'employee_code' not in kwargs:
            kwargs['employee_code'] = self.generate_employee_code()
        
        if 'probation_period_end' not in kwargs and 'join_date' in kwargs:
            join_date = kwargs.get('join_date')
            if join_date:
                # Ensure join_date is a date object
                if isinstance(join_date, datetime):
                    join_date = join_date.date()
                kwargs['probation_period_end'] = join_date + timedelta(days=90)
        
        if 'overtime_rate' not in kwargs and 'basic_salary' in kwargs:
            kwargs['overtime_rate'] = kwargs['basic_salary'] / 30 / 8 * 1.5
        
        super().__init__(**kwargs)

    # ---------------------------
    # Validators
    # ---------------------------
    @validates('emirates_id')
    def validate_emirates_id(self, key: str, value: str) -> str:
        if not value:
            return value
    
        # Clean the input: remove spaces, dashes, and any other separators
        cleaned = re.sub(r'[-\s]', '', value)
    
        # Check if it's a valid Emirates ID number
        # Valid format: 784 followed by 12 digits (total 15 digits)
        if not re.match(r'^784\d{12}$', cleaned):
            raise ValueError("Invalid Emirates ID format. Expected format: 784-XXXX-XXXXXXX-X")
    
        # Format it properly: 784-XXXX-XXXXXXX-X
        formatted = f"{cleaned[:3]}-{cleaned[3:7]}-{cleaned[7:14]}-{cleaned[14]}"
        return formatted

    @validates('phone_number')
    def validate_phone_number(self, key: str, value: str) -> str:
        if not value:
            return value
    
        # Remove any non-digit characters
        digits = re.sub(r'\D', '', value)
    
        # Accept UAE format: 9 digits starting with 5
        if len(digits) == 9 and digits.startswith('5'):
            return f"+971{digits}"
    
        # Or accept existing international format
        if re.match(r'^\+?[\d\s\-\(\)]{10,}$', value):
            return value
    
        raise ValueError("Invalid phone number format. Expected: 9 digits starting with 5")

    @validates('email')
    def validate_email(self, key: str, value: Optional[str]) -> Optional[str]:
        if value and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise ValueError("Invalid email format")
        return value

    @validates('basic_salary')
    def validate_basic_salary(self, key: str, value: float) -> float:
        if value < 0:
            raise ValueError("Basic salary cannot be negative")
        return float(value)

    # ---------------------------
    # Utility
    # ---------------------------
    def generate_employee_code(self) -> str:
        from app.utils.employee_utils import generate_employee_id
        return generate_employee_id()

    # ---------------------------
    # Serialization with eager loading optimization
    # ---------------------------
    def to_dict(self, include_salary: bool = False, include_leave: bool = False, include_attendance: bool = False) -> Dict[str, Any]:
        """
        Serialize employee to dict including optional salary, leave, and attendance data
        without triggering N+1 queries.
        """
        data: Dict[str, Any] = super().to_dict()
        data.update({
            'full_name': self.full_name,
            'total_salary': self.total_salary,
            'is_active': self.is_active,
            'is_on_probation': self.is_on_probation,
            'age': self.age,
            'experience_years': self.experience_years,
            'daily_rate': self.daily_rate,
            'hourly_rate': self.hourly_rate
        })

        # Format dates
        for field in ['date_of_birth', 'join_date', 'probation_period_end', 'last_leave_update', 'last_promotion_date', 'next_review_date']:
            value = getattr(self, field)
            if value:
                data[field] = value.isoformat()

        # Languages list
        if self.languages:
            data['languages_list'] = self.languages.split(',')

        # Salary, Leave, Attendance
        if include_salary:
            data['salary_structure'] = {
                'basic_salary': self.basic_salary,
                'housing_allowance': self.housing_allowance,
                'transportation_allowance': self.transportation_allowance,
                'other_allowances': self.other_allowances,
                'total_salary': self.total_salary,
                'overtime_rate': self.overtime_rate
            }
            data['recent_salaries'] = [s.to_dict() for s in self.salaries[:12]]  # eager-loaded

        if include_leave:
            data['leave_records'] = [l.to_dict() for l in self.leave_records]  # eager-loaded

        if include_attendance:
            data['attendance_records'] = [a.to_dict() for a in self.attendance_records]  # eager-loaded

        return data

    def __repr__(self) -> str:
        return f"<Employee {self.name} ({self.employee_code})>"
