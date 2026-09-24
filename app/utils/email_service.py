import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template
from config import Config
from app.constants import UserType


class EmailService:
    def __init__(self):
        self.smtp_server = Config.SMTP_SERVER
        self.smtp_port = Config.SMTP_PORT
        self.smtp_username = Config.SMTP_USERNAME
        self.smtp_password = Config.SMTP_PASSWORD
    
    def send_shipment_update(self, shipment, recipient_email):
        """
        Send shipment status update email
        """
        subject = f"Shipment Update: {shipment.tracking_number}"
        
        # Render HTML template
        html_content = render_template(
            'emails/shipment_update.html',
            shipment=shipment,
            customer=shipment.customer
        )
        
        # Send email
        self.send_email(recipient_email, subject, html_content)
    
    def send_invoice(self, invoice, recipient_email):
        """
        Send invoice email
        """
        subject = f"Invoice: {invoice.invoice_number}"
        
        html_content = render_template(
            'emails/invoice.html',
            invoice=invoice,
            customer=invoice.customer
        )
        
        self.send_email(recipient_email, subject, html_content)
    
    def send_email(self, recipient, subject, html_content):
        """
        Generic email sending function
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = recipient
            msg['Subject'] = subject
            
            msg.attach(MIMEText(html_content, 'html'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            print(f"Email sent to {recipient}")
            
        except Exception as e:
            print(f"Error sending email: {e}")