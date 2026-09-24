from app import db
from app.models.core.base import BaseModel, SoftDeleteMixin
from datetime import datetime
from sqlalchemy.orm import relationship, validates
import re

class Vehicle(BaseModel, SoftDeleteMixin):
    """
    Vehicle model for logistics and transportation operations
    """
    __tablename__ = 'vehicle'
    
    # [ALL YOUR EXISTING FIELDS - KEEP THEM EXACTLY AS THEY WERE]
    registration_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    vin = db.Column(db.String(50), unique=True, nullable=True, index=True)
    make = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    color = db.Column(db.String(30), nullable=True)
    vehicle_type = db.Column(db.String(50), nullable=False)
    capacity_kg = db.Column(db.Float, nullable=True)
    capacity_volume = db.Column(db.Float, nullable=True)
    dimensions = db.Column(db.String(100), nullable=True)
    fuel_type = db.Column(db.String(20), default='diesel')
    fuel_tank_capacity = db.Column(db.Float, nullable=True)
    fuel_efficiency = db.Column(db.Float, nullable=True)
    registration_expiry = db.Column(db.Date, nullable=False)
    insurance_company = db.Column(db.String(100), nullable=True)
    insurance_policy_number = db.Column(db.String(100), nullable=True)
    insurance_expiry = db.Column(db.Date, nullable=False)
    insurance_coverage_type = db.Column(db.String(50), default='comprehensive')
    ownership_type = db.Column(db.String(20), default='company')
    purchase_date = db.Column(db.Date, nullable=True)
    purchase_price = db.Column(db.Float, nullable=True)
    current_value = db.Column(db.Float, nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=True)
    status = db.Column(db.String(20), default='available', nullable=False)
    current_location = db.Column(db.String(100), nullable=True)
    last_maintenance_date = db.Column(db.Date, nullable=True)
    next_maintenance_date = db.Column(db.Date, nullable=True)
    last_serviced_odometer = db.Column(db.Float, default=0.0, nullable=False)
    current_odometer = db.Column(db.Float, default=0.0, nullable=False)
    total_distance = db.Column(db.Float, default=0.0, nullable=False)
    average_fuel_consumption = db.Column(db.Float, default=0.0, nullable=False)
    has_gps = db.Column(db.Boolean, default=True, nullable=False)
    has_refrigeration = db.Column(db.Boolean, default=False, nullable=False)
    has_trailer_hitch = db.Column(db.Boolean, default=False, nullable=False)
    has_safety_features = db.Column(db.Boolean, default=True, nullable=False)
    special_equipment = db.Column(db.Text, nullable=True)
    registration_copy_url = db.Column(db.String(500), nullable=True)
    insurance_copy_url = db.Column(db.String(500), nullable=True)
    vehicle_photos_url = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # FIXED RELATIONSHIPS - Unique names to avoid conflicts
    # supplier = relationship('Supplier', backref='supplied_vehicles')
    current_driver = relationship("Driver", back_populates="current_vehicle")
    # assignments_rel = relationship("DriverAssignment", backref="assignment_vehicle")  # Temporarily commented
    # shipments_rel = relationship("Shipment", backref="assigned_vehicle")  # Temporarily commented
    maintenance_records = relationship("VehicleMaintenance", back_populates="vehicle", lazy="dynamic")
    fuel_records = relationship("FuelRecord", back_populates="vehicle", lazy="dynamic")

    # [KEEP ALL YOUR EXISTING METHODS AND PROPERTIES EXACTLY AS THEY WERE]
    def __init__(self, **kwargs):
        if 'next_maintenance_date' not in kwargs and 'purchase_date' in kwargs:
            purchase_date = kwargs.get('purchase_date')
            if purchase_date:
                from datetime import timedelta
                kwargs['next_maintenance_date'] = purchase_date + timedelta(days=180)
        super().__init__(**kwargs)
    
    @validates('registration_number')
    def validate_registration_number(self, key, registration_number):
        if not registration_number:
            raise ValueError("Registration number cannot be empty")
        existing = Vehicle.query.filter_by(registration_number=registration_number).first()
        if existing and existing.id != getattr(self, 'id', None):
            raise ValueError("Registration number must be unique")
        return registration_number.upper()
    
    @validates('vin')
    def validate_vin(self, key, vin):
        if vin and len(vin) not in [17, 0]:
            raise ValueError("VIN must be 17 characters long")
        return vin.upper() if vin else vin
    
    @validates('year')
    def validate_year(self, key, year):
        current_year = datetime.now().year
        if year < 1900 or year > current_year + 1:
            raise ValueError(f"Vehicle year must be between 1900 and {current_year + 1}")
        return year
    
    @property
    def full_name(self):
        return f"{self.year} {self.make} {self.model} ({self.registration_number})"
    
    @property
    def is_available(self):
        return self.status == 'available' and self.is_active
    
    @property
    def is_in_use(self):
        return self.status == 'in_use'
    
    @property
    def is_in_maintenance(self):
        return self.status == 'maintenance'
    
    @property
    def registration_is_valid(self):
        if not self.registration_expiry:
            return False
        return self.registration_expiry > datetime.utcnow().date()
    
    @property
    def insurance_is_valid(self):
        if not self.insurance_expiry:
            return False
        return self.insurance_expiry > datetime.utcnow().date()
    
    @property
    def requires_maintenance(self):
        if self.next_maintenance_date:
            return self.next_maintenance_date <= datetime.utcnow().date()
        return False
    
    @property
    def maintenance_due_in_days(self):
        if self.next_maintenance_date:
            delta = self.next_maintenance_date - datetime.utcnow().date()
            return delta.days
        return None
    
    @property
    def age_years(self):
        if self.purchase_date:
            today = datetime.utcnow().date()
            return today.year - self.purchase_date.year - (
                (today.month, today.day) < (self.purchase_date.month, self.purchase_date.day)
            )
        return None
    
    @property
    def depreciation_value(self):
        if self.purchase_price and self.purchase_date:
            age_years = self.age_years or 0
            annual_depreciation = self.purchase_price / 10
            depreciated_value = max(0, self.purchase_price - (annual_depreciation * age_years))
            return depreciated_value
        return self.current_value

    # [KEEP ALL YOUR OTHER METHODS...]
    
    def to_dict(self, include_maintenance=False, include_fuel=False, include_financial=False):
        data = super().to_dict()
        
        # Add computed properties
        data['full_name'] = self.full_name
        data['is_available'] = self.is_available
        data['is_in_use'] = self.is_in_use
        data['is_in_maintenance'] = self.is_in_maintenance
        data['registration_is_valid'] = self.registration_is_valid
        data['insurance_is_valid'] = self.insurance_is_valid
        data['requires_maintenance'] = self.requires_maintenance
        data['maintenance_due_in_days'] = self.maintenance_due_in_days
        data['age_years'] = self.age_years
        data['depreciation_value'] = self.depreciation_value
        
        # Format dates
        date_fields = [
            'registration_expiry', 'insurance_expiry', 'purchase_date',
            'last_maintenance_date', 'next_maintenance_date'
        ]
        
        for field in date_fields:
            value = getattr(self, field)
            if value:
                data[field] = value.isoformat()
        
        # Include related data
        if self.current_driver:
            data['current_driver'] = {
                'id': self.current_driver.id,
                'name': self.current_driver.name,
                'phone': self.current_driver.phone
            }

        
        if self.supplier:
            data['supplier_name'] = self.supplier.name
        
        if include_maintenance:
            data['maintenance_records'] = [
                record.to_dict() for record in self.maintenance_records_rel[:10]
            ]
        
        if include_fuel:
            data['fuel_records'] = [
                record.to_dict() for record in self.fuel_records_rel[:10]
            ]
        
        return data
    
    @classmethod
    def get_available_vehicles(cls, vehicle_type=None):
        query = cls.query.filter_by(
            status='available', 
            is_active=True
        ).filter(
            cls.registration_expiry > datetime.utcnow().date(),
            cls.insurance_expiry > datetime.utcnow().date()
        )
        
        if vehicle_type:
            query = query.filter_by(vehicle_type=vehicle_type)
        
        return query.order_by(cls.make, cls.model).all()
    
    def __repr__(self):
        return f'<Vehicle {self.registration_number} - {self.make} {self.model}>'


