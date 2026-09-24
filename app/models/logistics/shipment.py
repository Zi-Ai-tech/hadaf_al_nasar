from datetime import datetime
from sqlalchemy.orm import relationship
from app import db
from app.models.core.base import BaseModel

class Shipment(BaseModel):
    __tablename__ = 'shipment'

    tracking_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending')
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)

    # Relationship to Customer
    customer = relationship("Customer", back_populates="shipments")

    # Other shipment relationships
    driver_assignments = relationship("DriverAssignment", back_populates="shipment", cascade="all, delete-orphan")
    items = relationship("ShipmentItem", back_populates="shipment", cascade="all, delete-orphan")
    routes = relationship("ShipmentRoute", back_populates="shipment", cascade="all, delete-orphan")
    events = relationship("ShipmentEvent", back_populates="shipment", cascade="all, delete-orphan")
    status_history = relationship("ShipmentStatusHistory", back_populates="shipment", cascade="all, delete-orphan")
    documents = relationship("ShipmentDocument", back_populates="shipment", cascade="all, delete-orphan")

    def get_customer_name(self):
        from app.models.core.customer import Customer
        customer = Customer.query.get(self.customer_id)
        return customer.name if customer else None

    def __repr__(self):
        return f"<Shipment {self.tracking_number}>"

# -------------------
# All other shipment-related models
# -------------------

class DriverAssignment(BaseModel):
    __tablename__ = 'driver_assignment'
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'))
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipment.id'))
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    shipment = relationship("Shipment", back_populates="driver_assignments")

class ShipmentItem(BaseModel):
    __tablename__ = 'shipment_item'
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipment.id'))
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, default=1)

    shipment = relationship("Shipment", back_populates="items")

class ShipmentRoute(BaseModel):
    __tablename__ = 'shipment_route'
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipment.id'))
    from_location = db.Column(db.String(100), nullable=False)
    to_location = db.Column(db.String(100), nullable=False)

    shipment = relationship("Shipment", back_populates="routes")

class ShipmentEvent(BaseModel):
    __tablename__ = 'shipment_event'
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipment.id'))
    event_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_time = db.Column(db.DateTime, default=datetime.utcnow)

    shipment = relationship("Shipment", back_populates="events")

class ShipmentStatusHistory(BaseModel):
    __tablename__ = 'shipment_status_history'
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipment.id'))
    status = db.Column(db.String(50), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    shipment = relationship("Shipment", back_populates="status_history")

class ShipmentDocument(BaseModel):
    __tablename__ = 'shipment_document'
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipment.id'), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    shipment = relationship("Shipment", back_populates="documents")