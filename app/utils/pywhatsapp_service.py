import pywhatkit
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PyWhatsAppService:
    def __init__(self):
        self.enabled = True  # Always enabled
    
    def send_salary_notification(self, salary, phone_number):
        """
        Send WhatsApp message using pywhatkit
        """
        try:
            # Format phone number
            if not phone_number.startswith('+'):
                phone_number = '+971' + phone_number.lstrip('0')
            
            # Create message
            message = self._create_salary_message(salary)
            
            # Send message (will open browser and send via web.whatsapp.com)
            # Send immediately or schedule for 1 minute later
            send_time = datetime.now() + timedelta(minutes=1)
            
            pywhatkit.sendwhatmsg(
                phone_no=phone_number,
                message=message,
                time_hour=send_time.hour,
                time_min=send_time.minute,
                wait_time=15,
                tab_close=True,
                close_time=3
            )
            
            logger.info(f"WhatsApp message sent to {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False
    
    def _create_salary_message(self, salary):
        """Create formatted WhatsApp message"""
        # Same message format as before
        employee = salary.employee
        return f"""🏢 *Hadaf Al Nasar Logistics*
💼 *Salary Payment Notification*

👤 Employee: {employee.name}
📅 Period: {salary.month}/{salary.year}
💳 Net Salary: AED {salary.net_salary:,.2f}

If you have any questions, please contact accounts department."""