from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import text
import traceback
from werkzeug.security import check_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login_route():
    """Login route using direct SQL to avoid model initialization issues"""
    if request.method != 'POST':
        return render_template('auth/login.html')
    
    try:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user_type_str = request.form.get('user_type', '').strip().lower()
        
        print(f"Login attempt: {username}")
        
        if not all([username, password, user_type_str]):
            flash('Please fill in all fields.', 'danger')
            return render_template('auth/login.html')
        
        # Get db from current_app - CORRECTED
        from flask import current_app
        db = current_app.extensions['sqlalchemy']  # Changed: removed .db
        
        # Query user from database
        result = db.session.execute(
            text('SELECT id, username, password_hash, user_type, is_active, full_name FROM users WHERE username = :username'),
            {'username': username}
        ).fetchone()
        
        if not result:
            flash('Invalid username.', 'danger')
            return render_template('auth/login.html')
        
        user_id, db_username, password_hash, db_user_type, is_active, full_name = result
        
        # Check password
        if not check_password_hash(password_hash, password):
            flash('Invalid password.', 'danger')
            return render_template('auth/login.html')
        
        # Check user type
        if db_user_type.lower() != user_type_str:
            flash(f'Invalid login type. Your account is for {db_user_type} section.', 'danger')
            return render_template('auth/login.html')
        
        # Check if active
        if not is_active:
            flash('Your account is inactive. Please contact an administrator.', 'danger')
            return render_template('auth/login.html')
        
        # Create a simple user object for Flask-Login
        class SimpleUser:
            def __init__(self, user_id, username, user_type, full_name):
                self.id = user_id
                self.username = username
                self.user_type = user_type
                self.full_name = full_name
                self.is_active = True
                self.is_authenticated = True
                self.is_anonymous = False
            
            def get_id(self):
                return str(self.id)
        
        user = SimpleUser(user_id, db_username, db_user_type, full_name)
        login_user(user)
        
        # Set session variables
        session['user_id'] = user_id
        session['username'] = db_username
        session['user_type'] = db_user_type
        session['full_name'] = full_name
        
        flash(f'Welcome back, {full_name}!', 'success')
        return redirect(url_for('dashboard.dashboard'))
        
    except Exception as e:
        print(f"Login error: {e}")
        traceback.print_exc()
        flash('An error occurred during login. Please try again.', 'danger')
        return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login_route'))