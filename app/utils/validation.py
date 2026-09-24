"""
Comprehensive Validation Utilities for the Hadaf Al Nasar Application
Handles validation for customers, incomes, invoices, and other entities
"""
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Union, List, Optional, Tuple, Dict, Any
import json


class ValidationError(Exception):
    """Custom validation error with field-specific messages"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)
    
    def to_dict(self):
        """Convert error to dictionary for API responses"""
        return {
            'error': self.message,
            'field': self.field
        }


# ==================== CUSTOMER VALIDATION ====================

def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return True  # Optional field
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    if not phone:
        return True  # Optional field
    # Allow numbers, spaces, hyphens, plus, parentheses
    cleaned_phone = re.sub(r'[\s\-\+\(\)]', '', phone)
    return cleaned_phone.isdigit() and 10 <= len(cleaned_phone) <= 15


def validate_trn(trn: str) -> bool:
    """Validate TRN format (UAE Tax Registration Number)"""
    if not trn:
        return False  # TRN is required in your customer model
    # UAE TRN is 15 digits
    return trn.isdigit() and len(trn) == 15


def validate_credit_limit(credit_limit: Union[str, float, int]) -> bool:
    """Validate credit limit"""
    try:
        limit = float(credit_limit)
        return limit >= 0
    except (TypeError, ValueError):
        return False


def validate_required_fields(data: Dict, required_fields: Dict[str, str]) -> List[str]:
    """Validate required fields"""
    errors = []
    for field, name in required_fields.items():
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f'{name} is required')
    return errors


def validate_customer_data(data: Dict, is_update: bool = False) -> Tuple[bool, List[str]]:
    """
    Comprehensive customer data validation
    Returns: (is_valid, errors)
    """
    errors = []
    
    # Required fields
    required_fields = {
        'company_name': 'Company Name',
        'trn': 'TRN', 
        'trade_license_number': 'Trade License Number'
    }
    
    errors.extend(validate_required_fields(data, required_fields))
    
    # TRN validation
    trn = data.get('trn', '').strip()
    if trn and not validate_trn(trn):
        errors.append('TRN must be exactly 15 digits')
    
    # Email validation
    email = data.get('email', '').strip()
    if email and not validate_email(email):
        errors.append('Invalid email format')
    
    # Phone validation
    phone = data.get('phone', '').strip()
    mobile = data.get('mobile', '').strip()
    
    if phone and not validate_phone(phone):
        errors.append('Invalid phone number format')
    if mobile and not validate_phone(mobile):
        errors.append('Invalid mobile number format')
    
    # Credit limit validation
    credit_limit = data.get('credit_limit')
    if credit_limit and not validate_credit_limit(credit_limit):
        errors.append('Credit limit must be a non-negative number')
    
    return len(errors) == 0, errors


# ==================== INCOME VALIDATION ====================

def validate_amount(amount: Union[str, int, float, Decimal]) -> Tuple[bool, str]:
    """
    Validate amount for incomes and invoices
    
    Args:
        amount: Amount value to validate
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    try:
        # Convert to float
        if isinstance(amount, str):
            amount = amount.replace(',', '').strip()
        
        amount_float = float(amount)
        
        # Check if it's a number
        if not isinstance(amount_float, (int, float)):
            return False, "Amount must be a valid number"
        
        # Check if positive
        if amount_float <= 0:
            return False, "Amount must be greater than 0"
        
        # Check if within reasonable range
        if amount_float > 1000000000:  # 1 billion
            return False, "Amount exceeds maximum allowed limit"
        
        return True, ""
        
    except (ValueError, TypeError):
        return False, "Invalid amount format"


def validate_income_amount(amount: Union[str, int, float]) -> bool:
    """Validate income amount (positive)"""
    return validate_amount(amount)[0]


def validate_date_string(date_str: str, date_format: str = '%Y-%m-%d') -> bool:
    """
    Validate date string format
    
    Args:
        date_str: Date string to validate
        date_format: Expected date format
        
    Returns:
        bool: True if valid
    """
    if not date_str:
        return False
    
    try:
        datetime.strptime(date_str, date_format)
        return True
    except ValueError:
        return False


def validate_income_date(income_date: str, allow_future: bool = False) -> bool:
    """
    Validate income date
    
    Args:
        income_date: Income date string
        allow_future: Whether to allow future dates
        
    Returns:
        bool: True if valid
    """
    if not validate_date_string(income_date):
        return False
    
    try:
        date_obj = datetime.strptime(income_date, '%Y-%m-%d').date()
        
        # Check if it's in the future
        if not allow_future and date_obj > date.today():
            return False
            
        return True
    except ValueError:
        return False


