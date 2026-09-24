from app import db
from app.models.core.base import BaseModel
from datetime import datetime
from sqlalchemy.orm import relationship

class Project(BaseModel):
    __tablename__ = 'project'
    
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    budget = db.Column(db.Float, default=0.0, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    department = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    manager_name = db.relationship('User', foreign_keys=[manager_id], backref='projects', lazy=True)
    
    # ⚡ Add this line to fix Expense relationship
    expenses = relationship('Expense', back_populates='project', lazy='dynamic')

    @property
    def total_expenses(self):
        return sum(expense.total_amount_in_default_currency for expense in self.expenses)

    @property
    def remaining_budget(self):
        return self.budget - self.total_expenses

    @property
    def budget_utilization(self):
        if self.budget > 0:
            return (self.total_expenses / self.budget) * 100
        return 0

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'budget': self.budget,
            'total_expenses': self.total_expenses,
            'remaining_budget': self.remaining_budget,
            'budget_utilization': self.budget_utilization,
            'status': self.status,
            'manager_name': self.project_manager.full_name if self.project_manager else None,
            'department': self.department,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Project {self.code} - {self.name}>'
