import json
import urllib.error
import urllib.parse
import urllib.request

from decouple import config


class PaystackError(Exception):
    pass


class PaystackClient:
    base_url = 'https://api.paystack.co'

    def __init__(self):
        self.secret_key = config('PAYSTACK_SECRET_KEY', default='')

    def is_configured(self):
        return bool(self.secret_key)

    def initialize_transaction(self, *, email, amount_kobo, reference, callback_url, channels, metadata=None):
        payload = {
            'email': email,
            'amount': str(amount_kobo),
            'reference': reference,
            'currency': 'NGN',
            'callback_url': callback_url,
            'channels': channels,
        }
        if metadata:
            payload['metadata'] = metadata
        response = self._request(
            method='POST',
            path='/transaction/initialize',
            payload=payload,
        )
        return response['data']

    def verify_transaction(self, reference):
        encoded_reference = urllib.parse.quote(reference, safe='')
        response = self._request(
            method='GET',
            path=f'/transaction/verify/{encoded_reference}',
        )
        return response['data']

    def _request(self, *, method, path, payload=None):
        if not self.is_configured():
            raise PaystackError('Paystack is not configured. Set PAYSTACK_SECRET_KEY.')

        request = urllib.request.Request(
            f'{self.base_url}{path}',
            method=method,
            headers={
                'Authorization': f'Bearer {self.secret_key}',
                'Content-Type': 'application/json',
            },
        )
        data = None
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')

        try:
            with urllib.request.urlopen(request, data=data, timeout=30) as response:
                body = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode('utf-8', errors='ignore')
            raise PaystackError(f'Paystack request failed: {error_body or exc.reason}') from exc
        except urllib.error.URLError as exc:
            raise PaystackError(f'Unable to reach Paystack: {exc.reason}') from exc

        if not body.get('status'):
            raise PaystackError(body.get('message', 'Paystack request failed.'))
        return body