def validate_due_date(due_date: str, income_date: str = None) -> bool:
    """
    Validate due date
    
    Args:
        due_date: Due date string
        income_date: Income date for comparison
        
    Returns:
        bool: True if valid
    """
    if not due_date:
        return True  # Optional field
    
    if not validate_date_string(due_date):
        return False
    
    try:
        due_date_obj = datetime.strptime(due_date, '%Y-%m-%d').date()
        
        # If income date provided, check that due date is after income date
        if income_date and validate_date_string(income_date):
            income_date_obj = datetime.strptime(income_date, '%Y-%m-%d').date()
            if due_date_obj < income_date_obj:
                return False
                
        return True
    except ValueError:
        return False


def validate_currency(currency: str) -> bool:
    """
    Validate currency code
    
    Args:
        currency: 3-letter currency code
        
    Returns:
        bool: True if valid
    """
    if not currency:
        return False
    
    currency = currency.upper().strip()
    
    # Check length and format
    if len(currency) != 3:
        return False
    
    if not currency.isalpha():
        return False
    
    # List of accepted currencies in UAE/ME region
    accepted_currencies = ['AED', 'USD', 'EUR', 'GBP', 'SAR', 'QAR', 'OMR', 'KWD', 'BHD']
    
    return currency in accepted_currencies


def validate_income_type(income_type: str) -> bool:
    """
    Validate income type
    
    Args:
        income_type: Income type string
        
    Returns:
        bool: True if valid
    """
    if not income_type:
        return False
    
    valid_types = [
        'SHIPMENT', 'SERVICE', 'VEHICLE_RENTAL', 'CONSULTATION',
        'STORAGE', 'INVOICE_PAYMENT', 'OTHER'
    ]
    
    return income_type.lower() in valid_types


def validate_status(status: str) -> bool:
    """
    Validate income/invoice status
    
    Args:
        status: Status string
        
    Returns:
        bool: True if valid
    """
    if not status:
        return False
    
    valid_statuses = ['draft', 'pending', 'received', 'paid', 'overdue', 'cancelled', 'partial']
    
    return status.lower() in valid_statuses


def validate_payment_method(method: str) -> bool:
    """
    Validate payment method
    
    Args:
        method: Payment method string
        
    Returns:
        bool: True if valid
    """
    if not method:
        return True  # Optional field
    
    valid_methods = [
        'cash', 'bank_transfer', 'card', 'cheque', 'credit',
        'online', 'wallet', 'invoice', 'other'
    ]
    
    return method.lower() in valid_methods


