from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user
from app.constants import UserType


def requires_accounts_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.user_type != UserType.ACCOUNTS:
            flash('You do not have permission to access this section.', 'danger')
            return redirect(url_for('auth.login_route'))
        return f(*args, **kwargs)
    return decorated_function

def requires_transport_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.user_type != UserType.TRANSPORT:
            flash('You do not have permission to access this section.', 'danger')
            return redirect(url_for('auth.login_route'))
        return f(*args, **kwargs)
    return decorated_function
