from app import db
from app.models.core.base import BaseModel
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class User(BaseModel, UserMixin):
    """
    Enhanced User model - NO RELATIONSHIPS DEFINED HERE
    All relationships are defined in the models with foreign keys
    """
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}  # MOVED INSIDE THE CLASS
    
    # Authentication and Basic Info
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    user_type = db.Column(db.String(20), nullable=False, default='staff')
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Additional fields for UAE context
    emirates_id = db.Column(db.String(50), nullable=True)
    department = db.Column(db.String(50), nullable=True)
    
    # NO RELATIONSHIPS DEFINED HERE - they are defined in the foreign key models
    
    def __init__(self, **kwargs):
        """
        Initialize user with password hashing
        """
        if 'password' in kwargs:
            password = kwargs.pop('password')
            kwargs['password_hash'] = generate_password_hash(password)
        super().__init__(**kwargs)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_admin(self):
        return self.user_type == 'admin'
    
    @property
    def is_driver(self):
        return self.user_type == 'driver'
    
    @property
    def is_staff(self):
        return self.user_type == 'staff'
    
    def to_dict(self, include_relationships=False):
        data = super().to_dict()
        data.pop('password_hash', None)
        data['is_admin'] = self.is_admin
        data['is_driver'] = self.is_driver
        data['is_staff'] = self.is_staff
        return data
    
    @classmethod
    def get_by_username(cls, username):
        return cls.query.filter_by(username=username).first()
    
    @classmethod
    def get_by_email(cls, email):
        return cls.query.filter_by(email=email).first()
    
    @classmethod
    def get_active_users(cls):
        return cls.query.filter_by(is_active=True).order_by(cls.full_name).all()
    
    @classmethod
    def get_users_by_type(cls, user_type):
        return cls.query.filter_by(user_type=user_type, is_active=True).order_by(cls.full_name).all()
    
    def __repr__(self):
        return f'<User {self.username} ({self.full_name})>'