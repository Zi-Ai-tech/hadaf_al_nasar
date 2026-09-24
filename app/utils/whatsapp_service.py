import requests
from flask import current_app
import logging
from twilio.rest import Client
import json

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        # Using Twilio API for WhatsApp (you can also use other providers)
        self.account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        self.auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        self.whatsapp_from = current_app.config.get('TWILIO_WHATSAPP_FROM')
        self.enabled = bool(self.account_sid and self.auth_token and self.whatsapp_from)
    
    def send_salary_notification(self, salary, phone_number):
        """
        Send salary notification via WhatsApp
        phone_number: should be in format +971501234567
        """
        if not self.enabled:
            logger.warning("WhatsApp service not configured")
            return False
        
        try:
            # Format phone number (ensure it starts with +971)
            if not phone_number.startswith('+'):
                if phone_number.startswith('0'):
                    phone_number = '+971' + phone_number[1:]
                else:
                    phone_number = '+971' + phone_number
            
            # Create message content
            message = self._create_salary_message(salary)
            
            # Send via Twilio
            client = Client(self.account_sid, self.auth_token)
            
            message = client.messages.create(
                body=message,
                from_=f'whatsapp:{self.whatsapp_from}',
                to=f'whatsapp:{phone_number}'
            )
            
            logger.info(f"WhatsApp message sent to {phone_number}: {message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False
    
    def _create_salary_message(self, salary):
        """Create formatted WhatsApp message for salary notification"""
        employee = salary.employee
        net_salary = salary.net_salary
        
        message = f"""🏢 *Hadaf Al Nasar Logistics*
💼 *Salary Payment Notification*

👤 *Employee:* {employee.name}
📅 *Period:* {salary.month}/{salary.year}
💳 *Net Salary:* AED {net_salary:,.2f}

📋 *Breakdown:*
• Basic Salary: AED {salary.basic_salary:,.2f}
• Allowances: AED {(salary.housing_allowance + salary.transportation_allowance + salary.other_allowances):,.2f}
• Overtime: AED {(salary.overtime_hours * salary.overtime_rate):,.2f}
• Deductions: AED {salary.deductions_amount:,.2f if salary.deductions_amount is not None else 0}

📅 *Payment Date:* {salary.payment_date.strftime('%d-%m-%Y') if salary.payment_date else 'Processing'}
✅ *Status:* {salary.status.value.upper()}

If you have any questions, please contact accounts department.

*Note:* This is an automated message. Do not reply to this number.
"""
        return message

    # Alternative method using WhatsApp Business API
    def send_whatsapp_template_message(self, phone_number, template_name, parameters):
        """
        Send template message via WhatsApp Business API
        """
        try:
            # Format phone number
            if not phone_number.startswith('+'):
                phone_number = '+971' + phone_number.lstrip('0')
            
            url = f"https://graph.facebook.com/v13.0/{current_app.config.get('WHATSAPP_BUSINESS_ID')}/messages"
            
            headers = {
                'Authorization': f'Bearer {current_app.config.get("WHATSAPP_ACCESS_TOKEN")}',
                'Content-Type': 'application/json'
            }
            
            data = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": "en"
                    },
                    "components": parameters
                }
            }
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Error sending WhatsApp template: {str(e)}")
            return False

def get_whatsapp_service():
    return WhatsAppService()