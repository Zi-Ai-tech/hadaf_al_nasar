import requests
import json
from flask import current_app
import logging
from datetime import datetime
from app.constants import UserType


logger = logging.getLogger(__name__)

class DubaiCompanySearch:
    def __init__(self):
        self.api_base = current_app.config.get('DUBAI_DED_API_BASE_URL', 'https://api.ded.ae')
        self.api_key = current_app.config.get('DUBAI_DED_API_KEY')
        self.timeout = 30
    
    def search_companies(self, search_term, search_type='name'):
        """
        Search for companies in Dubai DED database
        search_type: 'name', 'license', 'trn'
        """
        try:
            endpoint = "/v1/companies/search"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            params = {
                'q': search_term,
                'type': search_type,
                'page': 1,
                'limit': 20
            }
            
            response = requests.get(
                f"{self.api_base}{endpoint}",
                headers=headers,
                params=params,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            data = response.json()
            
            return self._format_company_results(data.get('data', []))
            
        except Exception as e:
            logger.error(f"Company search failed: {e}")
            # Fallback to mock data for development
            return self._get_mock_companies(search_term)
    
    def get_company_details(self, license_number):
        """
        Get detailed company information by license number
        """
        try:
            endpoint = f"/v1/companies/{license_number}"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json'
            }
            
            response = requests.get(
                f"{self.api_base}{endpoint}",
                headers=headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            data = response.json()
            
            return self._format_company_details(data)
            
        except Exception as e:
            logger.error(f"Company details fetch failed: {e}")
            return self._get_mock_company_details(license_number)
    
    def _format_company_results(self, companies):
        """Format search results"""
        formatted = []
        for company in companies:
            formatted.append({
                'license_number': company.get('licenseNumber'),
                'company_name_english': company.get('nameEnglish'),
                'company_name_arabic': company.get('nameArabic'),
                'legal_form': company.get('legalForm'),
                'status': company.get('status'),
                'establishment_date': company.get('establishmentDate'),
                'trn': company.get('trn'),
                'address': company.get('address'),
                'emirate': company.get('emirate'),
                'activities': company.get('mainActivities', [])
            })
        return formatted
    
    def _format_company_details(self, company_data):
        """Format detailed company information"""
        return {
            'license_number': company_data.get('licenseNumber'),
            'company_name_english': company_data.get('nameEnglish'),
            'company_name_arabic': company_data.get('nameArabic'),
            'legal_form': company_data.get('legalForm'),
            'status': company_data.get('status'),
            'establishment_date': company_data.get('establishmentDate'),
            'expiry_date': company_data.get('licenseExpiryDate'),
            'trn': company_data.get('trn'),
            'address_english': company_data.get('addressEnglish'),
            'address_arabic': company_data.get('addressArabic'),
            'emirate': company_data.get('emirate'),
            'city': company_data.get('city'),
            'po_box': company_data.get('poBox'),
            'business_activities': company_data.get('activities', []),
            'partners': company_data.get('partners', []),
            'contact_info': company_data.get('contactInformation', {})
        }
    
    def _get_mock_companies(self, search_term):
        """Mock data for development and testing"""
        mock_companies = [
            {
                'license_number': '1234567',
                'company_name_english': 'Alokozay International Ltd',
                'company_name_arabic': 'ألوكوزاي الدولية ش.ذ.م.م',
                'legal_form': 'LLC',
                'status': 'Active',
                'establishment_date': '2010-05-15',
                'trn': '100000000000001',
                'address': 'Dubai Investment Park, Dubai, UAE',
                'emirate': 'Dubai',
                'activities': ['Trading', 'Import/Export', 'FMCG']
            },
            {
                'license_number': '7654321',
                'company_name_english': 'Crown Packaging Industries',
                'company_name_arabic': 'كراون للصناعات التغليفية',
                'legal_form': 'FZCO',
                'status': 'Active',
                'establishment_date': '2008-11-20',
                'trn': '100000000000002',
                'address': 'Jebel Ali Free Zone, Dubai, UAE',
                'emirate': 'Dubai',
                'activities': ['Manufacturing', 'Packaging', 'Export']
            },
            {
                'license_number': '9876543',
                'company_name_english': 'Emirates Logistics LLC',
                'company_name_arabic': 'الإمارات للخدمات اللوجستية ش.ذ.م.م',
                'legal_form': 'LLC',
                'status': 'Active',
                'establishment_date': '2015-03-10',
                'trn': '100000000000003',
                'address': 'Deira, Dubai, UAE',
                'emirate': 'Dubai',
                'activities': ['Logistics', 'Transport', 'Warehousing']
            }
        ]
        
        # Filter mock data based on search term
        return [company for company in mock_companies 
                if search_term.lower() in company['company_name_english'].lower() or 
                   search_term.lower() in company['company_name_arabic'].lower()]
    
    def _get_mock_company_details(self, license_number):
        """Mock company details for development"""
        mock_details = {
            '1234567': {
                'license_number': '1234567',
                'company_name_english': 'Alokozay International Ltd',
                'company_name_arabic': 'ألوكوزاي الدولية ش.ذ.م.م',
                'legal_form': 'LLC',
                'status': 'Active',
                'establishment_date': '2010-05-15',
                'expiry_date': '2025-05-14',
                'trn': '100000000000001',
                'address_english': 'Plot 123, Dubai Investment Park 2, Dubai, UAE',
                'address_arabic': 'قطعة 123، دبي إنفستمنت بارك 2، دبي، الإمارات',
                'emirate': 'Dubai',
                'city': 'Dubai',
                'po_box': '12345',
                'business_activities': [
                    {'activity_code': '5190', 'activity_name': 'Wholesale trade'},
                    {'activity_code': '4630', 'activity_name': 'Import/Export'}
                ],
                'partners': [
                    {'name': 'Ahmed Alokozay', 'nationality': 'Afghan', 'share_percentage': 60},
                    {'name': 'Mohammed Khan', 'nationality': 'Pakistani', 'share_percentage': 40}
                ],
                'contact_info': {
                    'phone': '+97142234567',
                    'email': 'info@alokozay.com',
                    'website': 'www.alokozay.com'
                }
            }
        }
        return mock_details.get(license_number, {})

def get_company_searcher():
    return DubaiCompanySearch()