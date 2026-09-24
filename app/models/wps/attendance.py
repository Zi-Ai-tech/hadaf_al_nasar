from app import db
from app.models.core.base import BaseModel
from sqlalchemy.orm import relationship

class Attendance(BaseModel):
    __tablename__ = 'attendance'

    employee_id = db.Column(
        db.Integer,
        db.ForeignKey('employee.id'),
        nullable=False
    )

    attendance_date = db.Column(db.Date, nullable=False)
    check_in = db.Column(db.DateTime)
    check_out = db.Column(db.DateTime)

    # ✅ points to Employee.attendance_records
    employee = relationship(
        'Employee',
        back_populates='attendance_records'
    )

    def __repr__(self):
        return f'<Attendance {self.id}>'
