from weasyprint import HTML
from flask import render_template, current_app
import os
from datetime import datetime

class PDFService:
    @staticmethod
    def generate_invoice_pdf(invoice):
        """Generate PDF for a paid invoice"""
        try:
            # Only generate PDF for paid invoices
            if invoice.status != 'paid':
                raise ValueError("PDF can only be generated for paid invoices")
            
            # Render HTML template
            html_content = render_template(
                'accounts/invoice_pdf.html',
                invoice=invoice
            )
            
            # Generate PDF
            pdf = HTML(string=html_content).write_pdf()
            
            return pdf
            
        except Exception as e:
            current_app.logger.error(f"PDF generation error: {str(e)}")
            raise Exception(f"Failed to generate PDF: {str(e)}")

    @staticmethod
    def save_invoice_pdf(invoice, pdf_data):
        """Save PDF to file system"""
        try:
            # Create invoices directory if it doesn't exist
            invoices_dir = os.path.join(current_app.root_path, 'static', 'invoices')
            os.makedirs(invoices_dir, exist_ok=True)
            
            # Generate filename
            filename = f"invoice_{invoice.invoice_number}_{datetime.now().strftime('%Y%m%d')}.pdf"
            filepath = os.path.join(invoices_dir, filename)
            
            # Save PDF
            with open(filepath, 'wb') as f:
                f.write(pdf_data)
            
            return filepath
            
        except Exception as e:
            current_app.logger.error(f"PDF save error: {str(e)}")
            raise Exception(f"Failed to save PDF: {str(e)}")