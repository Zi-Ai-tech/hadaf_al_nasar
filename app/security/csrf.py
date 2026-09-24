from flask import current_app, request, session, jsonify
from functools import wraps
import secrets
import hmac
import hashlib

def generate_csrf_token():
    """Generate a CSRF token and store it in the session"""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

def validate_csrf_token(token):
    """Validate the CSRF token"""
    expected_token = session.get('_csrf_token')
    if not expected_token or not token:
        return False
    return hmac.compare_digest(expected_token, token)

def csrf_protect(f):
    """CSRF protection decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
            if not validate_csrf_token(token):
                return jsonify({'success': False, 'message': 'CSRF token validation failed'}), 403
        return f(*args, **kwargs)
    return decorated_function

def get_csrf_token():
    """Get current CSRF token"""
    return session.get('_csrf_token')