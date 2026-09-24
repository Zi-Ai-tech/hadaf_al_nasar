import secrets
from datetime import datetime, timedelta
from flask import current_app
from app import db

class KeyManager:
    @staticmethod
    def generate_api_key():
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def should_rotate_key(last_rotation_date):
        return datetime.utcnow() - last_rotation_date > timedelta(days=90)
    
    @staticmethod
    def validate_key_format(key):
        # Basic validation for key format
        return len(key) >= 32 and isinstance(key, str)

# Usage in your models
def rotate_api_key(user):
    if KeyManager.should_rotate_key(user.last_key_rotation):
        user.api_key = KeyManager.generate_api_key()
        user.last_key_rotation = datetime.utcnow()
        db.session.commit()