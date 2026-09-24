"""Canonical SQLAlchemy model registry."""

from app.models.core.customer import Customer
from app.models.core.user import User
from app.models.finance.invoice import Invoice, InvoiceItem
from app.models.finance.payment import Payment, Refund
from app.models.finance.transaction import Supplier, Transaction
from app.models.logistics.driver import Driver, DriverPerformance
from app.models.logistics.shipment import DriverAssignment, Shipment, ShipmentDocument, ShipmentEvent, ShipmentItem, ShipmentRoute, ShipmentStatusHistory
from app.models.logistics.vehicle import FuelRecord, Vehicle, VehicleMaintenance
from app.models.wps.attendance import Attendance
from app.models.wps.employee import Employee
from app.models.wps.employee_leave import EmployeeLeave
from app.models.wps.expense import Expense
from app.models.wps.income import Income, Service
from app.models.wps.project import Project
from app.models.wps.salary import Salary, SalaryNotification

MODEL_REGISTRY = {
    model.__name__: model
    for model in (
        User, Customer, Invoice, InvoiceItem, Payment, Refund, Transaction, Supplier,
        Driver, DriverPerformance, Vehicle, VehicleMaintenance, FuelRecord, Shipment,
        DriverAssignment, ShipmentItem, ShipmentRoute, ShipmentEvent,
        ShipmentStatusHistory, ShipmentDocument, Employee, Attendance, EmployeeLeave,
        Expense, Income, Service, Project, Salary, SalaryNotification,
    )
}


def load_models():
    """Return the canonical mapped-model registry after importing all models."""
    return MODEL_REGISTRY


def get_model(model_name):
    """Return a canonical mapped class by name."""
    try:
        return MODEL_REGISTRY[model_name]
    except KeyError as exc:
        raise ValueError(f"Model {model_name} not found") from exc


load_all_models = load_models