def validate_tax_amount(tax_amount: Union[str, float], amount: Union[str, float]) -> Tuple[bool, str]:
    """
    Validate tax amount
    
    Args:
        tax_amount: Tax amount
        amount: Base amount for comparison
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    try:
        # Convert to floats
        tax = float(tax_amount) if tax_amount else 0
        amt = float(amount) if amount else 0
        
        # Tax cannot be negative
        if tax < 0:
            return False, "Tax amount cannot be negative"
        
        # Tax cannot exceed amount (for VAT rates up to 100%)
        if tax > amt:
            return False, "Tax amount cannot exceed base amount"
        
        # Calculate VAT rate (assuming UAE 5% VAT)
        if amt > 0:
            vat_rate = (tax / amt) * 100
            if vat_rate > 100:  # Sanity check
                return False, "Tax rate appears too high"
        
        return True, ""
        
    except (ValueError, TypeError):
        return False, "Invalid tax amount format"


def validate_total_amount(total: Union[str, float], amount: Union[str, float], tax: Union[str, float]) -> bool:
    """
    Validate that total = amount + tax
    
    Args:
        total: Total amount
        amount: Base amount
        tax: Tax amount
        
    Returns:
        bool: True if valid
    """
    try:
        total_float = float(total) if total else 0
        amount_float = float(amount) if amount else 0
        tax_float = float(tax) if tax else 0
        
        # Allow small rounding differences
        return abs(total_float - (amount_float + tax_float)) < 0.01
        
    except (ValueError, TypeError):
        return False


def validate_exchange_rate(rate: Union[str, float]) -> bool:
    """
    Validate exchange rate
    
    Args:
        rate: Exchange rate
        
    Returns:
        bool: True if valid
    """
    try:
        rate_float = float(rate) if rate else 1.0
        
        if rate_float <= 0:
            return False
        
        # Reasonable bounds for exchange rates
        if rate_float < 0.0001 or rate_float > 1000:
            return False
            
        return True
        
    except (ValueError, TypeError):
        return False


def validate_percentage(value: Union[str, float], max_percentage: float = 100.0) -> bool:
    """
    Validate percentage value
    
    Args:
        value: Percentage value
        max_percentage: Maximum allowed percentage
        
    Returns:
        bool: True if valid
    """
    try:
        if isinstance(value, str):
            value = value.replace('%', '').strip()
        
        percentage = float(value)
        
        return 0 <= percentage <= max_percentage
        
    except (ValueError, TypeError):
        return False


def validate_alphanumeric(text: str, allow_spaces: bool = True) -> bool:
    """
    Validate alphanumeric text
    
    Args:
        text: Text to validate
        allow_spaces: Whether to allow spaces
        
    Returns:
        bool: True if valid
    """
    if not text:
        return False
    
    pattern = r'^[a-zA-Z0-9_\-' + (r'\s' if allow_spaces else '') + r']+$'
    return bool(re.match(pattern, text))


def validate_numeric_string(text: str) -> bool:
    """
    Validate numeric string
    
    Args:
        text: String to validate
        
    Returns:
        bool: True if contains only digits
    """
    if not text:
        return False
    
    return text.isdigit()


def validate_json_string(json_str: str) -> bool:
    """
    Validate JSON string
    
    Args:
        json_str: JSON string to validate
        
    Returns:
        bool: True if valid JSON
    """
    if not json_str:
        return False
    
    try:
        json.loads(json_str)
        return True
    except json.JSONDecodeError:
        return False


def validate_url(url: str) -> bool:
    """
    Validate URL format
    
    Args:
        url: URL to validate
        
    Returns:
        bool: True if valid URL format
    """
    if not url:
        return True  # Optional field
    
    pattern = r'^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$'
    return bool(re.match(pattern, url, re.IGNORECASE))


# ==================== COMPREHENSIVE VALIDATORS ====================

def validate_income_data(data: Dict, is_update: bool = False) -> Tuple[bool, List[str]]:
    """
    Comprehensive income data validation
    
    Args:
        data: Income data dictionary
        is_update: Whether this is an update operation
        
    Returns:
        Tuple[bool, List[str]]: (is_valid, error_messages)
    """
    errors = []
    
    # Required fields for creation
    if not is_update:
        required_fields = {
            'description': 'Description',
            'amount': 'Amount',
            'income_type': 'Income Type',
            'income_date': 'Income Date'
        }
        
        for field, name in required_fields.items():
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f'{name} is required')
    
    # Validate amount
    amount = data.get('amount')
    if amount:
        is_valid, error_msg = validate_amount(amount)
        if not is_valid:
            errors.append(f'Amount: {error_msg}')
    
    # Validate tax amount
    tax_amount = data.get('tax_amount')
    if tax_amount and amount:
        is_valid, error_msg = validate_tax_amount(tax_amount, amount)
        if not is_valid:
            errors.append(f'Tax Amount: {error_msg}')
    
    # Validate total amount
    total_amount = data.get('total_amount')
    if total_amount and amount and tax_amount:
        if not validate_total_amount(total_amount, amount, tax_amount):
            errors.append('Total amount does not match amount + tax')
    
    # Validate dates
    income_date = data.get('income_date')
    if income_date and not validate_income_date(str(income_date)):
        errors.append('Invalid income date')
    
    due_date = data.get('due_date')
    if due_date and not validate_due_date(str(due_date), str(income_date) if income_date else None):
        errors.append('Invalid due date')
    
    # Validate currency
    currency = data.get('currency', 'AED')
    if not validate_currency(currency):
        errors.append('Invalid currency code')
    
    # Validate income type
    income_type = data.get('income_type')
    if income_type and not validate_income_type(income_type):
        errors.append('Invalid income type')
    
    # Validate status
    status = data.get('status')
    if status and not validate_status(status):
        errors.append('Invalid status')
    
    # Validate payment method
    payment_method = data.get('payment_method')
    if payment_method and not validate_payment_method(payment_method):
        errors.append('Invalid payment method')
    
    # Validate exchange rate
    exchange_rate = data.get('exchange_rate', 1.0)
    if exchange_rate and not validate_exchange_rate(exchange_rate):
        errors.append('Invalid exchange rate')
    
    # Validate tags
    tags = data.get('tags')
    if tags and len(tags) > 500:
        errors.append('Tags field too long (max 500 characters)')
    
    return len(errors) == 0, errors


def validate_invoice_data(data: Dict) -> Tuple[bool, List[str]]:
    """
    Validate invoice data
    
    Args:
        data: Invoice data dictionary
        
    Returns:
        Tuple[bool, List[str]]: (is_valid, error_messages)
    """
    errors = []
    
    # Required fields
    required_fields = {
        'customer_id': 'Customer',
        'invoice_type': 'Invoice Type',
        'amount': 'Amount'
    }
    
    for field, name in required_fields.items():
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f'{name} is required')
    
    # Validate amount
    amount = data.get('amount')
    if amount:
        is_valid, error_msg = validate_amount(amount)
        if not is_valid:
            errors.append(f'Amount: {error_msg}')
    
    # Validate invoice type
    invoice_type = data.get('invoice_type')
    if invoice_type and invoice_type not in ['vat', 'commercial', 'proforma']:
        errors.append('Invalid invoice type')
    
    # Validate dates
    issue_date = data.get('issue_date')
    if issue_date and not validate_date_string(str(issue_date)):
        errors.append('Invalid issue date')
    
    due_date = data.get('due_date')
    if due_date and not validate_date_string(str(due_date)):
        errors.append('Invalid due date')
    
    # Validate payment terms
    payment_terms = data.get('payment_terms')
    if payment_terms and payment_terms not in ['NET0', 'NET7', 'NET15', 'NET30', 'NET60', 'Due on receipt']:
        errors.append('Invalid payment terms')
    
    return len(errors) == 0, errors


# ==================== BATCH VALIDATION ====================

class Validator:
    """Class-based validator for complex validation scenarios"""
    
    @staticmethod
    def validate_financial_transaction(data: Dict) -> Dict[str, Any]:
        """
        Validate financial transaction data
        
        Args:
            data: Transaction data
            
        Returns:
            Dict with validation results
        """
        errors = []
        warnings = []
        
        # Extract fields
        amount = data.get('amount')
        currency = data.get('currency', 'AED')
        date_str = data.get('date')
        description = data.get('description', '')
        
        # Amount validation
        if not amount:
            errors.append('Amount is required')
        else:
            is_valid, error_msg = validate_amount(amount)
            if not is_valid:
                errors.append(f'Amount: {error_msg}')
            elif float(amount) > 100000:
                warnings.append('Large transaction amount')
        
        # Currency validation
        if not validate_currency(currency):
            errors.append('Invalid currency')
        
        # Date validation
        if not date_str:
            errors.append('Date is required')
        elif not validate_date_string(str(date_str)):
            errors.append('Invalid date format')
        
        # Description validation
        if not description or len(description.strip()) < 5:
            warnings.append('Description is short or missing')
        
        # Tax validation if present
        tax_amount = data.get('tax_amount')
        if tax_amount and amount:
            is_valid, error_msg = validate_tax_amount(tax_amount, amount)
            if not is_valid:
                errors.append(f'Tax: {error_msg}')
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'has_warnings': len(warnings) > 0
        }
    
    @staticmethod
    def validate_batch_incomes(incomes_data: List[Dict]) -> List[Dict[str, Any]]:
        """
        Validate batch of income records
        
        Args:
            incomes_data: List of income data dictionaries
            
        Returns:
            List of validation results for each income
        """
        results = []
        
        for idx, income_data in enumerate(incomes_data):
            is_valid, errors = validate_income_data(income_data)
            
            results.append({
                'index': idx,
                'is_valid': is_valid,
                'errors': errors,
                'income_number': income_data.get('income_number', f'Row {idx + 1}')
            })
        
        return results


# ==================== FORMATTING AND SANITIZATION ====================

def sanitize_string(text: str, max_length: int = None) -> str:
    """
    Sanitize string input
    
    Args:
        text: Input string
        max_length: Maximum length to trim to
        
    Returns:
        Sanitized string
    """
    if not text:
        return ''
    
    # Remove extra whitespace
    sanitized = ' '.join(text.strip().split())
    
    # Trim to max length if specified
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip()
    
    return sanitized


def format_phone_number(phone: str) -> str:
    """
    Format phone number to consistent format
    
    Args:
        phone: Phone number string
        
    Returns:
        Formatted phone number
    """
    if not phone:
        return ''
    
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Format UAE numbers
    if digits.startswith('971') and len(digits) == 12:
        return f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:]}"
    elif digits.startswith('0') and len(digits) == 10:
        return f"+971 {digits[1:4]} {digits[4:7]} {digits[7:]}"
    elif len(digits) == 9:
        return f"+971 {digits[:3]} {digits[3:6]} {digits[6:]}"
    
    # Return original if can't format
    return phone


def format_amount(amount: Union[str, float], currency: str = 'AED') -> str:
    """
    Format amount with currency
    
    Args:
        amount: Amount value
        currency: Currency code
        
    Returns:
        Formatted amount string
    """
    try:
        amount_float = float(amount)
        return f"{amount_float:,.2f} {currency}"
    except (ValueError, TypeError):
        return f"0.00 {currency}"


def parse_date(date_str: str, default=None) -> Optional[date]:
    """
    Parse date string to date object
    
    Args:
        date_str: Date string
        default: Default value if parsing fails
        
    Returns:
        Date object or default
    """
    if not date_str:
        return default
    
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        try:
            return datetime.strptime(date_str, '%d/%m/%Y').date()
        except ValueError:
            try:
                return datetime.strptime(date_str, '%m/%d/%Y').date()
            except ValueError:
                return default


# ==================== QUICK VALIDATION FUNCTIONS ====================

def is_valid_email(email: str) -> bool:
    """Quick email validation"""
    return validate_email(email)


def is_valid_phone(phone: str) -> bool:
    """Quick phone validation"""
    return validate_phone(phone)


def is_valid_amount(amount: Union[str, float]) -> bool:
    """Quick amount validation"""
    return validate_amount(amount)[0]


def is_valid_date(date_str: str) -> bool:
    """Quick date validation"""
    return validate_date_string(date_str)


def is_valid_currency(currency: str) -> bool:
    """Quick currency validation"""
    return validate_currency(currency)


# ==================== HELPER FUNCTIONS ====================

def get_validation_errors(data: Dict, validation_type: str = 'income') -> List[str]:
    """
    Get validation errors for data
    
    Args:
        data: Data to validate
        validation_type: Type of validation ('income', 'customer', 'invoice')
        
    Returns:
        List of error messages
    """
    if validation_type == 'income':
        _, errors = validate_income_data(data)
    elif validation_type == 'customer':
        _, errors = validate_customer_data(data)
    elif validation_type == 'invoice':
        _, errors = validate_invoice_data(data)
    else:
        errors = ['Unknown validation type']
    
    return errors


def validate_and_sanitize_income(data: Dict) -> Tuple[Dict, List[str]]:
    """
    Validate and sanitize income data in one step
    
    Args:
        data: Raw income data
        
    Returns:
        Tuple of (sanitized_data, error_messages)
    """
    errors = []
    sanitized = {}
    
    # Sanitize string fields
    string_fields = ['description', 'category', 'subcategory', 'payment_method',
                     'payment_reference', 'customer_name', 'customer_contact',
                     'customer_email', 'reference_number', 'revenue_category',
                     'gl_account', 'accounting_period']
    
    for field in string_fields:
        if field in data:
            sanitized[field] = sanitize_string(str(data[field]), 255)
    
    # Validate and sanitize amount fields
    amount_fields = ['amount', 'tax_amount', 'total_amount', 'exchange_rate']
    for field in amount_fields:
        if field in data and data[field]:
            try:
                sanitized[field] = float(Decimal(str(data[field])))
            except (ValueError, InvalidOperation):
                errors.append(f'Invalid {field.replace("_", " ")}')
    
    # Validate dates
    date_fields = ['income_date', 'due_date', 'payment_received_date', 'recurrence_end_date']
    for field in date_fields:
        if field in data and data[field]:
            date_str = str(data[field])
            if validate_date_string(date_str):
                sanitized[field] = parse_date(date_str)
            else:
                errors.append(f'Invalid {field.replace("_", " ")}')
    
    # Validate required fields
    required = ['description', 'amount', 'income_type', 'income_date']
    for field in required:
        if field not in data or not data[field]:
            errors.append(f'{field.replace("_", " ").title()} is required')
    
    # Copy other fields
    for key, value in data.items():
        if key not in sanitized and key not in amount_fields + date_fields + string_fields:
            sanitized[key] = value
    
    return sanitized, errors