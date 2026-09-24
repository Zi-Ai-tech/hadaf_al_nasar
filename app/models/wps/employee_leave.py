from app import db
from app.models.core.base import BaseModel
from sqlalchemy.orm import relationship, validates
class EmployeeLeave(BaseModel):
    __tablename__ = 'employee_leave'
    
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    leave_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')
    
    # FIXED: Use unique backref name
    employee = relationship('Employee', back_populates='leave_records')
    
    def __repr__(self):
        return f'<EmployeeLeave {self.id}>'