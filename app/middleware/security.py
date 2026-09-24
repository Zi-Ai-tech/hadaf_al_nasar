from flask import request, abort

class SecurityMiddleware:
    @staticmethod
    def check_sql_injection():
        # Basic SQL injection prevention
        sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'UNION']
        for key, value in request.values.items():
            if any(keyword in value.upper() for keyword in sql_keywords):
                abort(400, description="Invalid input detected")
    
    @staticmethod
    def check_xss():
        # Basic XSS prevention
        xss_patterns = ['<script>', 'javascript:', 'onerror=']
        for key, value in request.values.items():
            if any(pattern in value.lower() for pattern in xss_patterns):
                abort(400, description="Invalid input detected")

