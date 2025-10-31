import requests
import json
from django.conf import settings

class PaystackClient:
    def __init__(self):
        self.secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', 'sk_test_your_test_key')
        self.base_url = "https://api.paystack.co"
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }
    
    def _make_request(self, method, endpoint, data=None):
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers, params=data)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            else:
                return {'status': False, 'message': 'Invalid HTTP method'}
            
            response_data = response.json()
            
            # Log the request and response
            from .models import PaymentProviderLog
            PaymentProviderLog.objects.create(
                provider='paystack',
                action=endpoint,
                reference=data.get('reference', '') if data else '',
                request_data=data or {},
                response_data=response_data,
                status='success' if response_data.get('status') else 'failed'
            )
            
            return response_data
            
        except requests.exceptions.RequestException as e:
            # Log error
            from .models import PaymentProviderLog
            PaymentProviderLog.objects.create(
                provider='paystack',
                action=endpoint,
                reference=data.get('reference', '') if data else '',
                request_data=data or {},
                response_data={'error': str(e)},
                status='failed'
            )
            return {'status': False, 'message': str(e)}
    
    def initialize_transaction(self, email, amount, reference, metadata=None):
        """Initialize a payment transaction"""
        endpoint = "/transaction/initialize"
        data = {
            'email': email,
            'amount': int(amount * 100),  # Paystack expects amount in kobo
            'reference': reference,
            'metadata': metadata or {}
        }
        return self._make_request('POST', endpoint, data)
    
    def verify_transaction(self, reference):
        """Verify a transaction"""
        endpoint = f"/transaction/verify/{reference}"
        return self._make_request('GET', endpoint)
    
    def create_transfer_recipient(self, name, account_number, bank_code, currency='NGN'):
        """Create a transfer recipient"""
        endpoint = "/transferrecipient"
        data = {
            'type': 'nuban',
            'name': name,
            'account_number': account_number,
            'bank_code': bank_code,
            'currency': currency
        }
        return self._make_request('POST', endpoint, data)
    
    def initiate_transfer(self, amount, recipient_code, reference, reason=None):
        """Initiate a transfer to a recipient"""
        endpoint = "/transfer"
        data = {
            'source': 'balance',
            'amount': int(amount * 100),  # Paystack expects amount in kobo
            'recipient': recipient_code,
            'reference': reference,
            'reason': reason or 'Withdrawal from Flow'
        }
        return self._make_request('POST', endpoint, data)
    
    def verify_account_number(self, account_number, bank_code):
        """Verify bank account number"""
        endpoint = f"/bank/resolve?account_number={account_number}&bank_code={bank_code}"
        return self._make_request('GET', endpoint)
    
    def list_banks(self):
        """Get list of supported banks"""
        endpoint = "/bank"
        return self._make_request('GET', endpoint)

# Singleton instance
paystack_client = PaystackClient()