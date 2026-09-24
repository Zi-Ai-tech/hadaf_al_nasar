from enum import Enum

class UserType(Enum):
    ACCOUNTS = "accounts"
    TRANSPORT = "transport"
    ADMIN = "admin"

class ShipmentStatus(Enum):
    PENDING = "pending"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    AT_WAREHOUSE = "at_warehouse"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class SalaryStatus(Enum):
    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    PROCESSED = 'processed'  
    CANCELLED = 'cancelled'  # Optional, if needed

class ExpenseType(Enum):
    OPERATIONAL = 'operational'
    VEHICLE = 'vehicle'
    EMPLOYEE = 'employee'
    OFFICE = 'office'
    ADMINISTRATIVE = 'administrative'
    MAINTENANCE = 'maintenance'
    FUEL = 'fuel'
    REPAIR = 'repair'
    INSURANCE = 'insurance'
    UTILITIES = 'utilities'
    RENT = 'rent'
    SALARY = 'salary'
    TRAINING = 'training'
    PARTS = 'parts'
    TRIP = 'trip'
    OTHER = 'other'

class IncomeType(Enum):
    SHIPMENT = 'SHIPMENT'
    SERVICE = 'SERVICE'
    VEHICLE_RENTAL = 'VEHICLE_RENTAL'
    CONSULTATION = 'CONSULTATION'
    STORAGE = 'STORAGE'
    INVOICE_PAYMENT = 'INVOICE_PAYMENT'
    OTHER = 'OTHER'

# UAE-specific constants
DEFAULT_CURRENCY = 'AED'
VAT_PERCENTAGE = 5
DEFAULT_PAYMENT_TERMS = 'NET30'