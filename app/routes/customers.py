from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
import traceback

customers_bp = Blueprint('customers', __name__)

@customers_bp.route('/customers', methods=['GET'])
@login_required
def customers():
    try:
        filter_type = request.args.get('filter', 'active')
        
        # Use the CustomerService
        from app.services.customer_service import CustomerService
        customers_data, error = CustomerService.get_customers(filter_type)
        
        if error:
            print(f"Database error in customers route: {error}")
            return render_template('accounts/customers.html', 
                                 customers=[], 
                                 current_filter=filter_type,
                                 error=error)
        
        # CustomerService returns (customers, None) where customers is a list of dictionaries
        # We don't need to convert it, just pass it to template
        return render_template('accounts/customers.html', 
                             customers=customers_data or [], 
                             current_filter=filter_type)
            
    except Exception as e:
        print(f"[Customers Route Error] {e}")
        traceback.print_exc()
        return render_template('accounts/customers.html', 
                             customers=[], 
                             current_filter='active',
                             error=str(e))

@customers_bp.route('/customers', methods=['POST'])
@login_required
def create_customer():
    """Handle customer creation"""
    try:
        from app.services.customer_service import CustomerService
        success, message = CustomerService.create_customer(request.form)
        
        status_code = 200 if success else 400
        return jsonify({'success': success, 'message': message}), status_code
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error: {str(e)}'
        }), 500

@customers_bp.route('/customers/<int:id>', methods=['GET'])
@login_required
def get_customer(id):
    """Get customer by ID"""
    try:
        from app.services.customer_service import CustomerService
        customer, error = CustomerService.get_customer_by_id(id)
        
        if error:
            return jsonify({
                'success': False,
                'message': error
            }), 404
        
        if not customer:
            return jsonify({
                'success': False,
                'message': 'Customer not found'
            }), 404
        
        # CustomerService already returns a dictionary with proper formatting
        return jsonify({
            'success': True,
            'customer': customer
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@customers_bp.route('/customers/<int:id>/update', methods=['POST'])
@login_required
def update_customer(id):
    """Update customer"""
    try:
        from app.services.customer_service import CustomerService
        success, message = CustomerService.update_customer(id, request.form)
        
        status_code = 200 if success else 400
        return jsonify({'success': success, 'message': message}), status_code
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@customers_bp.route('/customers/<int:id>/deactivate', methods=['POST'])
@login_required
def deactivate_customer(id):
    """Deactivate customer"""
    try:
        from app.services.customer_service import CustomerService
        success, message = CustomerService.change_customer_status(id, False)
        
        status_code = 200 if success else 400
        return jsonify({'success': success, 'message': message}), status_code
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@customers_bp.route('/customers/<int:id>/activate', methods=['POST'])
@login_required
def activate_customer(id):
    """Activate customer"""
    try:
        from app.services.customer_service import CustomerService
        success, message = CustomerService.change_customer_status(id, True)
        
        status_code = 200 if success else 400
        return jsonify({'success': success, 'message': message}), status_code
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@customers_bp.route('/customers/<int:id>/delete', methods=['POST'])
@login_required
def delete_customer(id):
    """Delete customer"""
    try:
        from app.services.customer_service import CustomerService
        success, message = CustomerService.delete_customer(id)
        
        status_code = 200 if success else 400
        return jsonify({'success': success, 'message': message}), status_code
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500