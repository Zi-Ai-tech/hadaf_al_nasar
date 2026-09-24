from flask import request
import re

class SecurityHeadersMiddleware:
    @staticmethod
    def set_security_headers(response):
        """
        Set additional security headers
        """
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # Enable XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions policy
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Feature policy (deprecated but still supported)
        response.headers['Feature-Policy'] = "geolocation 'none'; microphone 'none'; camera 'none'"
        
        return response
    
    @staticmethod
    def check_request_security():
        """
        Perform security checks on incoming requests
        """
        # Check for suspicious user agents
        user_agent = request.headers.get('User-Agent', '')
        suspicious_agents = ['nmap', 'sqlmap', 'nikto', 'metasploit']
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            return False
        
        # Check for excessive content length
        if request.content_length and request.content_length > 10 * 1024 * 1024:  # 10MB
            return False
        
        return True