"""
Income Service for handling all income-related business logic
Centralizes income operations, validation, and coordination between models
"""
from app import db
from app.models.wps.income import Income, Service
from app.models.finance.invoice import Invoice, InvoiceItem
from app.models.core.customer import Customer
from app.models.core.user import User
from app.constants import IncomeType
from app.exceptions import ValidationError, DatabaseError, BusinessRuleError
from app.utils.sequence_generator import generate_next_sequence
from app.utils.validation import validate_amount, validate_currency, parse_date
# from app.utils.currency_converter import CurrencyConverter
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import json
import logging

logger = logging.getLogger(__name__)

class IncomeService:
    """
    Service class for handling income-related business logic
    """
    
    @staticmethod
    def generate_income_number() -> str:
        """
        Generate unique income number in format: INC-YYYY-MM-XXXX
        
        Returns:
            str: Generated income number
        """
        try:
            now = datetime.now()
            year_month = now.strftime('%Y-%m')
            
            # Get next sequence for this month
            sequence_key = f"income_{year_month}"
            sequence = generate_next_sequence(sequence_key)
            
            return f"INC-{year_month}-{sequence:04d}"
        except Exception as e:
            logger.error(f"Error generating income number: {e}")
            # Fallback: timestamp-based number
            timestamp = int(datetime.now().timestamp())
            return f"INC-EMG-{timestamp}"
    
    @staticmethod
    def create_income(income_data: Dict, recorded_by: int) -> Income:
        """
        Create a new income record with validation
        
        Args:
            income_data: Dictionary containing income data
            recorded_by: User ID of the person recording the income
            
        Returns:
            Income: Created income object
            
        Raises:
            ValidationError: If validation fails
            DatabaseError: If database operation fails
        """
        try:
            allow_manual_income = bool(income_data.pop('_allow_manual_income', False))

            # Strict business rule: all income in this workflow is created from completed payments.
            # Manual entry is forbidden by design.
            if not allow_manual_income and not income_data.get('payment_id') and not income_data.get('invoice_id'):
                raise BusinessRuleError(
                    "Manual income creation is disabled. Income is recorded automatically when an invoice payment is completed."
                )

            if income_data.get('invoice_id') and not income_data.get('payment_id'):
                raise BusinessRuleError(
                    "Invoice income must be created from a completed payment"
                )

            # Validate required fields
            required_fields = ['income_type', 'amount', 'description', 'income_date']
            for field in required_fields:
                if field not in income_data:
                    raise ValidationError(f"Missing required field: {field}")
            
            # Validate amount
            amount = validate_amount(income_data['amount'])
            if amount <= 0:
                raise ValidationError("Income amount must be positive")
            
            # Validate date
            income_date = parse_date(income_data['income_date'])
            if not income_date:
                raise ValidationError("Invalid income date format. Use YYYY-MM-DD")
            if income_date > date.today():
                raise ValidationError("Income date cannot be in the future")
            
            # Generate income number if not provided
            if 'income_number' not in income_data or not income_data['income_number']:
                income_data['income_number'] = IncomeService.generate_income_number()
            
            # Set default values
            income_data.setdefault('currency', 'AED')
            income_data.setdefault('exchange_rate', 1.0)
            income_data.setdefault('status', 'pending')
            income_data.setdefault('recorded_by', recorded_by)
            
            # Calculate totals if not provided
            tax_amount = income_data.get('tax_amount', 0.0)
            if 'total_amount' not in income_data:
                income_data['total_amount'] = amount + tax_amount
            
            # Validate customer if provided
            if 'customer_id' in income_data:
                customer = Customer.query.get(income_data['customer_id'])
                if not customer:
                    raise ValidationError(f"Customer with ID {income_data['customer_id']} not found")
            
            # Create income object
            income = Income(**income_data)
            
            # Save to database
            db.session.add(income)
            db.session.commit()
            
            logger.info(f"Income {income.income_number} created by user {recorded_by}")
            
            # Trigger any post-creation events
            IncomeService._trigger_post_creation_events(income)
            
            return income
            
        except (ValidationError, BusinessRuleError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating income: {e}")
            raise DatabaseError(f"Failed to create income: {str(e)}")
    
    @staticmethod
    def create_income_from_invoice(invoice_id: int, recorded_by: int) -> Income:
        """
        Create income record from invoice payment
        
        Args:
            invoice_id: ID of the invoice
            recorded_by: User ID recording the payment
            
        Returns:
            Income: Created income record
        """
        try:
            raise BusinessRuleError(
                "Direct invoice income is disabled; record a completed payment instead"
            )

            # Get invoice with related data
            invoice = Invoice.query.options(
                db.joinedload(Invoice.customer),
                db.joinedload(Invoice.items)
            ).get(invoice_id)
            
            if not invoice:
                raise ValidationError(f"Invoice with ID {invoice_id} not found")
            
            # Check if invoice is already paid
            if invoice.is_paid:
                raise BusinessRuleError("Invoice is already paid")
            
            # Check if income already exists for this invoice
            existing_income = Income.query.filter_by(
                invoice_id=invoice_id,
                status='received'
            ).first()
            
            if existing_income:
                raise BusinessRuleError("Income record already exists for this invoice")
            
            # Prepare income data
            income_data = {
                'income_type': 'invoice_payment',
                'amount': invoice.amount,
                'tax_amount': invoice.vat_amount,
                'total_amount': invoice.total_amount,
                'currency': 'AED',
                'exchange_rate': 1.0,
                'income_date': date.today(),
                'payment_received_date': date.today(),
                'description': f"Payment for Invoice {invoice.invoice_number}",
                'category': 'invoice_payment',
                'payment_method': 'invoice',
                'customer_id': invoice.customer_id,
                'invoice_id': invoice_id,
                'reference_number': invoice.invoice_number,
                'status': 'received',
                'is_taxable': invoice.is_vat_invoice
            }
            
            # Add customer information if available
            if invoice.customer:
                income_data.update({
                    'customer_name': invoice.customer.company_name,
                    'customer_contact': invoice.customer.contact_person,
                    'customer_phone': invoice.customer.phone,
                    'customer_trn': invoice.customer.trn,
                    'customer_email': invoice.customer.email
                })
            
            # Create income
            income = IncomeService.create_income(income_data, recorded_by)
            
            # Update invoice payment status
            invoice.status = 'paid'
            invoice.amount_paid = invoice.total_amount
            invoice.income_created = True
            db.session.commit()
            
            logger.info(f"Income {income.income_number} created from invoice {invoice.invoice_number}")
            
            return income
            
        except (ValidationError, BusinessRuleError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating income from invoice: {e}")
            raise DatabaseError(f"Failed to create income from invoice: {str(e)}")

    @staticmethod
    def create_income_from_payment(payment, recorded_by: Optional[int] = None) -> Income:
        """Create exactly one received income record for a completed payment.

        Invoice income is payment-based: partial payments create partial income
        records, and the unique payment link prevents duplicate records.
        """
        if payment.status != 'completed':
            raise BusinessRuleError("Only completed payments can create income")
        if not payment.invoice:
            raise ValidationError("Payment must belong to an invoice")

        existing_income = Income.query.filter_by(payment_id=payment.id).first() if payment.id else None
        if existing_income:
            return existing_income

        invoice = payment.invoice
        if payment.reference_number:
            existing_income = Income.query.filter_by(
                invoice_id=invoice.id,
                payment_reference=payment.reference_number,
            ).first()
            if existing_income:
                if existing_income.payment_id is None:
                    existing_income.payment = payment
                    db.session.flush()
                return existing_income

        if invoice.total_amount <= 0:
            raise ValidationError("Invoice total must be greater than zero")

        payment_ratio = payment.amount / invoice.total_amount
        tax_amount = invoice.vat_amount * payment_ratio
        base_amount = payment.amount - tax_amount
        payment_date = payment.payment_date.date() if payment.payment_date else date.today()
        customer = invoice.customer

        income = Income(
            income_type=IncomeType.INVOICE_PAYMENT.value,
            amount=base_amount,
            tax_amount=tax_amount,
            total_amount=payment.amount,
            currency=payment.currency or 'AED',
            exchange_rate=payment.exchange_rate or 1.0,
            income_date=payment_date,
            payment_received_date=payment_date,
            description=f"Payment for Invoice {invoice.invoice_number}",
            category='invoice',
            payment_method=payment.payment_method,
            payment_reference=payment.reference_number,
            customer_id=invoice.customer_id,
            customer_name=customer.company_name if customer else None,
            customer_contact=customer.contact_person if customer else None,
            customer_phone=customer.phone if customer else None,
            customer_trn=customer.trn if customer else None,
            customer_email=customer.email if customer else None,
            status='received',
            invoice_id=invoice.id,
            payment=payment,
            recorded_by=recorded_by or payment.recorded_by or 1,
            reference_number=payment.payment_reference or payment.reference_number,
            is_taxable=invoice.is_vat_invoice,
        )
        db.session.add(income)
        db.session.flush()
        return income
    
    @staticmethod
    def create_recurring_income_template(
        base_income_data: Dict,
        recurrence_pattern: str,
        recorded_by: int,
        recurrence_end_date: Optional[date] = None
        
    ) -> Income:
        """
        Create a recurring income template
        
        Args:
            base_income_data: Base income data for the template
            recurrence_pattern: Pattern (daily, weekly, monthly, quarterly, yearly)
            recurrence_end_date: Optional end date for recurrence
            recorded_by: User ID creating the template
            
        Returns:
            Income: Created recurring income template
        """
        try:
            # Validate recurrence pattern
            valid_patterns = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
            if recurrence_pattern not in valid_patterns:
                raise ValidationError(
                    f"Invalid recurrence pattern. Must be one of: {valid_patterns}"
                )
            
            # Validate end date if provided
            if recurrence_end_date:
                if recurrence_end_date <= base_income_data.get('income_date', date.today()):
                    raise ValidationError("Recurrence end date must be after start date")
            
            # Set recurring flags
            base_income_data['is_recurring'] = True
            base_income_data['recurrence_pattern'] = recurrence_pattern
            base_income_data['recurrence_end_date'] = recurrence_end_date
            
            # Create the template
            template = IncomeService.create_income(base_income_data, recorded_by)
            
            logger.info(f"Recurring income template {template.income_number} created")
            
            return template
            
        except ValidationError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating recurring income template: {e}")
            raise DatabaseError(f"Failed to create recurring income template: {str(e)}")
    
    @staticmethod
    def generate_recurring_incomes() -> List[Income]:
        """
        Generate next occurrences for all active recurring incomes
        
        Returns:
            List[Income]: List of generated incomes
        """
        generated_incomes = []
        
        try:
            # Get all active recurring incomes
            recurring_templates = Income.query.filter_by(
                is_recurring=True,
                status='received'  # Only generate from received templates
            ).all()
            
            for template in recurring_templates:
                try:
                    # Check if recurrence has ended
                    if (template.recurrence_end_date and 
                        template.recurrence_end_date < date.today()):
                        continue
                    
                    # Calculate next occurrence date
                    next_date = IncomeService._calculate_next_recurrence_date(
                        template.income_date,
                        template.recurrence_pattern
                    )
                    
                    if not next_date or next_date > date.today():
                        continue
                    
                    # Check if this occurrence already exists
                    existing_occurrence = Income.query.filter_by(
                        parent_income_id=template.id,
                        income_date=next_date
                    ).first()
                    
                    if existing_occurrence:
                        continue
                    
                    # Generate the next occurrence
                    next_income = Income(
                        income_type=template.income_type,
                        amount=template.amount,
                        currency=template.currency,
                        exchange_rate=template.exchange_rate,
                        tax_amount=template.tax_amount,
                        total_amount=template.total_amount,
                        description=f"Recurring: {template.description}",
                        category=template.category,
                        subcategory=template.subcategory,
                        income_date=next_date,
                        due_date=next_date,
                        payment_method=template.payment_method,
                        customer_name=template.customer_name,
                        customer_contact=template.customer_contact,
                        customer_phone=template.customer_phone,
                        customer_trn=template.customer_trn,
                        customer_email=template.customer_email,
                        is_recurring=True,
                        recurrence_pattern=template.recurrence_pattern,
                        recurrence_end_date=template.recurrence_end_date,
                        parent_income_id=template.id,
                        customer_id=template.customer_id,
                        recorded_by=template.recorded_by,
                        revenue_category=template.revenue_category,
                        gl_account=template.gl_account,
                        is_taxable=template.is_taxable,
                        status='pending'  # New occurrences are pending
                    )
                    
                    db.session.add(next_income)
                    generated_incomes.append(next_income)
                    
                    logger.info(
                        f"Generated recurring income from template {template.income_number} "
                        f"for date {next_date}"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Error generating recurrence for template {template.income_number}: {e}"
                    )
                    continue
            
            if generated_incomes:
                db.session.commit()
            
            return generated_incomes
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error generating recurring incomes: {e}")
            raise DatabaseError(f"Failed to generate recurring incomes: {str(e)}")
    
    @staticmethod
    def mark_income_as_received(
        income_id: int,
        recorded_by: int,
        payment_date: Optional[date] = None,
        payment_method: Optional[str] = None,
        payment_reference: Optional[str] = None
        
    ) -> Income:
        """
        Mark income as received (paid)
        
        Args:
            income_id: ID of the income to mark as received
            payment_date: Date payment was received
            payment_method: Method of payment
            payment_reference: Payment reference number
            recorded_by: User ID recording the payment
            
        Returns:
            Income: Updated income object
        """
        try:
            income = Income.query.get(income_id)
            
            if not income:
                raise ValidationError(f"Income with ID {income_id} not found")
            
            if income.status == 'received':
                raise BusinessRuleError(f"Income {income.income_number} is already marked as received")
            
            # Update income status and payment info
            income.status = 'received'
            income.payment_received_date = payment_date or date.today()
            
            if payment_method:
                income.payment_method = payment_method
            if payment_reference:
                income.payment_reference = payment_reference
            
            # Record audit trail
            IncomeService._record_audit_trail(
                income,
                'status',
                'pending',
                'received',
                recorded_by
            )
            
            db.session.commit()
            
            logger.info(f"Income {income.income_number} marked as received by user {recorded_by}")
            
            return income
            
        except (ValidationError, BusinessRuleError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error marking income as received: {e}")
            raise DatabaseError(f"Failed to mark income as received: {str(e)}")
    
    @staticmethod
    def update_income(income_id: int, update_data: Dict, updated_by: int) -> Income:
        """
        Update income record with validation
        
        Args:
            income_id: ID of the income to update
            update_data: Dictionary of fields to update
            updated_by: User ID making the update
            
        Returns:
            Income: Updated income object
        """
        try:
            income = Income.query.get(income_id)
            
            if not income:
                raise ValidationError(f"Income with ID {income_id} not found")
            
            # Check if income is already received (restrict certain updates)
            if income.status == 'received':
                restricted_fields = ['amount', 'tax_amount', 'total_amount', 'currency']
                for field in restricted_fields:
                    if field in update_data:
                        raise BusinessRuleError(
                            f"Cannot update {field} for received income"
                        )
            
            # Record old values for audit trail
            old_values = {}
            for field, new_value in update_data.items():
                if hasattr(income, field):
                    old_value = getattr(income, field)
                    old_values[field] = old_value
            
            # Apply updates
            for field, value in update_data.items():
                if hasattr(income, field) and field != 'id':
                    setattr(income, field, value)
            
            # Recalculate totals if financial fields were updated
            if any(field in update_data for field in ['amount', 'tax_amount']):
                income.total_amount = income.amount + income.tax_amount
            
            # Record audit trail for changed fields
            for field, old_value in old_values.items():
                new_value = getattr(income, field)
                if old_value != new_value:
                    IncomeService._record_audit_trail(
                        income,
                        field,
                        old_value,
                        new_value,
                        updated_by
                    )
            
            income.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Income {income.income_number} updated by user {updated_by}")
            
            return income
            
        except (ValidationError, BusinessRuleError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating income: {e}")
            raise DatabaseError(f"Failed to update income: {str(e)}")
    
    @staticmethod
    def get_income_summary(
        start_date: date,
        end_date: date,
        filters: Optional[Dict] = None
    ) -> Dict:
        """
        Get comprehensive income summary for a date range
        
        Args:
            start_date: Start date for summary
            end_date: End date for summary
            filters: Optional filters (customer_id, income_type, status, etc.)
            
        Returns:
            Dict: Comprehensive income summary
        """
        try:
            # Build query
            query = Income.query.filter(
                Income.income_date.between(start_date, end_date)
            )
            
            # Apply filters
            if filters:
                if 'customer_id' in filters:
                    query = query.filter_by(customer_id=filters['customer_id'])
                if 'income_type' in filters:
                    query = query.filter_by(income_type=filters['income_type'])
                if 'status' in filters:
                    query = query.filter_by(status=filters['status'])
                if 'category' in filters:
                    query = query.filter_by(category=filters['category'])
            
            incomes = query.all()
            
            # Calculate summary statistics
            total_count = len(incomes)
            received_count = sum(1 for i in incomes if i.status == 'received')
            pending_count = sum(1 for i in incomes if i.status == 'pending')
            overdue_count = sum(1 for i in incomes if i.is_overdue)
            
            total_amount = sum(i.total_amount_in_default_currency for i in incomes)
            received_amount = sum(
                i.total_amount_in_default_currency 
                for i in incomes if i.status == 'received'
            )
            pending_amount = sum(
                i.total_amount_in_default_currency 
                for i in incomes if i.status == 'pending'
            )
            overdue_amount = sum(
                i.total_amount_in_default_currency 
                for i in incomes if i.is_overdue
            )
            
            # Group by income type
            by_type = {}
            for income in incomes:
                income_type = income.income_type.value
                if income_type not in by_type:
                    by_type[income_type] = {
                        'count': 0,
                        'amount': 0,
                        'amount_aed': 0
                    }
                by_type[income_type]['count'] += 1
                by_type[income_type]['amount'] += income.total_amount
                by_type[income_type]['amount_aed'] += income.total_amount_in_default_currency
            
            # Group by status
            by_status = {}
            for income in incomes:
                status = income.status
                if status not in by_status:
                    by_status[status] = {
                        'count': 0,
                        'amount': 0,
                        'amount_aed': 0
                    }
                by_status[status]['count'] += 1
                by_status[status]['amount'] += income.total_amount
                by_status[status]['amount_aed'] += income.total_amount_in_default_currency
            
            # Group by customer
            by_customer = {}
            for income in incomes:
                if income.customer_id:
                    customer_id = income.customer_id
                    customer_name = income.customer_name or f"Customer {customer_id}"
                    
                    if customer_id not in by_customer:
                        by_customer[customer_id] = {
                            'name': customer_name,
                            'count': 0,
                            'amount': 0,
                            'amount_aed': 0
                        }
                    
                    by_customer[customer_id]['count'] += 1
                    by_customer[customer_id]['amount'] += income.total_amount
                    by_customer[customer_id]['amount_aed'] += income.total_amount_in_default_currency
            
            # Calculate collection rate
            collection_rate = 0
            if total_amount > 0:
                collection_rate = (received_amount / total_amount) * 100
            
            # Top 5 customers by income
            top_customers = sorted(
                by_customer.items(),
                key=lambda x: x[1]['amount_aed'],
                reverse=True
            )[:5]
            
            return {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': (end_date - start_date).days + 1
                },
                'overview': {
                    'total_count': total_count,
                    'received_count': received_count,
                    'pending_count': pending_count,
                    'overdue_count': overdue_count,
                    'total_amount': total_amount,
                    'received_amount': received_amount,
                    'pending_amount': pending_amount,
                    'overdue_amount': overdue_amount,
                    'collection_rate': round(collection_rate, 2),
                    'avg_daily_income': round(total_amount / max(1, (end_date - start_date).days + 1), 2)
                },
                'breakdown': {
                    'by_type': by_type,
                    'by_status': by_status,
                    'by_customer': by_customer
                },
                'insights': {
                    'top_customers': [
                        {
                            'customer_id': cust_id,
                            'customer_name': data['name'],
                            'total_amount': data['amount_aed'],
                            'transaction_count': data['count']
                        }
                        for cust_id, data in top_customers
                    ],
                    'largest_single_income': max(
                        [i.total_amount_in_default_currency for i in incomes] or [0]
                    ),
                    'smallest_single_income': min(
                        [i.total_amount_in_default_currency for i in incomes] or [0]
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating income summary: {e}")
            raise DatabaseError(f"Failed to generate income summary: {str(e)}")
    
    @staticmethod
    def get_income_forecast(
        start_date: date,
        end_date: date,
        include_recurring: bool = True
    ) -> Dict:
        """
        Generate income forecast based on historical data and recurring incomes
        
        Args:
            start_date: Start date for forecast
            end_date: End date for forecast
            include_recurring: Whether to include recurring income projections
            
        Returns:
            Dict: Income forecast data
        """
        try:
            # Get historical data for the past 12 months
            historical_start = datetime(start_date.year - 1, start_date.month, start_date.day).date()
            historical_end = start_date - timedelta(days=1)
            
            historical_summary = IncomeService.get_income_summary(
                historical_start,
                historical_end
            )
            
            # Calculate monthly averages
            historical_months = max(1, (historical_end - historical_start).days // 30)
            avg_monthly_income = (
                historical_summary['overview']['total_amount'] / historical_months
                if historical_months > 0 else 0
            )
            
            # Generate base forecast from historical average
            forecast_months = max(1, (end_date - start_date).days // 30)
            base_forecast = avg_monthly_income * forecast_months
            
            # Add recurring income projections
            recurring_forecast = 0
            if include_recurring:
                recurring_templates = Income.query.filter_by(
                    is_recurring=True,
                    status='received'
                ).all()
                
                for template in recurring_templates:
                    # Calculate number of occurrences in forecast period
                    occurrences = IncomeService._calculate_recurring_occurrences(
                        template,
                        start_date,
                        end_date
                    )
                    recurring_forecast += occurrences * template.total_amount_in_default_currency
            
            # Calculate total forecast
            total_forecast = base_forecast + recurring_forecast
            
            # Calculate forecast by month
            monthly_forecast = {}
            current_date = start_date
            
            while current_date <= end_date:
                month_key = current_date.strftime('%Y-%m')
                if month_key not in monthly_forecast:
                    monthly_forecast[month_key] = {
                        'month': current_date.strftime('%B %Y'),
                        'base_forecast': 0,
                        'recurring_forecast': 0,
                        'total_forecast': 0
                    }
                
                # Add monthly base forecast (pro-rated)
                month_days = (end_date - current_date).days + 1
                if month_days > 30:
                    month_days = 30
                
                monthly_forecast[month_key]['base_forecast'] += (
                    avg_monthly_income * (month_days / 30)
                )
                
                # Move to next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
            
            # Add recurring forecast to appropriate months
            for template in recurring_templates:
                next_date = IncomeService._calculate_next_recurrence_date(
                    template.income_date,
                    template.recurrence_pattern
                )
                
                while next_date and next_date <= end_date:
                    month_key = next_date.strftime('%Y-%m')
                    if month_key in monthly_forecast:
                        monthly_forecast[month_key]['recurring_forecast'] += (
                            template.total_amount_in_default_currency
                        )
                    
                    # Calculate next occurrence
                    next_date = IncomeService._calculate_next_recurrence_date(
                        next_date,
                        template.recurrence_pattern
                    )
            
            # Calculate total for each month
            for month_data in monthly_forecast.values():
                month_data['total_forecast'] = (
                    month_data['base_forecast'] + month_data['recurring_forecast']
                )
            
            return {
                'forecast_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': (end_date - start_date).days + 1,
                    'months': forecast_months
                },
                'historical_basis': {
                    'period': {
                        'start_date': historical_start.isoformat(),
                        'end_date': historical_end.isoformat()
                    },
                    'total_income': historical_summary['overview']['total_amount'],
                    'avg_monthly_income': round(avg_monthly_income, 2),
                    'collection_rate': historical_summary['overview']['collection_rate']
                },
                'forecast_totals': {
                    'base_forecast': round(base_forecast, 2),
                    'recurring_forecast': round(recurring_forecast, 2),
                    'total_forecast': round(total_forecast, 2),
                    'confidence_score': min(100, max(0, int(
                        historical_summary['overview']['collection_rate']
                    )))
                },
                'monthly_breakdown': list(monthly_forecast.values()),
                'assumptions': {
                    'historical_data_months': historical_months,
                    'include_recurring': include_recurring,
                    'growth_rate': 0,  # Could be parameterized
                    'seasonality_adjustment': 1.0  # Could be calculated from historical patterns
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating income forecast: {e}")
            raise DatabaseError(f"Failed to generate income forecast: {str(e)}")
    
    @staticmethod
    def reconcile_incomes_with_invoices() -> Dict:
        """
        Reconcile income records with invoice payments
        
        Returns:
            Dict: Reconciliation report
        """
        try:
            # Get all invoices with payments
            invoices = Invoice.query.options(
                db.joinedload(Invoice.payments),
                db.joinedload(Invoice.invoice_incomes)
            ).filter(
                Invoice.amount_paid > 0
            ).all()
            
            reconciliation_report = {
                'total_invoices': len(invoices),
                'invoices_with_discrepancy': 0,
                'total_discrepancy': 0,
                'details': []
            }
            
            for invoice in invoices:
                try:
                    # Calculate total payments
                    total_payments = sum(p.amount for p in invoice.payments if p.status == 'completed')
                    
                    # Calculate total income recorded
                    total_income = sum(i.total_amount for i in invoice.invoice_incomes if i.status == 'received')
                    
                    # Calculate discrepancy
                    discrepancy = abs(total_payments - total_income)
                    
                    if discrepancy > 0.01:  # Allow small rounding differences
                        reconciliation_report['invoices_with_discrepancy'] += 1
                        reconciliation_report['total_discrepancy'] += discrepancy
                        
                        reconciliation_report['details'].append({
                            'invoice_number': invoice.invoice_number,
                            'invoice_id': invoice.id,
                            'total_payments': total_payments,
                            'total_income': total_income,
                            'discrepancy': discrepancy,
                            'status': invoice.status,
                            'income_created_flag': invoice.income_created
                        })
                        
                        # Auto-fix if possible
                        if total_payments > total_income and not invoice.income_created:
                            IncomeService.sync_missing_income_from_invoice(invoice.id, 1)
                
                except Exception as e:
                    logger.error(f"Error reconciling invoice {invoice.invoice_number}: {e}")
                    continue
            
            return reconciliation_report
            
        except Exception as e:
            logger.error(f"Error during income-invoice reconciliation: {e}")
            raise DatabaseError(f"Failed to reconcile incomes with invoices: {str(e)}")
    
    @staticmethod
    def sync_missing_income_from_invoice(invoice_id: int, recorded_by: int) -> List[Income]:
        """
        Create missing income records for invoice payments
        
        Args:
            invoice_id: ID of the invoice
            recorded_by: User ID recording the sync
            
        Returns:
            List[Income]: List of created income records
        """
        try:
            invoice = Invoice.query.options(
                db.joinedload(Invoice.payments),
                db.joinedload(Invoice.customer)
            ).get(invoice_id)
            if not invoice:
                raise ValidationError(f"Invoice with ID {invoice_id} not found")

            created_incomes = []
            if any(income.payment_id is None for income in invoice.invoice_incomes):
                logger.warning(
                    "Skipping invoice %s: unlinked historical income requires manual reconciliation",
                    invoice.invoice_number,
                )
                return created_incomes

            for payment in invoice.payments:
                if payment.status != 'completed' or payment.income:
                    continue
                created_incomes.append(
                    IncomeService.create_income_from_payment(
                        payment,
                        recorded_by=recorded_by,
                    )
                )

            if created_incomes:
                invoice.income_created = invoice.amount_paid >= invoice.total_amount
                db.session.commit()
            return created_incomes
        except ValidationError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error syncing missing income from invoice: {e}")
            raise DatabaseError(f"Failed to sync missing income from invoice: {str(e)}")
    
    @staticmethod
    def _calculate_next_recurrence_date(
        last_date: date,
        recurrence_pattern: str
    ) -> Optional[date]:
        """
        Calculate next recurrence date based on pattern
        
        Args:
            last_date: Last occurrence date
            recurrence_pattern: Recurrence pattern
            
        Returns:
            Optional[date]: Next recurrence date or None if invalid
        """
        try:
            if recurrence_pattern == 'daily':
                return last_date + timedelta(days=1)
            elif recurrence_pattern == 'weekly':
                return last_date + timedelta(weeks=1)
            elif recurrence_pattern == 'monthly':
                # Handle month end dates
                if last_date.month == 12:
                    return last_date.replace(year=last_date.year + 1, month=1)
                else:
                    return last_date.replace(month=last_date.month + 1)
            elif recurrence_pattern == 'quarterly':
                return last_date + timedelta(days=90)  # Approximately 3 months
            elif recurrence_pattern == 'yearly':
                return last_date.replace(year=last_date.year + 1)
            else:
                return None
        except Exception:
            return None
    
    @staticmethod
    def _calculate_recurring_occurrences(
        template: Income,
        start_date: date,
        end_date: date
    ) -> int:
        """
        Calculate number of recurring occurrences in a date range
        
        Args:
            template: Recurring income template
            start_date: Start date
            end_date: End date
            
        Returns:
            int: Number of occurrences
        """
        if not template.is_recurring or not template.recurrence_pattern:
            return 0
        
        occurrences = 0
        next_date = IncomeService._calculate_next_recurrence_date(
            template.income_date,
            template.recurrence_pattern
        )
        
        while next_date and next_date <= end_date:
            if next_date >= start_date:
                if (template.recurrence_end_date and 
                    next_date > template.recurrence_end_date):
                    break
                occurrences += 1
            
            next_date = IncomeService._calculate_next_recurrence_date(
                next_date,
                template.recurrence_pattern
            )
        
        return occurrences
    
    @staticmethod
    def _record_audit_trail(
        income: Income,
        field: str,
        old_value,
        new_value,
        changed_by: int
    ) -> None:
        """
        Record audit trail for income changes
        
        Args:
            income: Income object
            field: Field that changed
            old_value: Old value
            new_value: New value
            changed_by: User ID who made the change
        """
        try:
            # In a real implementation, this would write to an audit table
            # For now, we'll just log it
            logger.info(
                f"Income {income.income_number}: {field} changed from "
                f"{old_value} to {new_value} by user {changed_by}"
            )
            
            # Example audit table implementation:
            # audit = IncomeAudit(
            #     income_id=income.id,
            #     field_changed=field,
            #     old_value=str(old_value),
            #     new_value=str(new_value),
            #     changed_by=changed_by
            # )
            # db.session.add(audit)
            
        except Exception as e:
            logger.error(f"Error recording audit trail: {e}")
    
    @staticmethod
    def _trigger_post_creation_events(income: Income) -> None:
        """
        Trigger events after income creation
        
        Args:
            income: Newly created income
        """
        try:
            # Example: Send notifications
            if income.status == 'received':
                IncomeService._send_income_received_notification(income)
            
            # Example: Update customer balance
            if income.customer_id:
                IncomeService._update_customer_balance(income.customer_id)
            
            # Example: Trigger webhook for external systems
            IncomeService._trigger_webhook('income.created', income)
            
        except Exception as e:
            logger.error(f"Error triggering post-creation events: {e}")
    
    @staticmethod
    def _send_income_received_notification(income: Income) -> None:
        """Send notification for received income"""
        # Implementation would depend on your notification system
        pass
    
    @staticmethod
    def _update_customer_balance(customer_id: int) -> None:
        """Update customer's cached balance"""
        # Implementation would update a cached balance field in customer table
        pass
    
    @staticmethod
    def _trigger_webhook(event_type: str, income: Income) -> None:
        """Trigger webhook for external systems"""
        # Implementation would send HTTP request to configured webhook URLs
        pass