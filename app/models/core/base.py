"""
Base model that uses the main SQLAlchemy instance from app
"""
from app import db
from datetime import datetime
from sqlalchemy import inspect
import json

class BaseModel(db.Model):
    """
    Base model with common fields and methods for all models
    """
    __abstract__ = True
    
    # Common fields for all models
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def save(self):
        """Save the current instance to database"""
        try:
            db.session.add(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False
    
    def delete(self):
        """Delete the current instance from database"""
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False
    
    def to_dict(self, include_relationships=False):
        """
        Convert model instance to dictionary
        """
        result = {}
        
        # Get all column values
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            
            # Handle datetime serialization
            if isinstance(value, datetime):
                value = value.isoformat()
            
            result[column.name] = value
        
        return result
    
    def update(self, **kwargs):
        """
        Update model attributes from keyword arguments
        """
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            
            self.updated_at = datetime.utcnow()
            return self.save()
        except Exception as e:
            return False
    
    @classmethod
    def get_by_id(cls, id):
        """Get instance by primary key ID"""
        return cls.query.get(id)
    
    @classmethod
    def get_all(cls):
        """Get all instances"""
        return cls.query.all()
    
    @classmethod
    def create(cls, **kwargs):
        """Create a new instance"""
        instance = cls(**kwargs)
        if instance.save():
            return instance
        return None
    
    def __repr__(self):
        """String representation of the model"""
        return f"<{self.__class__.__name__}(id={self.id})>"


class TimestampMixin:
    """
    Mixin for adding timestamp fields
    """
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SoftDeleteMixin:
    """
    Mixin for adding soft delete functionality
    """
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    def soft_delete(self):
        """Soft delete the record"""
        self.is_active = False
        self.deleted_at = datetime.utcnow()
        return self.save()
    
    def restore(self):
        """Restore a soft-deleted record"""
        self.is_active = True
        self.deleted_at = None
        return self.save()


class AuditMixin:
    """
    Mixin for adding audit fields
    """
    created_by = db.Column(db.Integer, nullable=True)
    updated_by = db.Column(db.Integer, nullable=True)