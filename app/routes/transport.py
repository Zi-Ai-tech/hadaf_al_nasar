from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.core.customer import Customer
from app.models.logistics.driver import Driver
from app.models.logistics.shipment import Shipment, ShipmentStatusHistory
from app.models.logistics.vehicle import Vehicle
import enum

# Define UserType enum here
class UserType(enum.Enum):
    ACCOUNTS = "accounts"
    TRANSPORT = "transport"
    ADMIN = "admin"

transport_bp = Blueprint('transport', __name__)

@transport_bp.route('/dashboard')
@login_required
def dashboard():
    total_shipments = Shipment.query.count()
    pending_shipments = Shipment.query.filter_by(status='pending').count()
    in_transit_shipments = Shipment.query.filter_by(status='in_transit').count()
    
    return render_template('transport/dashboard.html', 
                         total_shipments=total_shipments,
                         pending_shipments=pending_shipments,
                         in_transit_shipments=in_transit_shipments)

@transport_bp.route('/shipments')
@login_required
def shipments():
    shipments = Shipment.query.all()
    return render_template('transport/shipments.html', shipments=shipments)

@transport_bp.route('/create_shipment', methods=['GET', 'POST'])
@login_required
def create_shipment():
    if request.method == 'POST':
        # Extract form data
        # Generate tracking number
        # Create shipment
        # Log operation
        
        flash('Shipment created successfully.', 'success')
        return redirect(url_for('transport.shipments'))
    
    customers = Customer.query.all()
    drivers = Driver.query.filter_by(is_active=True).all()
    vehicles = Vehicle.query.filter_by(status='available').all()
    
    return render_template('transport/create_shipment.html', 
                         customers=customers, 
                         drivers=drivers, 
                         vehicles=vehicles)

@transport_bp.route('/update_shipment_status/<int:shipment_id>', methods=['GET', 'POST'])
@login_required
def update_shipment_status(shipment_id):
    shipment = Shipment.query.get_or_404(shipment_id)
    
    if request.method == 'POST':
        new_status = request.form.get('status')
        shipment.status = new_status
        status_history = ShipmentStatusHistory(
            shipment_id=shipment.id,
            status=new_status,
            changed_by=current_user.id,
        )
        db.session.add(status_history)
        db.session.commit()
        
        flash('Shipment status updated successfully.', 'success')
        return redirect(url_for('transport.shipments'))
    
    return render_template('transport/update_status.html', shipment=shipment)
