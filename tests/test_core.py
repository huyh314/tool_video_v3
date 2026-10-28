import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from shared.models import canonical_facebook_video, script_hash, validate_script
from shared.store import Store
from shared.sheet import SheetClient


class CoreTests(unittest.TestCase):
    def test_url_preserves_video_identity(self):
        self.assertEqual(canonical_facebook_video('https://www.facebook.com/watch/?v=123&ref=x'), ('fb_123', '123', 'https://www.facebook.com/watch/?v=123'))
        self.assertEqual(canonical_facebook_video('https://www.facebook.com/reel/123/?foo=x')[0], 'fb_123')
        with self.assertRaises(ValueError):
            canonical_facebook_video('https://evil.example/watch/?v=123')
        with self.assertRaises(ValueError):
            canonical_facebook_video('https://www.facebook.com/somepage')

    def test_hash_changes_only_content(self):
        script = dict(hook=' CHỮ VIỆT ', items=[' Một ý ', 'Hai ý'], caption='Caption', brand='Kênh', template='auto', duration_seconds=0)
        self.assertEqual(script_hash(script), script_hash(dict(script, version=9)))
        self.assertNotEqual(script_hash(script), script_hash(dict(script, hook='Khác')))
        with self.assertRaises(ValueError):
            validate_script(dict(script, items=[]))

    def test_outbox_survives_failure_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'jobs.db'
            store = Store(path)
            store.enqueue('job1', 'complete_post', {'post_id': 'fb_123'})
            store.enqueue('job1', 'complete_post', {'post_id': 'fb_123'})
            client = Mock()
            client.call.side_effect = RuntimeError('offline')
            self.assertEqual(store.flush(client), 0)
            store = Store(path)
            self.assertEqual(len(store.pending()), 1)
            client.call.side_effect = None
            self.assertEqual(store.flush(client), 1)
            self.assertEqual(store.pending(), [])

    def test_sheet_rejects_http_200_application_error(self):
        cfg = {'webhook_url':'https://script.google.com/macros/s/test/exec','sheet_token':'private-token'}
        client = SheetClient(cfg)
        response = Mock(status_code=200)
        response.json.return_value = {'status':'error','message':'bad private-token'}
        with patch('shared.sheet.requests.post', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'bad') as ctx:
                client.call('ping')
            self.assertNotIn('private-token', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()

