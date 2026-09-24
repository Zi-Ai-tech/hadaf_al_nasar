import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Security - Use environment variables, never hardcode secrets
    SECRET_KEY = os.environ.get('SECRET_KEY', 'test-only-secret-key-change-before-production')
    
    # Database - Use environment variable, provide secure default
    _db_url = os.environ.get('DATABASE_URL')
    if _db_url and _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url or f"sqlite:///{os.path.join(basedir, 'hadaf_al_nasar.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security: Prevent connection leaks in production
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    
    # Dubai Government API Configuration
    DUBAI_GOV_API_BASE_URL = os.environ.get('DUBAI_GOV_API_BASE_URL', 'https://api.dubaigate.gov.ae')
    DUBAI_GOV_API_KEY = os.environ.get('DUBAI_GOV_API_KEY', 'test-placeholder-gov-key')    
    API_TIMEOUT = int(os.environ.get('API_TIMEOUT', 30))

    # SMTP Configuration for Email - Use environment variables only
    SMTP_SERVER = os.environ.get('SMTP_SERVER')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587)) if os.environ.get('SMTP_PORT') else 587
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'True').lower() == 'true'

    # Google Maps API
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')

    # Dubai DED API Configuration
    DUBAI_DED_API_BASE_URL = os.environ.get('DUBAI_DED_API_BASE_URL', 'https://api.ded.ae')
    DUBAI_DED_API_KEY = os.environ.get('DUBAI_DED_API_KEY', 'test-placeholder-ded-key')
    # WhatsApp Configuration - Twilio
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM')

    # WhatsApp Business API
    WHATSAPP_BUSINESS_ID = os.environ.get('WHATSAPP_BUSINESS_ID')
    WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN')
    
    # Session settings - Security enhancements
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    
    # Application settings
    MAX_CREDIT_LIMIT = float(os.environ.get('MAX_CREDIT_LIMIT', 1000000))
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 20))
    
    # Security Headers (will be applied via Flask-Talisman or similar)
    SECURITY_HEADERS = {
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
    }
    
    # Logging
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT') is not None
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO', 'False').lower() == 'true'
    # Development-specific settings
    EXPLAIN_TEMPLATE_LOADING = False
    WTF_CSRF_ENABLED = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    # Disable external API calls during tests
    DUBAI_GOV_API_BASE_URL = 'http://testserver/'
    DUBAI_DED_API_BASE_URL = 'http://testserver/'

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # Production security settings
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    
    # Validate that all required production settings are present
    def __init__(self):
        required_vars = ['SECRET_KEY', 'DUBAI_GOV_API_KEY', 'DUBAI_DED_API_KEY']
        for var in required_vars:
            if not getattr(self, var):
                raise ValueError(f"{var} is required in production environment")

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}