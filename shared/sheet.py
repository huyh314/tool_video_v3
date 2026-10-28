import requests


class SheetError(RuntimeError):
    def __init__(self, message, code='REMOTE_ERROR'):
        super().__init__(message)
        self.code = code


class SheetClient:
    def __init__(self, config):
        self.config = config
        self.url = str(config.get('webhook_url', '')).strip()
        self.configured = self.url.startswith('https://script.google.com/macros/s/') and self.url.endswith('/exec')

    def call(self, action, **payload):
        from shared.runtime import safe_error
        if not self.configured:
            raise RuntimeError('Chưa cấu hình URL Apps Script Web App hợp lệ.')
        try:
            response = requests.post(self.url, json={'token':self.config.get('sheet_token',''), 'action':action, **payload},
                                     headers={'Content-Type':'text/plain;charset=utf-8'}, timeout=(10, 60))
            if response.status_code != 200:
                raise RuntimeError(f'Sheet HTTP {response.status_code}')
            try:
                body = response.json()
            except ValueError:
                raise RuntimeError('Web App chưa trả JSON. Kiểm tra quyền truy cập và phiên bản triển khai.') from None
            if not isinstance(body, dict) or body.get('status') != 'success':
                message = body.get('message', 'Không đúng giao thức v3; cần cập nhật Apps Script.') if isinstance(body, dict) else 'Phản hồi Sheet không hợp lệ.'
                raise SheetError(str(message)[:500],body.get('code','REMOTE_ERROR') if isinstance(body,dict) else 'REMOTE_ERROR')
            return body
        except Exception as exc:
            raise SheetError(safe_error(exc, self.config),getattr(exc,'code','NETWORK_ERROR')) from None

