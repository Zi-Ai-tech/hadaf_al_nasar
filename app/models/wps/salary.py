from app import db
from app.models.core.base import BaseModel
from app.constants import SalaryStatus
from datetime import datetime
from sqlalchemy.orm import relationship, validates
import json

class Salary(BaseModel):
    """
    Salary model for Workforce and Payroll System (WPS)
    Manages salary processing, calculations, payments, and compliance for employees
    """
    __tablename__ = 'salary'
    
    # Salary Identification
    salary_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Employee and Period
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    
    # Salary Components (Basic Structure)
    basic_salary = db.Column(db.Float, nullable=False)
    housing_allowance = db.Column(db.Float, default=0.0, nullable=False)
    transportation_allowance = db.Column(db.Float, default=0.0, nullable=False)
    other_allowances = db.Column(db.Float, default=0.0, nullable=False)
    
    # Overtime Calculation
    overtime_hours = db.Column(db.Float, default=0.0, nullable=False)
    overtime_rate = db.Column(db.Float, default=0.0, nullable=False)
    overtime_amount = db.Column(db.Float, default=0.0, nullable=False)
    
    # Bonuses and Incentives (Stored as JSON for flexibility)
    bonuses_data = db.Column(db.Text, nullable=True)  # JSON string for bonus details
    incentives_amount = db.Column(db.Float, default=0.0, nullable=False)
    
    # Deductions (Stored as JSON for flexibility)
    deductions_data = db.Column(db.Text, nullable=True)  # JSON string for deduction details
    deductions_amount = db.Column(db.Float, default=0.0, nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'month', 'year',                           
                            name='uq_salary_employee_month_year'),
    )

    # Tax and Social Security
    tax_amount = db.Column(db.Float, default=0.0, nullable=False)
    social_security_amount = db.Column(db.Float, default=0.0, nullable=False)
    other_deductions = db.Column(db.Float, default=0.0, nullable=False)
    
    # Final Calculations
    gross_salary = db.Column(db.Float, nullable=False)
    total_deductions = db.Column(db.Float, default=0.0, nullable=False)
    net_salary = db.Column(db.Float, nullable=False)
    
    # Payment Information
    status = db.Column(db.Enum(SalaryStatus), default=SalaryStatus.PENDING, nullable=False)
    payment_date = db.Column(db.Date, nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)  # bank_transfer, cash, cheque
    payment_reference = db.Column(db.String(100), nullable=True)
    bank_account = db.Column(db.String(100), nullable=True)
    
    # Attendance and Leave Impact
    working_days = db.Column(db.Integer, default=0, nullable=False)
    actual_worked_days = db.Column(db.Integer, default=0, nullable=False)
    leave_days = db.Column(db.Integer, default=0, nullable=False)
    absent_days = db.Column(db.Integer, default=0, nullable=False)
    
    # WPS Compliance (UAE Specific)
    wps_salary_file_url = db.Column(db.String(500), nullable=True)
    wps_submission_date = db.Column(db.DateTime, nullable=True)
    wps_status = db.Column(db.String(50), nullable=True)  # submitted, processed, failed
    wps_reference = db.Column(db.String(100), nullable=True)
    
    # Approval and Processing
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    processed_date = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_date = db.Column(db.DateTime, nullable=True)
    
    # Additional Information
    notes = db.Column(db.Text, nullable=True)
    salary_slip_url = db.Column(db.String(500), nullable=True)
    
    # Relationships - FIXED: Using string references for User model
    employee = relationship('Employee', back_populates='salaries')
    processor = relationship('User', foreign_keys=[processed_by], backref='salaries_processed')
    approver = relationship('User', foreign_keys=[approved_by], backref='salaries_approved')
    notifications = relationship('SalaryNotification', backref='salary', lazy='dynamic',
                               cascade='all, delete-orphan')
    
    # In models/wps/salary.py

    def __init__(self, **kwargs):
        """
        Initialize salary with automatic number generation and calculations
        """
        if 'salary_number' not in kwargs:
            kwargs['salary_number'] = self.generate_salary_number()
    
        # Calculate derived fields if not provided
        if 'overtime_amount' not in kwargs and 'overtime_hours' in kwargs and 'overtime_rate' in kwargs:
            kwargs['overtime_amount'] = kwargs['overtime_hours'] * kwargs['overtime_rate']
    
        # FIRST initialize the object with provided kwargs
        super().__init__(**kwargs)
    
        # THEN calculate gross salary and other fields if not provided
        if 'gross_salary' not in kwargs:
            self.gross_salary = self.calculate_gross_salary()
    
        if 'total_deductions' not in kwargs:
            self.total_deductions = self.calculate_total_deductions()
    
        if 'net_salary' not in kwargs:
            self.net_salary = self.gross_salary - self.total_deductions
    
    @validates('month')
    def validate_month(self, key, month):
        """Validate month is between 1-12"""
        if not 1 <= month <= 12:
            raise ValueError("Month must be between 1 and 12")
        return month
    
    @validates('year')
    def validate_year(self, key, year):
        """Validate year is reasonable"""
        current_year = datetime.now().year
        if year < 2000 or year > current_year + 1:
            raise ValueError(f"Year must be between 2000 and {current_year + 1}")
        return year
    
    @property
    def is_paid(self):
        """Check if salary is paid"""
        return self.status == SalaryStatus.PAID
    
    @property
    def is_pending(self):
        """Check if salary is pending"""
        return self.status == SalaryStatus.PENDING
    
    @property
    def is_processed(self):
        """Check if salary is processed"""
        return self.status in [SalaryStatus.PROCESSED, SalaryStatus.PAID]
    
    @property
    def period_name(self):
        """Get salary period name (e.g., 'June 2024')"""
        from datetime import datetime
        return datetime(self.year, self.month, 1).strftime('%B %Y')
    
    @property
    def attendance_rate(self):
        """Calculate attendance rate percentage"""
        if self.working_days > 0:
            return (self.actual_worked_days / self.working_days) * 100
        return 0
    
    @property
    def basic_salary_per_day(self):
        """Calculate basic salary per day"""
        if self.working_days > 0:
            return self.basic_salary / self.working_days
        return 0
    
    @property
    def net_salary_per_day(self):
        """Calculate net salary per day"""
        if self.working_days > 0:
            return self.net_salary / self.working_days
        return 0
    
    @property
    def bonuses_list(self):
        """Get bonuses as list from JSON data"""
        if self.bonuses_data:
            try:
                return json.loads(self.bonuses_data)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    @property
    def deductions_list(self):
        """Get deductions as list from JSON data"""
        if self.deductions_data:
            try:
                return json.loads(self.deductions_data)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def generate_salary_number(self):
        """
        Generate automatic salary number
        Format: SAL-YYYY-MM-EMP-XXXX
        """
        from app.utils.salary_utils import generate_salary_number
        return generate_salary_number()
    
    def calculate_gross_salary(self, data=None):
        """
        Calculate gross salary from components
        
        Args:
            data (dict): Optional data to use for calculation
            
        Returns:
            float: Gross salary amount
        """
        if data is None:
            data = {
                'basic_salary': self.basic_salary,
                'housing_allowance': self.housing_allowance,
                'transportation_allowance': self.transportation_allowance,
                'other_allowances': self.other_allowances,
                'overtime_amount': self.overtime_amount,
                'incentives_amount': self.incentives_amount
            }
        
        return (data.get('basic_salary', 0) + 
                data.get('housing_allowance', 0) + 
                data.get('transportation_allowance', 0) + 
                data.get('other_allowances', 0) + 
                data.get('overtime_amount', 0) + 
                data.get('incentives_amount', 0))
    
    def calculate_total_deductions(self, data=None):
        """
        Calculate total deductions
        
        Args:
            data (dict): Optional data to use for calculation
            
        Returns:
            float: Total deductions amount
        """
        if data is None:
            data = {
                'deductions_amount': self.deductions_amount,
                'tax_amount': self.tax_amount,
                'social_security_amount': self.social_security_amount,
                'other_deductions': self.other_deductions
            }
        
        return (data.get('deductions_amount', 0) + 
                data.get('tax_amount', 0) + 
                data.get('social_security_amount', 0) + 
                data.get('other_deductions', 0))
    
    def recalculate_salary(self):
        """
        Recalculate all salary components and totals
        
        Returns:
            bool: True if recalculated successfully
        """
        # Recalculate overtime
        self.overtime_amount = self.overtime_hours * self.overtime_rate
        
        # Recalculate gross salary
        self.gross_salary = self.calculate_gross_salary()
        
        # Recalculate total deductions
        self.total_deductions = self.calculate_total_deductions()
        
        # Recalculate net salary
        self.net_salary = self.gross_salary - self.total_deductions
        
        return self.save()
    
    def add_bonus(self, description, amount, bonus_type='performance', effective_date=None):
        """
        Add bonus to salary
        
        Args:
            description (str): Bonus description
            amount (float): Bonus amount
            bonus_type (str): Type of bonus
            effective_date (date): Effective date
            
        Returns:
            bool: True if bonus was added
        """
        bonuses = self.bonuses_list
        
        bonus = {
            'id': len(bonuses) + 1,
            'description': description,
            'amount': amount,
            'type': bonus_type,
            'effective_date': effective_date.isoformat() if effective_date else datetime.utcnow().date().isoformat(),
            'added_date': datetime.utcnow().isoformat()
        }
        
        bonuses.append(bonus)
        self.bonuses_data = json.dumps(bonuses, ensure_ascii=False)
        self.incentives_amount += amount
        self.gross_salary += amount
        self.net_salary += amount
        
        return self.save()
    
    def remove_bonus(self, bonus_id):
        """
        Remove bonus from salary
        
        Args:
            bonus_id (int): Bonus ID to remove
            
        Returns:
            bool: True if bonus was removed
        """
        bonuses = self.bonuses_list
        original_count = len(bonuses)
        
        bonuses = [bonus for bonus in bonuses if bonus.get('id') != bonus_id]
        
        if len(bonuses) < original_count:
            # Recalculate incentives amount
            self.incentives_amount = sum(bonus['amount'] for bonus in bonuses)
            self.bonuses_data = json.dumps(bonuses, ensure_ascii=False)
            
            # Recalculate totals
            return self.recalculate_salary()
        
        return False
    
    def add_deduction(self, description, amount, deduction_type='other', reason=None, effective_date=None):
        """
        Add deduction to salary
        
        Args:
            description (str): Deduction description
            amount (float): Deduction amount
            deduction_type (str): Type of deduction
            reason (str): Deduction reason
            effective_date (date): Effective date
            
        Returns:
            bool: True if deduction was added
        """
        deductions = self.deductions_list
        
        deduction = {
            'id': len(deductions) + 1,
            'description': description,
            'amount': amount,
            'type': deduction_type,
            'reason': reason,
            'effective_date': effective_date.isoformat() if effective_date else datetime.utcnow().date().isoformat(),
            'added_date': datetime.utcnow().isoformat()
        }
        
        deductions.append(deduction)
        self.deductions_data = json.dumps(deductions, ensure_ascii=False)
        self.deductions_amount += amount
        self.total_deductions += amount
        self.net_salary -= amount
        
        return self.save()
    
    def remove_deduction(self, deduction_id):
        """
        Remove deduction from salary
        
        Args:
            deduction_id (int): Deduction ID to remove
            
        Returns:
            bool: True if deduction was removed
        """
        deductions = self.deductions_list
        original_count = len(deductions)
        
        deductions = [deduction for deduction in deductions if deduction.get('id') != deduction_id]
        
        if len(deductions) < original_count:
            # Recalculate deductions amount
            self.deductions_amount = sum(deduction['amount'] for deduction in deductions)
            self.deductions_data = json.dumps(deductions, ensure_ascii=False)
            
            # Recalculate totals
            return self.recalculate_salary()
        
        return False
    
    def mark_as_processed(self, processed_by_user_id, notes=None):
        """
        Mark salary as processed
        
        Args:
            processed_by_user_id (int): User ID who processed
            notes (str): Processing notes
            
        Returns:
            bool: True if marked as processed successfully
        """
        if self.status != SalaryStatus.PENDING:
            raise ValueError("Salary is not in pending status")
        
        self.status = SalaryStatus.PROCESSED
        self.processed_by = processed_by_user_id
        self.processed_date = datetime.utcnow()
        
        if notes:
            self.notes = f"{self.notes or ''}\nProcessed: {notes}".strip()
        
        return self.save()
    
    def mark_as_paid(self, payment_date=None, payment_method=None, payment_reference=None, approved_by_user_id=None):
        """
        Mark salary as paid
        
        Args:
            payment_date (date): Payment date
            payment_method (str): Payment method
            payment_reference (str): Payment reference
            approved_by_user_id (int): User ID who approved payment
            
        Returns:
            bool: True if marked as paid successfully
        """
        if self.status not in [SalaryStatus.PENDING, SalaryStatus.PROCESSED]:
            raise ValueError("Salary must be pending or processed to mark as paid")
        
        self.status = SalaryStatus.PAID
        self.payment_date = payment_date or datetime.utcnow().date()
        
        if payment_method:
            self.payment_method = payment_method
        if payment_reference:
            self.payment_reference = payment_reference
        if approved_by_user_id:
            self.approved_by = approved_by_user_id
            self.approved_date = datetime.utcnow()
        
        return self.save()
    
    def mark_as_cancelled(self, cancelled_by_user_id, reason):
        """
        Mark salary as cancelled
        
        Args:
            cancelled_by_user_id (int): User ID who cancelled
            reason (str): Cancellation reason
            
        Returns:
            bool: True if marked as cancelled successfully
        """
        self.status = SalaryStatus.CANCELLED
        self.processed_by = cancelled_by_user_id
        self.processed_date = datetime.utcnow()
        
        if reason:
            self.notes = f"{self.notes or ''}\nCancelled: {reason}".strip()
        
        return self.save()
    
    def generate_salary_slip_data(self):
        """
        Generate data for salary slip
        
        Returns:
            dict: Salary slip data
        """
        employee_name = "Unknown"
        employee_info = {}
        
        # Safely access employee info
        if hasattr(self, 'employee') and self.employee:
            employee_info = {
                'name': self.employee.name,
                'employee_id': self.employee.employee_id,
                'position': self.employee.position,
                'department': self.employee.department,
                'bank_account': getattr(self.employee, 'bank_account', None),
                'bank_name': getattr(self.employee, 'bank_name', None)
            }
            employee_name = self.employee.name
        
        return {
            'salary_number': self.salary_number,
            'employee': employee_info,
            'period': {
                'month': self.month,
                'year': self.year,
                'name': self.period_name
            },
            'earnings': {
                'basic_salary': self.basic_salary,
                'housing_allowance': self.housing_allowance,
                'transportation_allowance': self.transportation_allowance,
                'other_allowances': self.other_allowances,
                'overtime_amount': self.overtime_amount,
                'incentives_amount': self.incentives_amount,
                'gross_salary': self.gross_salary
            },
            'deductions': {
                'tax_amount': self.tax_amount,
                'social_security_amount': self.social_security_amount,
                'other_deductions': self.other_deductions,
                'deductions_amount': self.deductions_amount,
                'total_deductions': self.total_deductions
            },
            'summary': {
                'gross_salary': self.gross_salary,
                'total_deductions': self.total_deductions,
                'net_salary': self.net_salary
            },
            'attendance': {
                'working_days': self.working_days,
                'actual_worked_days': self.actual_worked_days,
                'leave_days': self.leave_days,
                'absent_days': self.absent_days,
                'attendance_rate': self.attendance_rate
            },
            'payment': {
                'status': self.status.value,
                'payment_date': self.payment_date.isoformat() if self.payment_date else None,
                'payment_method': self.payment_method,
                'payment_reference': self.payment_reference
            },
            'additional': {
                'bonuses': self.bonuses_list,
                'deductions': self.deductions_list,
                'notes': self.notes
            }
        }
    
    def prepare_wps_data(self):
        """
        Prepare data for WPS (Wage Protection System) submission
        
        Returns:
            dict: WPS compliant salary data
        """
        # UAE WPS requires specific format for salary data
        wps_data = {
            'salary_id': self.salary_number,
            'employee_id': getattr(self.employee, 'employee_id', 'Unknown') if hasattr(self, 'employee') and self.employee else 'Unknown',
            'employee_name': getattr(self.employee, 'name', 'Unknown') if hasattr(self, 'employee') and self.employee else 'Unknown',
            'employee_id_number': getattr(self.employee, 'emirates_id', '') if hasattr(self, 'employee') and self.employee else '',
            'bank_code': self._get_bank_code(getattr(self.employee, 'bank_name', '')) if hasattr(self, 'employee') and self.employee else 'OTHER',
            'bank_account': getattr(self.employee, 'bank_account', '') if hasattr(self, 'employee') and self.employee else '',
            'salary_amount': self.net_salary,
            'salary_currency': 'AED',
            'salary_date': self.payment_date.isoformat() if self.payment_date else datetime.utcnow().date().isoformat(),
            'payment_method': 'BANK_TRANSFER',  # WPS typically requires bank transfer
            'working_days': self.working_days
        }
        
        return wps_data
    
    def _get_bank_code(self, bank_name):
        """
        Map bank name to WPS bank code
        
        Args:
            bank_name (str): Bank name
            
        Returns:
            str: Bank code for WPS
        """
        bank_codes = {
            'Emirates NBD': 'EIB',
            'Mashreq Bank': 'MSHQ',
            'Dubai Islamic Bank': 'DIB',
            'Abu Dhabi Commercial Bank': 'ADCB',
            'First Abu Dhabi Bank': 'FAB',
            'RAK Bank': 'RAK',
            'Commercial Bank of Dubai': 'CBD'
        }
        
        return bank_codes.get(bank_name, 'OTHER')
    
    def to_dict(self, include_employee=False, include_breakdown=True, include_wps=False):
        """
        Convert salary to dictionary
        
        Args:
            include_employee (bool): Include employee details
            include_breakdown (bool): Include salary breakdown
            include_wps (bool): Include WPS information
            
        Returns:
            dict: Salary data
        """
        data = super().to_dict()
        
        # Add computed properties
        data['is_paid'] = self.is_paid
        data['is_pending'] = self.is_pending
        data['is_processed'] = self.is_processed
        data['period_name'] = self.period_name
        data['attendance_rate'] = self.attendance_rate
        data['basic_salary_per_day'] = self.basic_salary_per_day
        data['net_salary_per_day'] = self.net_salary_per_day
        
        # Format dates
        if self.payment_date:
            data['payment_date'] = self.payment_date.isoformat()
        if self.processed_date:
            data['processed_date'] = self.processed_date.isoformat()
        if self.approved_date:
            data['approved_date'] = self.approved_date.isoformat()
        if self.wps_submission_date:
            data['wps_submission_date'] = self.wps_submission_date.isoformat()
        
        # Include related data
        if include_employee and hasattr(self, 'employee') and self.employee:
            data['employee'] = {
                'id': self.employee.id,
                'name': self.employee.name,
                'employee_id': self.employee.employee_id,
                'position': getattr(self.employee, 'position', None),
                'department': getattr(self.employee, 'department', None),
                'bank_name': getattr(self.employee, 'bank_name', None),
                'bank_account': getattr(self.employee, 'bank_account', None)
            }
        
        if include_breakdown:
            data['breakdown'] = {
                'earnings': {
                    'basic_salary': self.basic_salary,
                    'housing_allowance': self.housing_allowance,
                    'transportation_allowance': self.transportation_allowance,
                    'other_allowances': self.other_allowances,
                    'overtime': {
                        'hours': self.overtime_hours,
                        'rate': self.overtime_rate,
                        'amount': self.overtime_amount
                    },
                    'incentives': self.incentives_amount,
                    'gross_salary': self.gross_salary
                },
                'deductions': {
                    'tax': self.tax_amount,
                    'social_security': self.social_security_amount,
                    'other': self.other_deductions,
                    'additional': self.deductions_amount,
                    'total_deductions': self.total_deductions
                },
                'net_salary': self.net_salary,
                'bonuses': self.bonuses_list,
                'deductions_list': self.deductions_list
            }
        
        if include_wps:
            data['wps_info'] = {
                'wps_status': self.wps_status,
                'wps_reference': self.wps_reference,
                'wps_submission_date': self.wps_submission_date.isoformat() if self.wps_submission_date else None,
                'wps_salary_file_url': self.wps_salary_file_url
            }
        
        # Include processor/approver names (using safe access)
        if hasattr(self, 'processor') and self.processor:
            data['processed_by_name'] = self.processor.full_name
        else:
            data['processed_by_name'] = None
            
        if hasattr(self, 'approver') and self.approver:
            data['approved_by_name'] = self.approver.full_name
        else:
            data['approved_by_name'] = None
        
        return data
    
    def validate_salary_data(self):
        """
        Validate that all salary data is complete
        """
        required_fields = ['basic_salary', 'gross_salary', 'total_deductions', 'net_salary']
    
        for field in required_fields:
            if getattr(self, field) is None:
                raise ValueError(f"Missing required field: {field}")
    
        # Ensure deductions are properly calculated
        expected_total_deductions = self.calculate_total_deductions()
        if abs(self.total_deductions - expected_total_deductions) > 0.01:  # Allow small floating point differences
            raise ValueError(f"Total deductions mismatch. Expected: {expected_total_deductions}, Got: {self.total_deductions}")
    
        return True
    
    @classmethod
    def get_by_period(cls, month, year, employee_id=None):
        """
        Get salaries by period
        
        Args:
            month (int): Month (1-12)
            year (int): Year
            employee_id (int): Optional employee filter
            
        Returns:
            list: List of salaries for the period
        """
        query = cls.query.filter_by(month=month, year=year)
        
        if employee_id:
            query = query.filter_by(employee_id=employee_id)
        
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_by_employee(cls, employee_id, status=None, start_date=None, end_date=None):
        """
        Get salaries for a specific employee
        
        Args:
            employee_id (int): Employee ID
            status (SalaryStatus): Filter by status
            start_date (date): Start date filter
            end_date (date): End date filter
            
        Returns:
            list: List of employee salaries
        """
        query = cls.query.filter_by(employee_id=employee_id)
        
        if status:
            query = query.filter_by(status=status)
        
        # Date filtering based on payment date or created date
        if start_date:
            query = query.filter(cls.payment_date >= start_date if cls.payment_date else cls.created_at >= start_date)
        if end_date:
            query = query.filter(cls.payment_date <= end_date if cls.payment_date else cls.created_at <= end_date)
        
        return query.order_by(cls.year.desc(), cls.month.desc()).all()
    
    @classmethod
    def get_pending_salaries(cls, month=None, year=None):
        """
        Get pending salaries
        
        Args:
            month (int): Optional month filter
            year (int): Optional year filter
            
        Returns:
            list: List of pending salaries
        """
        query = cls.query.filter_by(status=SalaryStatus.PENDING)
        
        if month and year:
            query = query.filter_by(month=month, year=year)
        
        return query.order_by(cls.created_at).all()
    
    @classmethod
    def get_unpaid_salaries(cls, month=None, year=None):
        """
        Get unpaid salaries (pending or processed but not paid)
        
        Args:
            month (int): Optional month filter
            year (int): Optional year filter
            
        Returns:
            list: List of unpaid salaries
        """
        query = cls.query.filter(
            cls.status.in_([SalaryStatus.PENDING, SalaryStatus.PROCESSED])
        )
        
        if month and year:
            query = query.filter_by(month=month, year=year)
        
        return query.order_by(cls.created_at).all()
    
    @classmethod
    def get_salary_summary(cls, month, year, department=None):
        """
        Get salary summary for a period
        
        Args:
            month (int): Month
            year (int): Year
            department (str): Optional department filter
            
        Returns:
            dict: Salary summary
        """
        from app.models.wps.employee import Employee
        
        query = cls.query.filter_by(month=month, year=year)
        
        if department:
            query = query.join(Employee).filter(Employee.department == department)
        
        salaries = query.all()
        
        total_salaries = len(salaries)
        paid_salaries = len([s for s in salaries if s.is_paid])
        pending_salaries = len([s for s in salaries if s.is_pending])
        
        total_gross = sum(s.gross_salary for s in salaries)
        total_deductions = sum(s.total_deductions for s in salaries)
        total_net = sum(s.net_salary for s in salaries)
        
        return {
            'period': f"{month}/{year}",
            'total_salaries': total_salaries,
            'paid_salaries': paid_salaries,
            'pending_salaries': pending_salaries,
            'payment_rate': (paid_salaries / total_salaries * 100) if total_salaries > 0 else 0,
            'total_gross': total_gross,
            'total_deductions': total_deductions,
            'total_net': total_net,
            'average_salary': total_net / total_salaries if total_salaries > 0 else 0,
            'department': department or 'All'
        }
    
    def __repr__(self):
        employee_name = getattr(self.employee, 'name', 'Unknown') if hasattr(self, 'employee') and self.employee else 'Unknown'
        return f'<Salary {self.salary_number} - {employee_name} - {self.month}/{self.year} - {self.net_salary} AED>'


class SalaryNotification(BaseModel):
    """
    Salary notification tracking for WPS compliance and employee communication
    """
    __tablename__ = 'salary_notification'
    
    id = db.Column(db.Integer, primary_key=True)
    salary_id = db.Column(db.Integer, db.ForeignKey('salary.id'), nullable=False)
    notification_type = db.Column(db.String(20), nullable=False)  # whatsapp, sms, email, wps
    recipient = db.Column(db.String(100), nullable=False)  # phone number, email, etc.
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, sent, failed, delivered
    message = db.Column(db.Text, nullable=True)
    response_data = db.Column(db.Text, nullable=True)  # JSON response from service provider
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        """Convert notification to dictionary"""
        return {
            'id': self.id,
            'salary_id': self.salary_id,
            'notification_type': self.notification_type,
            'recipient': self.recipient,
            'status': self.status,
            'message': self.message,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<SalaryNotification {self.notification_type} for Salary {self.salary_id}>'