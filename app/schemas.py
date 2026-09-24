from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from datetime import datetime
import re

class CustomerSchema(Schema):
    id = fields.Int(dump_only=True)
    company_name = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    trade_license_number = fields.Str(validate=validate.Length(max=100))
    trn = fields.Str(validate=validate.Length(max=50))
    legal_form = fields.Str(validate=validate.Length(max=50))
    contact_person = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    contact_designation = fields.Str(validate=validate.Length(max=100))
    email = fields.Email(validate=validate.Length(max=100))
    phone = fields.Str(required=True, validate=validate.Length(min=8, max=20))
    mobile = fields.Str(validate=validate.Length(max=20))
    address = fields.Str(validate=validate.Length(max=500))
    emirate = fields.Str(validate=validate.Length(max=50))
    city = fields.Str(validate=validate.Length(max=50))
    po_box = fields.Str(validate=validate.Length(max=50))
    business_activities = fields.Str(validate=validate.Length(max=500))
    industry_type = fields.Str(validate=validate.Length(max=100))
    credit_limit = fields.Float(validate=validate.Range(min=0))
    payment_terms = fields.Str(validate=validate.Length(max=50))
    is_active = fields.Bool(load_default=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates_schema
    def validate_phone_format(self, data, **kwargs):
        if 'phone' in data and data['phone']:
            phone_pattern = re.compile(r'^\+?[\d\s\-\(\)]{8,20}$')
            if not phone_pattern.match(data['phone']):
                raise ValidationError('Invalid phone number format')

class InvoiceSchema(Schema):
    id = fields.Int(dump_only=True)
    invoice_number = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    invoice_type = fields.Str(required=True, validate=validate.OneOf(['vat', 'non_vat']))
    customer_id = fields.Int(required=True)
    issue_date = fields.Date(required=True)
    due_date = fields.Date(required=True)
    amount = fields.Float(required=True, validate=validate.Range(min=0))
    vat_amount = fields.Float(validate=validate.Range(min=0))
    total_amount = fields.Float(required=True, validate=validate.Range(min=0))
    status = fields.Str(validate=validate.OneOf(['pending', 'paid', 'overdue']))
    description = fields.Str(validate=validate.Length(max=500))
    created_at = fields.DateTime(dump_only=True)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        if 'issue_date' in data and 'due_date' in data:
            if data['due_date'] < data['issue_date']:
                raise ValidationError('Due date must be after issue date')