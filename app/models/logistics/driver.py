"""
Driver model for logistics and transportation operations
"""
from app import db
from app.models.core.base import BaseModel, SoftDeleteMixin
from datetime import datetime
from sqlalchemy.orm import relationship, validates
import re

class Driver(BaseModel, SoftDeleteMixin):
    """
    Driver model for logistics and transportation operations
    """
    __tablename__ = 'driver'
    
    # [ALL YOUR EXISTING FIELDS - KEEP THEM EXACTLY AS THEY WERE]
    name = db.Column(db.String(100), nullable=False)
    emirates_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    passport_number = db.Column(db.String(50), nullable=True)
    nationality = db.Column(db.String(50), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    address = db.Column(db.Text, nullable=True)
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_phone = db.Column(db.String(20), nullable=True)
    emergency_contact_relation = db.Column(db.String(50), nullable=True)
    license_number = db.Column(db.String(50), nullable=False, index=True)
    license_type = db.Column(db.String(20), nullable=False, default='light')
    license_issuing_authority = db.Column(db.String(100), nullable=True)
    license_issue_date = db.Column(db.Date, nullable=True)
    license_expiry_date = db.Column(db.Date, nullable=False)
    license_classes = db.Column(db.String(200), nullable=True)
    employee_id = db.Column(db.String(50), nullable=True, unique=True, index=True)
    join_date = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    employment_type = db.Column(db.String(20), default='full_time')
    department = db.Column(db.String(50), default='logistics')
    position = db.Column(db.String(50), default='driver')
    status = db.Column(db.String(20), default='available', nullable=False)
    current_location = db.Column(db.String(100), nullable=True)
    last_active = db.Column(db.DateTime, nullable=True)
    current_vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    preferred_vehicle_types = db.Column(db.String(200), nullable=True)
    total_trips = db.Column(db.Integer, default=0, nullable=False)
    total_distance = db.Column(db.Float, default=0.0, nullable=False)
    average_rating = db.Column(db.Float, default=0.0, nullable=False)
    rating_count = db.Column(db.Integer, default=0, nullable=False)
    passport_copy_url = db.Column(db.String(500), nullable=True)
    license_copy_url = db.Column(db.String(500), nullable=True)
    id_copy_url = db.Column(db.String(500), nullable=True)
    medical_certificate_url = db.Column(db.String(500), nullable=True)
    medical_certificate_expiry = db.Column(db.Date, nullable=True)
    blood_group = db.Column(db.String(5), nullable=True)
    medical_conditions = db.Column(db.Text, nullable=True)
    special_skills = db.Column(db.Text, nullable=True)
    languages = db.Column(db.String(200), nullable=True)
    
    # Relationships - TEMPORARILY SIMPLIFIED
    # performance_records = relationship('DriverPerformance', backref='driver_performance_records')
    # assignments = relationship('DriverAssignment', backref='driver', lazy='dynamic')
    # payments = relationship('Payment', backref='driver', lazy='dynamic', foreign_keys='Payment.driver_id')
    
    # Relationships
    current_vehicle = relationship("Vehicle", back_populates="current_driver")
    def __init__(self, **kwargs):
        """
        Initialize driver with automatic employee ID generation
        and string-to-date conversion for date fields
        """
        # Convert string dates to date objects
        date_fields = [
            'date_of_birth', 
            'license_issue_date', 
            'license_expiry_date', 
            'join_date', 
            'medical_certificate_expiry'
        ]
        
        datetime_fields = ['last_active']
        
        # Convert date fields (string to date)
        for field in date_fields:
            if field in kwargs and isinstance(kwargs[field], str):
                try:
                    # Try ISO format first, then other common formats
                    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
                        try:
                            kwargs[field] = datetime.strptime(kwargs[field], fmt).date()
                            break
                        except ValueError:
                            continue
                    else:
                        # If conversion fails, set to None
                        kwargs[field] = None
                except (ValueError, TypeError, AttributeError):
                    kwargs[field] = None
        
        # Convert datetime fields (string to datetime)
        for field in datetime_fields:
            if field in kwargs and isinstance(kwargs[field], str):
                try:
                    # Try multiple datetime formats
                    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
                        try:
                            kwargs[field] = datetime.strptime(kwargs[field], fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        # If none of the formats work, set to None
                        kwargs[field] = None
                except (ValueError, TypeError, AttributeError):
                    kwargs[field] = None
        
        # Generate employee_id if not provided
        if 'employee_id' not in kwargs:
            kwargs['employee_id'] = self.generate_employee_id()
        
        # Validate and set license_expiry_date if not provided but license_issue_date exists
        if 'license_expiry_date' not in kwargs and 'license_issue_date' in kwargs:
            license_issue_date = kwargs.get('license_issue_date')
            if license_issue_date and isinstance(license_issue_date, (date, datetime)):
                # Default: license expires 5 years from issue date
                if isinstance(license_issue_date, datetime):
                    license_issue_date = license_issue_date.date()
                from datetime import timedelta
                kwargs['license_expiry_date'] = license_issue_date + timedelta(days=5*365)
        
        super().__init__(**kwargs)
    
    @validates('phone')
    def validate_phone(self, key, phone):
        """Validate phone number format"""
        if phone and not re.match(r'^\+?[\d\s\-\(\)]{10,}$', phone):
            raise ValueError("Invalid phone number format")
        return phone
    
    @validates('email')
    def validate_email(self, key, email):
        """Validate email format"""
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValueError("Invalid email format")
        return email
    
    @validates('emirates_id')
    def validate_emirates_id(self, key, emirates_id):
        """Validate Emirates ID format"""
        if not emirates_id:
            return emirates_id
    
        # Clean the input
        cleaned = re.sub(r'[-\s]', '', str(emirates_id))
    
        # Check if it's a valid Emirates ID number
        if not re.match(r'^784\d{12}$', cleaned):
            raise ValueError("Invalid Emirates ID format. Use format: 784-XXXX-XXXXXXX-X")
    
        # Format it properly
        formatted = f"{cleaned[:3]}-{cleaned[3:7]}-{cleaned[7:14]}-{cleaned[14]}"
        return formatted
    
    @property
    def is_available(self):
        """Check if driver is available"""
        return self.status == 'available' and self.is_active
    
    @property
    def is_assigned(self):
        """Check if driver is assigned"""
        return self.status == 'assigned'
    
    @property
    def is_on_leave(self):
        """Check if driver is on leave"""
        return self.status == 'on_leave'
    
    @property
    def license_is_valid(self):
        """Check if license is valid"""
        if not self.license_expiry_date:
            return False
        return self.license_expiry_date > datetime.utcnow().date()
    
    @property
    def medical_certificate_is_valid(self):
        """Check if medical certificate is valid"""
        if not self.medical_certificate_expiry:
            return False
        return self.medical_certificate_expiry > datetime.utcnow().date()
    
    @property
    def age(self):
        """Calculate driver's age"""
        if self.date_of_birth:
            today = datetime.utcnow().date()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    @property
    def experience_years(self):
        """Calculate years of experience"""
        if self.join_date:
            today = datetime.utcnow().date()
            return today.year - self.join_date.year - (
                (today.month, today.day) < (self.join_date.month, self.join_date.day)
            )
        return 0
    
    def generate_employee_id(self):
        """
        Generate automatic employee ID
        Format: DRV-YYYY-XXXX
        """
        from datetime import datetime
        year = datetime.now().year
        last_driver = Driver.query.order_by(Driver.id.desc()).first()
        sequence = (last_driver.id + 1) if last_driver else 1
        return f"DRV-{year}-{sequence:04d}"
    
    def to_dict(self, include_assignments=False, include_performance=False):
        """
        Convert driver to dictionary
        """
        data = super().to_dict()
        
        # Add computed properties
        data['is_available'] = self.is_available
        data['is_assigned'] = self.is_assigned
        data['is_on_leave'] = self.is_on_leave
        data['license_is_valid'] = self.license_is_valid
        data['medical_certificate_is_valid'] = self.medical_certificate_is_valid
        data['age'] = self.age
        data['experience_years'] = self.experience_years
        
        # Format dates
        if self.date_of_birth:
            data['date_of_birth'] = self.date_of_birth.isoformat()
        if self.license_issue_date:
            data['license_issue_date'] = self.license_issue_date.isoformat()
        if self.license_expiry_date:
            data['license_expiry_date'] = self.license_expiry_date.isoformat()
        if self.join_date:
            data['join_date'] = self.join_date.isoformat()
        if self.medical_certificate_expiry:
            data['medical_certificate_expiry'] = self.medical_certificate_expiry.isoformat()
        if self.last_active:
            data['last_active'] = self.last_active.isoformat()
        
        # Parse comma-separated fields
        if self.license_classes:
            data['license_classes_list'] = self.license_classes.split(',')
        if self.preferred_vehicle_types:
            data['preferred_vehicle_types_list'] = self.preferred_vehicle_types.split(',')
        if self.languages:
            data['languages_list'] = self.languages.split(',')
        
        # Include related data
        if include_assignments:
            data['recent_assignments'] = []
        
        if include_performance:
            data['performance_summary'] = {}
            data['lifetime_stats'] = {
                'total_trips': self.total_trips,
                'total_distance_km': self.total_distance,
                'average_rating': self.average_rating
            }
        
        # Include current vehicle info
        if self.current_vehicle:
            data['current_vehicle'] = {
                'id': self.current_vehicle.id,
                'registration_number': self.current_vehicle.registration_number,
                'vehicle_type': self.current_vehicle.vehicle_type
            }
        
        return data
    
    @classmethod
    def get_available_drivers(cls, vehicle_type=None):
        """
        Get available drivers
        """
        query = cls.query.filter_by(
            status='available', 
            is_active=True
        ).filter(
            cls.license_expiry_date > datetime.utcnow().date()
        )
        
        if vehicle_type:
            query = query.filter(
                cls.license_type.in_(['medium', 'heavy', 'all'])
                if vehicle_type in ['truck_medium', 'truck_heavy', 'trailer']
                else cls.license_type.in_(['light', 'medium', 'heavy', 'all'])
            )
        
        return query.order_by(cls.average_rating.desc()).all()
    
    @classmethod
    def get_drivers_by_license_expiry(cls, days_threshold=30):
        """
        Get drivers with licenses expiring soon
        """
        from datetime import timedelta
        expiry_date = datetime.utcnow().date() + timedelta(days=days_threshold)
        return cls.query.filter(
            cls.license_expiry_date <= expiry_date,
            cls.license_expiry_date >= datetime.utcnow().date(),
            cls.is_active == True
        ).order_by(cls.license_expiry_date).all()
    
    def __repr__(self):
        return f'<Driver {self.name} ({self.employee_id})>'


class DriverPerformance(BaseModel):
    """
    Driver performance tracking
    """
    __tablename__ = 'driver_performance'
    
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), nullable=False)
    evaluation_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    evaluator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    evaluator = db.relationship('User', 
                            foreign_keys=[evaluator_id], 
                            backref='driver_evaluations', 
                            primaryjoin='DriverPerformance.evaluator_id == User.id',
                            lazy=True)
    
    # Performance Metrics (1-5 scale)
    driving_skill = db.Column(db.Integer, nullable=False)
    safety_compliance = db.Column(db.Integer, nullable=False)
    customer_service = db.Column(db.Integer, nullable=False)
    punctuality = db.Column(db.Integer, nullable=False)
    vehicle_maintenance = db.Column(db.Integer, nullable=False)
    
    # Quantitative Metrics
    trips_completed = db.Column(db.Integer, default=0)
    distance_covered = db.Column(db.Float, default=0.0)
    on_time_deliveries = db.Column(db.Integer, default=0)
    
    # Overall
    overall_rating = db.Column(db.Float, nullable=False)
    comments = db.Column(db.Text, nullable=True)
    recommendations = db.Column(db.Text, nullable=True)

    driver = db.relationship('Driver', backref='performance_records', lazy=True)
    
    def __init__(self, **kwargs):
        # Don't call super().__init__(**kwargs) - BaseModel handles it
        # Just calculate rating if provided
        if 'overall_rating' not in kwargs and any(k in kwargs for k in ['driving_skill', 'safety_compliance', 'customer_service', 'punctuality', 'vehicle_maintenance']):
            self.calculate_overall_rating()
    
    def calculate_overall_rating(self):
        """Calculate overall rating from metrics"""
        metrics = [
            self.driving_skill,
            self.safety_compliance, 
            self.customer_service,
            self.punctuality,
            self.vehicle_maintenance
        ]
        self.overall_rating = sum(metrics) / len(metrics)
        return self.overall_rating
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()  # Get base fields from BaseModel
        
        # Add additional fields
        additional_data = {
            'driving_skill': self.driving_skill,
            'safety_compliance': self.safety_compliance,
            'customer_service': self.customer_service,
            'punctuality': self.punctuality,
            'vehicle_maintenance': self.vehicle_maintenance,
            'trips_completed': self.trips_completed,
            'distance_covered': self.distance_covered,
            'on_time_deliveries': self.on_time_deliveries,
            'overall_rating': self.overall_rating,
            'comments': self.comments,
            'recommendations': self.recommendations
        }
        data.update(additional_data)
        return data
    
    def __repr__(self):
        return f'<DriverPerformance {self.id}>'