class VehicleMaintenance(BaseModel):
    """
    Vehicle maintenance records
    """
    __tablename__ = 'vehicle_maintenance'
    
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    maintenance_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    cost = db.Column(db.Float, default=0.0, nullable=False)
    odometer_reading = db.Column(db.Float, nullable=False)
    service_date = db.Column(db.Date, nullable=False)
    next_maintenance_date = db.Column(db.Date, nullable=True)
    service_provider = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='completed')
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # FIXED: Use backref
    vehicle = relationship("Vehicle", back_populates="maintenance_records")
    
    @property
    def is_scheduled(self):
        return self.status == 'scheduled'
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    def to_dict(self):
        return {
            'id': self.id,
            'vehicle_id': self.vehicle_id,
            'maintenance_type': self.maintenance_type,
            'description': self.description,
            'cost': self.cost,
            'odometer_reading': self.odometer_reading,
            'service_date': self.service_date.isoformat(),
            'next_maintenance_date': self.next_maintenance_date.isoformat() if self.next_maintenance_date else None,
            'service_provider': self.service_provider,
            'status': self.status,
            'is_scheduled': self.is_scheduled,
            'is_completed': self.is_completed,
            'notes': self.notes,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<VehicleMaintenance {self.maintenance_type} for {self.vehicle.registration_number}>'


class FuelRecord(BaseModel):
    """
    Vehicle fuel consumption records
    """
    __tablename__ = 'fuel_record'
    
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    liters = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    odometer_reading = db.Column(db.Float, nullable=False)
    fuel_station = db.Column(db.String(100), nullable=True)
    fuel_efficiency = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # FIXED: Use backref
    vehicle = relationship("Vehicle", back_populates="fuel_records")
    
    @property
    def price_per_liter(self):
        return self.amount / self.liters if self.liters > 0 else 0
    
    def to_dict(self):
        return {
            'id': self.id,
            'vehicle_id': self.vehicle_id,
            'liters': self.liters,
            'amount': self.amount,
            'price_per_liter': self.price_per_liter,
            'odometer_reading': self.odometer_reading,
            'fuel_station': self.fuel_station,
            'fuel_efficiency': self.fuel_efficiency,
            'notes': self.notes,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<FuelRecord {self.liters}L for {self.vehicle.registration_number}>'