import json
import urllib.error
import urllib.request

from decouple import config


class PremblyError(Exception):
    pass


class PremblyClient:
    base_url = 'https://api.prembly.com'

    def __init__(self):
        self.app_id = config('PREMBLY_APP_ID', default='')
        self.api_key = config('PREMBLY_API_KEY', default='')

    def is_configured(self):
        return bool(self.app_id and self.api_key)

    def verify_nin_basic(self, nin_number):
        response = self._request(
            path='/verification/vnin-basic',
            payload={'number': nin_number},
        )
        return response

    def _request(self, *, path, payload):
        if not self.is_configured():
            raise PremblyError('Prembly is not configured. Set PREMBLY_APP_ID and PREMBLY_API_KEY.')

        request = urllib.request.Request(
            f'{self.base_url}{path}',
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'app-id': self.app_id,
                'x-api-key': self.api_key,
            },
        )
        data = json.dumps(payload).encode('utf-8')

        try:
            with urllib.request.urlopen(request, data=data, timeout=30) as response:
                body = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode('utf-8', errors='ignore')
            raise PremblyError(f'Prembly request failed: {error_body or exc.reason}') from exc
        except urllib.error.URLError as exc:
            raise PremblyError(f'Unable to reach Prembly: {exc.reason}') from exc

        if not body.get('status'):
            raise PremblyError(body.get('detail') or body.get('message') or 'Prembly verification failed.')
        return body
