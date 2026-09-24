"""
Logistics models registry
CRITICAL: IMPORT ORDER MATTERS
"""

# ==================================
# Core models FIRST (NO DEPENDENCIES)
# ==================================
from app.models.logistics.driver import Driver

# ==================================
# Vehicle depends on Driver
# ==================================
from app.models.logistics.vehicle import (
    Vehicle,
    VehicleMaintenance,
    FuelRecord
)

# ==================================
# Shipment lookups (NO relationships)
# ==================================
from app.models.logistics.shipment import ShipmentStatus
from app.models.logistics.shipment import ShipmentType

# ==================================
# Shipment core
# ==================================
from app.models.logistics.shipment import Shipment

# ==================================
# Shipment children
# ==================================
from app.models.logistics.shipment import ShipmentItem
from app.models.logistics.shipment import ShipmentRoute
from app.models.logistics.shipment import ShipmentEvent
from app.models.logistics.shipment import ShipmentDocument
from app.models.logistics.shipment import ShipmentStatusHistory

__all__ = [
    "Driver",
    "Vehicle",
    "VehicleMaintenance",
    "FuelRecord",
    "ShipmentStatus",
    "ShipmentType",
    "Shipment",
    "ShipmentItem",
    "ShipmentRoute",
    "ShipmentEvent",
    "ShipmentDocument",
    "ShipmentStatusHistory",
]
