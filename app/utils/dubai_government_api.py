import requests
import json
from datetime import datetime
from flask import current_app
import logging
from requests.exceptions import RequestException
from app.constants import UserType


logger = logging.getLogger(__name__)

class DubaiGovernmentAPI:
    def __init__(self):
        # These would be configured in your config.py
        self.base_url = current_app.config.get('DUBAI_GOV_API_BASE_URL', 'https://api.dubaigate.gov.ae')
        self.api_key = current_app.config.get('DUBAI_GOV_API_KEY')
        self.timeout = current_app.config.get('API_TIMEOUT', 30)
        
    def _make_request(self, endpoint, method='GET', data=None, params=None):
        """
        Generic method to make API requests to Dubai government services
        """
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            if method.upper() == 'GET':
                response = requests.get(
                    url, 
                    headers=headers, 
                    params=params, 
                    timeout=self.timeout
                )
            elif method.upper() == 'POST':
                response = requests.post(
                    url, 
                    headers=headers, 
                    json=data, 
                    timeout=self.timeout
                )
            elif method.upper() == 'PUT':
                response = requests.put(
                    url, 
                    headers=headers, 
                    json=data, 
                    timeout=self.timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except RequestException as e:
            logger.error(f"API request failed: {e}")
            raise Exception(f"Government API service unavailable: {str(e)}")
        except ValueError as e:
            logger.error(f"JSON parsing error: {e}")
            raise Exception("Invalid response from government API")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise Exception(f"Government API integration error: {str(e)}")
    
    def validate_trn(self, trn_number):
        """
        Validate UAE TRN (Tax Registration Number) with FTA
        Returns: {'valid': bool, 'company_name': str, 'status': str}
        """
        try:
            endpoint = "/fta/trn/validate"
            data = {
                "trn_number": trn_number,
                "request_id": f"trn_val_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            }
            
            response = self._make_request(endpoint, 'POST', data)
            
            return {
                'valid': response.get('isValid', False),
                'company_name': response.get('legalName', ''),
                'status': response.get('status', 'UNKNOWN'),
                'trn_number': trn_number,
                'verified_at': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"TRN validation failed for {trn_number}: {e}")
            return {
                'valid': False,
                'company_name': '',
                'status': 'VALIDATION_FAILED',
                'error': str(e)
            }
    
    def get_vat_certificate(self, trn_number):
        """
        Retrieve VAT certificate information for a TRN
        """
        try:
            endpoint = f"/fta/vat-certificate/{trn_number}"
            response = self._make_request(endpoint)
            
            return {
                'trn_number': trn_number,
                'certificate_number': response.get('certificateNumber'),
                'issue_date': response.get('issueDate'),
                'expiry_date': response.get('expiryDate'),
                'status': response.get('status'),
                'business_activities': response.get('businessActivities', [])
            }
            
        except Exception as e:
            logger.error(f"VAT certificate retrieval failed: {e}")
            raise Exception(f"Could not retrieve VAT certificate: {str(e)}")
    
    def submit_vat_return(self, vat_data):
        """
        Submit VAT return to FTA
        vat_data should contain: trn_number, tax_period, taxable_sales, vat_due, etc.
        """
        try:
            endpoint = "/fta/vat-returns/submit"
            
            payload = {
                "trn_number": vat_data['trn_number'],
                "tax_period": vat_data['tax_period'],
                "taxable_sales": vat_data['taxable_sales'],
                "vat_due": vat_data['vat_due'],
                "vat_reclaimed": vat_data.get('vat_reclaimed', 0),
                "net_vat_due": vat_data['vat_due'] - vat_data.get('vat_reclaimed', 0),
                "submission_date": datetime.now().isoformat()
            }
            
            response = self._make_request(endpoint, 'POST', payload)
            
            return {
                'submission_id': response.get('submissionId'),
                'status': response.get('status'),
                'receipt_number': response.get('receiptNumber'),
                'submission_date': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"VAT return submission failed: {e}")
            raise Exception(f"VAT return submission failed: {str(e)}")
    
    def check_shipment_customs(self, tracking_number, shipment_details):
        """
        Check customs clearance status with Dubai Customs
        """
        try:
            endpoint = "/customs/clearance/check"
            
            payload = {
                "tracking_number": tracking_number,
                "shipment_type": shipment_details.get('shipment_type'),
                "content_value": shipment_details.get('content_value'),
                "content_description": shipment_details.get('content_description'),
                "origin_country": shipment_details.get('origin_country'),
                "destination_country": "AE"
            }
            
            response = self._make_request(endpoint, 'POST', payload)
            
            return {
                'clearance_required': response.get('clearanceRequired', False),
                'clearance_status': response.get('clearanceStatus'),
                'customs_duty': response.get('customsDuty', 0),
                'vat_amount': response.get('vatAmount', 0),
                'documents_required': response.get('documentsRequired', []),
                'estimated_clearance_time': response.get('estimatedClearanceTime')
            }
            
        except Exception as e:
            logger.error(f"Customs check failed: {e}")
            return {
                'clearance_required': True,
                'clearance_status': 'CHECK_FAILED',
                'error': str(e)
            }
    
    def get_dubai_traffic_info(self, route_coordinates):
        """
        Get real-time traffic information for Dubai routes
        """
        try:
            endpoint = "/rta/traffic-info"
            
            payload = {
                "route": route_coordinates,
                "timestamp": datetime.now().isoformat()
            }
            
            response = self._make_request(endpoint, 'POST', payload)
            
            return {
                'traffic_conditions': response.get('trafficConditions', {}),
                'estimated_delay': response.get('estimatedDelay', 0),
                'alternative_routes': response.get('alternativeRoutes', []),
                'toll_gates': response.get('tollGates', [])
            }
            
        except Exception as e:
            logger.error(f"Traffic info retrieval failed: {e}")
            return {
                'traffic_conditions': 'UNKNOWN',
                'estimated_delay': 0,
                'error': str(e)
            }
    
    def validate_emirates_id(self, emirates_id_number):
        """
        Validate Emirates ID with ICA
        """
        try:
            endpoint = "/ica/emirates-id/validate"
            
            payload = {
                "emirates_id": emirates_id_number,
                "request_type": "validation"
            }
            
            response = self._make_request(endpoint, 'POST', payload)
            
            return {
                'valid': response.get('isValid', False),
                'full_name': response.get('fullName'),
                'nationality': response.get('nationality'),
                'expiry_date': response.get('expiryDate'),
                'status': response.get('status')
            }
            
        except Exception as e:
            logger.error(f"Emirates ID validation failed: {e}")
            return {
                'valid': False,
                'status': 'VALIDATION_FAILED',
                'error': str(e)
            }
    
    def get_business_license_info(self, license_number):
        """
        Get business license information from DED
        """
        try:
            endpoint = f"/ded/business-license/{license_number}"
            
            response = self._make_request(endpoint)
            
            return {
                'license_number': license_number,
                'company_name': response.get('companyName'),
                'legal_form': response.get('legalForm'),
                'activities': response.get('activities', []),
                'issue_date': response.get('issueDate'),
                'expiry_date': response.get('expiryDate'),
                'status': response.get('status')
            }
            
        except Exception as e:
            logger.error(f"Business license check failed: {e}")
            raise Exception(f"Business license information unavailable: {str(e)}")

# Utility function to use the API
def get_dubai_gov_api():
    return DubaiGovernmentAPI()