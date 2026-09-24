class ApplicationError(Exception):
    """Base application exception"""
    pass

class ValidationError(ApplicationError):
    """Raised when validation fails"""
    pass

class DatabaseError(ApplicationError):
    """Raised when database operations fail"""
    pass

class GovernmentAPIError(ApplicationError):
    """Raised when government API calls fail"""
    pass

class BusinessRuleError(Exception):
    """Raised when business rules are violated"""
    def __init__(self, message, rule_name=None):
        super().__init__(message)
        self.rule_name = rule_name