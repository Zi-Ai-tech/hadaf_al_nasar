from sqlalchemy import text
from app import db
from app.utils.validation import validate_customer_data
from datetime import datetime

class CustomerService:
    @staticmethod
    def get_db_session():
        return db.session
    
    @staticmethod
    def get_customers(filter_type='active'):
        """Get customers with optional filtering"""
        session = CustomerService.get_db_session()
        
        try:
            if filter_type == 'inactive':
                result = session.execute(text("SELECT * FROM customer WHERE is_active = false ORDER BY company_name"))
            elif filter_type == 'all':
                result = session.execute(text("SELECT * FROM customer ORDER BY company_name"))
            else:
                result = session.execute(text("SELECT * FROM customer WHERE is_active = true ORDER BY company_name"))
            
            customers = []
            for row in result:
                customer_dict = {}
                for key, value in row._mapping.items():
                    if hasattr(value, 'isoformat'):
                        customer_dict[key] = value.isoformat()
                    else:
                        customer_dict[key] = value
                customers.append(customer_dict)
            
            return customers, None
        except Exception as e:
            return None, f"Database error: {str(e)}"
    
    @staticmethod
    def get_customer_by_id(customer_id):
        """Get a single customer by ID"""
        session = CustomerService.get_db_session()
        
        try:
            result = session.execute(
                text("SELECT * FROM customer WHERE id = :id"),
                {'id': customer_id}
            ).fetchone()
            
            if not result:
                return None, "Customer not found"
            
            customer_dict = {}
            for key, value in result._mapping.items():
                if hasattr(value, 'isoformat'):
                    customer_dict[key] = value.isoformat()
                else:
                    customer_dict[key] = value
            
            return customer_dict, None
        except Exception as e:
            return None, f"Database error: {str(e)}"
    
    @staticmethod
    def check_duplicate_trn(trn, exclude_id=None):
        """Check if TRN already exists"""
        session = CustomerService.get_db_session()
        try:
            if exclude_id:
                result = session.execute(
                    text("SELECT id FROM customer WHERE trn = :trn AND id != :exclude_id"),
                    {'trn': trn, 'exclude_id': exclude_id}
                ).fetchone()
            else:
                result = session.execute(
                    text("SELECT id FROM customer WHERE trn = :trn"),
                    {'trn': trn}
                ).fetchone()
            return result is not None
        except Exception as e:
            raise Exception(f"Error checking duplicate TRN: {str(e)}")
    
    @staticmethod
    def create_customer(form_data):
        """Create a new customer"""
        session = CustomerService.get_db_session()
        
        try:
            customer_data = CustomerService._extract_customer_data(form_data)
            
            # Validate data
            is_valid, errors = validate_customer_data(customer_data)
            if not is_valid:
                return False, "Validation errors: " + ", ".join(errors)
            
            # Check for duplicate TRN
            if CustomerService.check_duplicate_trn(customer_data['trn']):
                return False, f"TRN {customer_data['trn']} already exists"
            
            # Insert customer
            session.execute(
                text("""
                    INSERT INTO customer (
                        company_name, trade_license_number, trn, legal_form, 
                        contact_person, contact_designation, email, phone, mobile,
                        address, emirate, city, po_box, business_activities, 
                        industry_type, credit_limit, payment_terms, is_active,
                        created_at, updated_at
                    ) VALUES (
                        :company_name, :trade_license_number, :trn, :legal_form,
                        :contact_person, :contact_designation, :email, :phone, :mobile,
                        :address, :emirate, :city, :po_box, :business_activities,
                        :industry_type, :credit_limit, :payment_terms, :is_active,
                        :created_at, :updated_at
                    )
                """),
                {
                    'company_name': customer_data['company_name'],
                    'trade_license_number': customer_data['trade_license_number'],
                    'trn': customer_data['trn'],
                    'legal_form': customer_data['legal_form'],
                    'contact_person': customer_data['contact_person'],
                    'contact_designation': customer_data['contact_designation'],
                    'email': customer_data['email'],
                    'phone': customer_data['phone'],
                    'mobile': customer_data['mobile'],
                    'address': customer_data['address'],
                    'emirate': customer_data['emirate'],
                    'city': customer_data['city'],
                    'po_box': customer_data['po_box'],
                    'business_activities': customer_data['business_activities'],
                    'industry_type': customer_data['industry_type'],
                    'credit_limit': customer_data['credit_limit'],
                    'payment_terms': customer_data['payment_terms'],
                    'is_active': customer_data['is_active'],
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
            )
            session.commit()
            return True, "Customer added successfully!"
            
        except Exception as e:
            session.rollback()
            return False, f"Database error: {str(e)}"
    
    @staticmethod
    def update_customer(customer_id, form_data):
        """Update an existing customer"""
        session = CustomerService.get_db_session()
        
        try:
            customer_data = CustomerService._extract_customer_data(form_data)
            
            # Validate data
            is_valid, errors = validate_customer_data(customer_data, is_update=True)
            if not is_valid:
                return False, "Validation errors: " + ", ".join(errors)
            
            # Check for duplicate TRN (excluding current customer)
            if CustomerService.check_duplicate_trn(customer_data['trn'], exclude_id=customer_id):
                return False, f"TRN {customer_data['trn']} already exists for another customer"
            
            # Update customer
            result = session.execute(
                text("""
                    UPDATE customer SET 
                        company_name = :company_name,
                        email = :email,
                        mobile = :mobile,
                        phone = :phone,
                        trade_license_number = :trade_license_number,
                        trn = :trn,
                        legal_form = :legal_form,
                        contact_person = :contact_person,
                        contact_designation = :contact_designation,
                        address = :address,
                        emirate = :emirate,
                        city = :city,
                        po_box = :po_box,
                        business_activities = :business_activities,
                        industry_type = :industry_type,
                        credit_limit = :credit_limit,
                        payment_terms = :payment_terms,
                        is_active = :is_active,
                        updated_at = :updated_at
                    WHERE id = :id
                """),
                {
                    'id': customer_id,
                    'company_name': customer_data['company_name'],
                    'email': customer_data['email'],
                    'mobile': customer_data['mobile'],
                    'phone': customer_data['phone'],
                    'trade_license_number': customer_data['trade_license_number'],
                    'trn': customer_data['trn'],
                    'legal_form': customer_data['legal_form'],
                    'contact_person': customer_data['contact_person'],
                    'contact_designation': customer_data['contact_designation'],
                    'address': customer_data['address'],
                    'emirate': customer_data['emirate'],
                    'city': customer_data['city'],
                    'po_box': customer_data['po_box'],
                    'business_activities': customer_data['business_activities'],
                    'industry_type': customer_data['industry_type'],
                    'credit_limit': customer_data['credit_limit'],
                    'payment_terms': customer_data['payment_terms'],
                    'is_active': customer_data['is_active'],
                    'updated_at': datetime.utcnow()
                }
            )
            
            if result.rowcount == 0:
                return False, "Customer not found"
                
            session.commit()
            return True, "Customer updated successfully!"
            
        except Exception as e:
            session.rollback()
            return False, f"Database error: {str(e)}"
    
    @staticmethod
    def _extract_customer_data(form_data):
        """Extract and normalize customer data from form"""
        credit_limit = form_data.get('credit_limit')
        try:
            credit_limit = float(credit_limit) if credit_limit else 0.0
        except (TypeError, ValueError):
            credit_limit = 0.0
            
        return {
            'company_name': form_data.get('company_name', '').strip(),
            'trade_license_number': form_data.get('trade_license_number', '').strip(),
            'trn': form_data.get('trn', '').strip(),
            'legal_form': form_data.get('legal_form', '').strip(),
            'contact_person': form_data.get('contact_person', '').strip(),
            'contact_designation': form_data.get('contact_designation', '').strip(),
            'email': form_data.get('email', '').strip(),
            'phone': form_data.get('phone', '').strip(),
            'mobile': form_data.get('mobile', '').strip(),
            'address': form_data.get('address', '').strip(),
            'emirate': form_data.get('emirate', '').strip(),
            'city': form_data.get('city', '').strip(),
            'po_box': form_data.get('po_box', '').strip(),
            'business_activities': form_data.get('business_activities', '').strip(),
            'industry_type': form_data.get('industry_type', '').strip(),
            'credit_limit': credit_limit,
            'payment_terms': form_data.get('payment_terms', 'NET30'),
            'is_active': form_data.get('is_active') in ['true', 'on', '1', True]
        }
    
    @staticmethod
    def change_customer_status(customer_id, new_status):
        """Activate or deactivate a customer"""
        session = CustomerService.get_db_session()
        
        try:
            # Check if customer exists
            customer = session.execute(
                text("SELECT id, is_active FROM customer WHERE id = :id"),
                {'id': customer_id}
            ).fetchone()
            
            if not customer:
                return False, "Customer not found"
            
            if customer.is_active == new_status:
                status_text = "active" if new_status else "inactive"
                return False, f"Customer is already {status_text}"
            
            # Update status
            session.execute(
                text("UPDATE customer SET is_active = :status, updated_at = NOW() WHERE id = :id"),
                {'status': new_status, 'id': customer_id}
            )
            session.commit()
            
            action = "activated" if new_status else "deactivated"
            return True, f"Customer {action} successfully!"
            
        except Exception as e:
            session.rollback()
            return False, f"Database error: {str(e)}"
    
    @staticmethod
    def delete_customer(customer_id):
        """Delete customer permanently"""
        session = CustomerService.get_db_session()
        
        try:
            # Check if customer exists and is inactive
            customer = session.execute(
                text("SELECT id, is_active FROM customer WHERE id = :id"),
                {'id': customer_id}
            ).fetchone()
            
            if not customer:
                return False, "Customer not found"
            
            if customer.is_active:
                return False, "Cannot delete active customer. Please deactivate first."
            
            # Check for invoices
            invoice_tables = [
                ("invoice", "customer_id"),
                ("invoices", "customer_id"),
            ]
            
            total_invoices = 0
            for table_name, fk_column in invoice_tables:
                try:
                    result = session.execute(
                        text(f"SELECT COUNT(*) as count FROM {table_name} WHERE {fk_column} = :id"),
                        {'id': customer_id}
                    ).fetchone()
                    if result:
                        total_invoices += result.count
                except Exception:
                    continue
            
            if total_invoices > 0:
                return False, f'Cannot delete customer. There are {total_invoices} invoice(s) linked to this customer.'
            
            # Delete customer
            result = session.execute(
                text("DELETE FROM customer WHERE id = :id"),
                {'id': customer_id}
            )
            
            if result.rowcount == 0:
                return False, "Customer not found"
                
            session.commit()
            return True, "Customer deleted permanently!"
            
        except Exception as e:
            session.rollback()
            return False, f"Database error: {str(e)}"