from flask import Flask, jsonify, request, send_from_directory, render_template, session, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
import logging
from logging.handlers import RotatingFileHandler
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import os
from datetime import datetime

# -----------------------------
# Import exceptions at the top level
# -----------------------------
try:
    from app.exceptions import ApplicationError, ValidationError, DatabaseError
except ImportError:
    # Create minimal exception classes if they don't exist
    class ApplicationError(Exception):
        pass
    
    class ValidationError(Exception):
        pass
    
    class DatabaseError(Exception):
        pass

# -----------------------------
# Create extensions instances
# -----------------------------
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

# -----------------------------
# Factory function
# -----------------------------
def create_app(config_name=None):
    app = Flask(__name__)
    
    # Select configuration from an explicit caller value or the environment.
    from config import config as config_mapping
    selected_config = config_name or os.environ.get(
        'FLASK_CONFIG', os.environ.get('FLASK_ENV', 'default')
    )
    if selected_config not in config_mapping:
        valid_configs = ', '.join(sorted(config_mapping))
        raise ValueError(
            f"Unknown configuration '{selected_config}'. "
            f"Expected one of: {valid_configs}."
        )
    app.config.from_object(config_mapping[selected_config])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Setup login manager
    login_manager.login_view = 'auth.login_route'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.models.core.user import User
            return db.session.get(User, int(user_id))
        except Exception as e:
            if 'app' in locals():
                current_app.logger.error(f"Error loading user {user_id}: {e}")
            return None

    # -----------------------------
    # Initialize models on first request and handle form persistence
    # -----------------------------
    models_initialized = False

    @app.before_request
    def before_request_handler():
        """Handle all before-request tasks including model initialization and form persistence"""
        nonlocal models_initialized
    
        # Part 1: Model initialization (run once)
        if not models_initialized:
            current_app.logger.info("Initializing models on first request...")
            if initialize_models():
                models_initialized = True
                current_app.logger.info("✓ Models initialized successfully on first request")
            else:
                current_app.logger.error("✗ Failed to initialize models")
    
        # Part 2: Form data persistence for income routes
        handle_form_data_persistence()

    def handle_form_data_persistence():
        """Handle form data persistence across redirects for income forms"""
        from flask import session
        import time
    
        # Skip static files and API endpoints
        if request.endpoint in ['static'] or request.path.startswith('/api/'):
            return
    
        # Only process for income-related endpoints
        if request.endpoint and 'income.' in request.endpoint:
            current_app.logger.debug(f"Form persistence - Endpoint: {request.endpoint}, Method: {request.method}")
        
            if request.method == 'GET':
                # Check if we should clear form data from previous POST
                if 'form_errors' in session or 'form_data' in session:
                    # Check timestamp for expiration (5 minutes)
                    if 'form_timestamp' in session:
                        if time.time() - session['form_timestamp'] > 300:  # 5 minutes
                            current_app.logger.debug("Clearing expired form data")
                            session.pop('form_errors', None)
                            session.pop('form_data', None)
                            session.pop('form_timestamp', None)
                    else:
                        # No timestamp, clear immediately
                        session.pop('form_errors', None)
                        session.pop('form_data', None)
        
            elif request.method == 'POST' and request.endpoint == 'income.create_income':
                # Store timestamp for newly submitted forms
                session['form_timestamp'] = time.time()

    # -----------------------------
    # Security headers middleware
    # -----------------------------
    from app.middleware.security_headers import SecurityHeadersMiddleware

    @app.after_request
    def after_request(response):
        return SecurityHeadersMiddleware.set_security_headers(response)

    # -----------------------------
    # Logging configuration
    # -----------------------------
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        log_file = os.path.join('logs', 'app.log')
        file_handler = RotatingFileHandler(log_file, maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Application startup')

    # -----------------------------
    # Initialize models AFTER db is set up
    # -----------------------------
    def initialize_models():
        """Initialize all models - ULTRA SIMPLE VERSION"""
        try:
            with current_app.app_context():
                current_app.logger.info("Starting model initialization...")
            
                # Just import the models - relationships will be configured automatically
                # We'll import in dependency order
            
                # 1. Base model first
                from app.models.registry import load_models
            
                # 2. Simple models without complex dependencies
                load_models()
            
                current_app.logger.info("✓ Basic models imported")
            
                # 3. Now import models with relationships
                # Import them but don't worry about circular imports - use string references
            
                current_app.logger.info("✓ Relationship models imported")
            
                # 4. SQLAlchemy will handle the rest
                current_app.logger.info("Configuring database mappers...")
                db.configure_mappers()
                current_app.logger.info("✓ Database mappers configured")
            
                current_app.logger.info("All models initialized successfully")
                return True
        except Exception as e:
            current_app.logger.error(f"Error initializing models: {str(e)}")
            import traceback
            current_app.logger.error(f"Full traceback: {traceback.format_exc()}")
            raise

    @app.template_filter('format_currency')
    def format_currency_filter(value, currency='AED'):
        """Format value as currency"""
        try:
            return f"{float(value):,.2f} {currency}"
        except (ValueError, TypeError):
            return value

    @app.template_filter('format_phone')
    def format_phone_filter(phone):
        """Format phone number for display"""
        if not phone:
            return ''
        # Remove all non-digit characters
        digits = ''.join(filter(str.isdigit, str(phone)))
        if len(digits) == 10:
            return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
        elif len(digits) == 9:
            return f"{digits[:2]} {digits[2:5]} {digits[5:]}"
        return phone

    # -----------------------------
    # Context processor for expense and income types
    # -----------------------------
    @app.context_processor
    def utility_processor():
        """Provide utility functions and data to all templates"""
        def get_expense_types():
            """Get expense types as dictionary for templates"""
            try:
                from app.constants import ExpenseType
                return {e.value: e.value.replace('_', ' ').title() for e in ExpenseType}
            except ImportError:
                # Fallback if constants not available
                return {
                    'operational': 'Operational',
                    'vehicle': 'Vehicle',
                    'employee': 'Employee',
                    'office': 'Office',
                    'administrative': 'Administrative',
                    'maintenance': 'Maintenance',
                    'fuel': 'Fuel',
                    'repair': 'Repair',
                    'insurance': 'Insurance',
                    'utilities': 'Utilities',
                    'rent': 'Rent',
                    'salary': 'Salary',
                    'training': 'Training'
                }
        
        def get_income_types():
            """Get income types as dictionary for templates"""
            try:
                from app.constants import IncomeType
                return {i.value: i.value.replace('_', ' ').title() for i in IncomeType}
            except ImportError:
                # Fallback if constants not available
                return {
                    'shipment': 'Shipment',
                    'service': 'Service',
                    'vehicle_rental': 'Vehicle Rental',
                    'consultation': 'Consultation',
                    'storage': 'Storage',
                    'other': 'Other'
                }
        
        def get_payment_methods():
            """Get payment methods for dropdowns"""
            return {
                'cash': 'Cash',
                'bank_transfer': 'Bank Transfer',
                'cheque': 'Cheque',
                'card': 'Card',
                'online': 'Online Payment'
            }
        
        def get_currencies():
            """Get available currencies"""
            return {
                'AED': 'AED (UAE Dirham)',
                'USD': 'USD (US Dollar)',
                'EUR': 'EUR (Euro)',
                'SAR': 'SAR (Saudi Riyal)',
                'INR': 'INR (Indian Rupee)'
            }
        
        def get_expense_categories():
            """Get expense categories"""
            return {
                'operational': 'Operational',
                'vehicle': 'Vehicle',
                'employee': 'Employee',
                'office': 'Office',
                'administrative': 'Administrative',
                'maintenance': 'Maintenance',
                'fuel': 'Fuel',
                'insurance': 'Insurance'
            }
        
        def get_income_categories():
            """Get income categories"""
            return {
                'shipment': 'Shipment',
                'service': 'Service',
                'vehicle_rental': 'Vehicle Rental',
                'storage': 'Storage',
                'other': 'Other'
            }
        
        def get_status_badge(status):
            """Return Bootstrap badge class based on status"""
            status_map = {
                'pending': 'warning',
                'approved': 'success',
                'paid': 'info',
                'rejected': 'danger',
                'received': 'success',
                'overdue': 'danger',
                'cancelled': 'secondary'
            }
            return status_map.get(status, 'secondary')
        
        def get_current_year():
            """Get current year for copyright notices"""
            from datetime import datetime
            return datetime.now().year
        
        return dict(
            # Enum types for dropdowns
            expense_types=get_expense_types(),
            income_types=get_income_types(),
            payment_methods=get_payment_methods(),
            currencies=get_currencies(),
            expense_categories=get_expense_categories(),
            income_categories=get_income_categories(),
            
            # Utility functions
            get_status_badge=get_status_badge,
            get_current_year=get_current_year,
            
            # Current date for forms
            current_date=datetime.utcnow().strftime('%Y-%m-%d'),
            current_year=get_current_year(),
            current_month=datetime.utcnow().strftime('%Y-%m')
        )

    # -----------------------------
    # Error handlers
    # -----------------------------
    @app.errorhandler(ApplicationError)
    def handle_application_error(error):
        current_app.logger.error(f'Application error: {str(error)}')
        return jsonify({'error': str(error)}), 400

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        current_app.logger.warning(f'Validation error: {str(error)}')
        return jsonify({'error': str(error)}), 400

    @app.errorhandler(DatabaseError)
    def handle_database_error(error):
        current_app.logger.error(f'Database error: {str(error)}')
        return jsonify({'error': 'Database operation failed'}), 500

    @app.errorhandler(404)
    def not_found_error(error):
        # Check if it's an API request
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'error': 'Resource not found'}), 404
        
        # For regular web requests, try to render template or fall back to JSON
        try:
            return render_template('errors/404.html'), 404
        except Exception:
            return jsonify({'error': 'Resource not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        current_app.logger.error(f'Server error: {str(error)}')
        
        # Check if it's an API request
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'error': 'Internal server error'}), 500
        
        # For regular web requests, try to render template or fall back to JSON
        try:
            return render_template('errors/500.html'), 500
        except Exception:
            return jsonify({'error': 'Internal server error'}), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        # Handle Government API errors specifically
        if "Government API" in str(error):
            return jsonify({
                'error': 'Government service temporarily unavailable',
                'message': str(error)
            }), 503
        
        # Log unexpected errors
        current_app.logger.error(f'Unexpected error: {str(error)}')
        
        # For API requests, return JSON
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({
                'error': 'An unexpected error occurred',
                'message': str(error) if app.debug else 'Please try again later'
            }), 500
        
        # For web requests, use the internal_error handler
        return internal_error(error)

    # -----------------------------
    # CSP Reporting
    # -----------------------------
    @app.route('/csp-report', methods=['POST'])
    def csp_report():
        if request.is_json:
            report = request.get_json()
            current_app.logger.warning(f'CSP Violation: {report}')
            return jsonify({'status': 'received'}), 200
        return jsonify({'error': 'Invalid report'}), 400

    @app.route('/.well-known/security.txt')
    def security_txt():
        return send_from_directory(app.static_folder, '.well-known/security.txt')

    # -----------------------------
    # Health check endpoint
    # -----------------------------
    @app.route('/health')
    def health_check():
        """Health check endpoint for load balancers and monitoring"""
        try:
            # Test database connection - FIXED: Use text() for SQL expression
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'timestamp': datetime.utcnow().isoformat()
            })
        except Exception as e:
            current_app.logger.error(f'Health check failed: {str(e)}')
            return jsonify({
                'status': 'unhealthy',
                'database': 'disconnected',
                'error': str(e)
            }), 503

    
    # Basic routes
    @app.route('/')
    def index():
        return "Hadaf Al Nasar Application is running! <a href='/login'>Go to Login</a>"
    
    @app.route('/ping')
    def ping():
        return "pong"
    
    if app.config.get('DEBUG') or app.config.get('TESTING'):
        @app.route('/debug/routes')
        def debug_routes():
            import json
            routes = []
            for rule in app.url_map.iter_rules():
                if rule.endpoint != 'static':
                    routes.append({
                        'rule': rule.rule,
                        'endpoint': rule.endpoint,
                        'methods': list(rule.methods)
                    })
            return json.dumps(routes, indent=2)

    # -----------------------------
    # Register blueprints - ONLY ONCE AT THE END
    # -----------------------------
    from app.routes import register_all_blueprints
    register_all_blueprints(app)

    return app
