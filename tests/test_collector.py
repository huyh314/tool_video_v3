import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from collector.gemini import GeminiClient, validate_extraction
from collector.worker import process_post
from shared.store import Store


class CollectorTests(unittest.TestCase):
    def test_no_source_or_uncertainty_never_becomes_script(self):
        with self.assertRaises(ValueError):
            validate_extraction({'source_text':'','segments':[], 'uncertain':False})
        with self.assertRaises(ValueError):
            validate_extraction({'source_text':'Một ý', 'segments':[], 'uncertain':'false'})

    def test_api_block_or_malformed_json_is_failure(self):
        api = GeminiClient({'gemini_api_key':'secret', 'gemini_model':'gemini-2.5-flash'})
        with patch.object(api, '_request', return_value={'candidates':[]}):
            with self.assertRaises(RuntimeError):
                api.generate_json([{'text':'test'}], {'type':'OBJECT','properties':{}})

    def test_success_cached_and_outbox_failure_does_not_repeat_ai(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = {'data_dir':Path(temp), 'default_signature':'Kênh'}
            store = Store(Path(temp)/'state.sqlite3')
            client = Mock()
            job = {'job_id':'j1','worker_id':'w1','post':{'post_id':'fb_123','post_url':'https://www.facebook.com/watch/?v=123','caption':'gốc'}}
            api = Mock()
            api.extract.return_value = {'source_text':'Thông tin trong video','segments':[],'uncertain':False}
            api.write_script.return_value = {'hook':'Tiêu đề', 'items':['Ý một','Ý hai'],'caption':'mới','brand':'Kênh','template':'auto','duration_seconds':0}
            with patch('collector.worker.download_video', return_value=Path(temp)/'source.mp4') as dl:
                process_post(cfg, client, store, job, api)
                process_post(cfg, client, store, job, api)
                self.assertEqual(dl.call_count, 1)
                self.assertEqual(api.extract.call_count, 1)
                self.assertEqual(api.write_script.call_count, 1)
            self.assertEqual(len(store.pending()), 1)
            self.assertEqual(store.pending()[0]['action'], 'complete_post')

    def test_gemini_failure_queues_fail_no_canned_script(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = {'data_dir':Path(temp), 'default_signature':'Kênh'}
            store = Store(Path(temp)/'state.sqlite3')
            job = {'job_id':'j2','worker_id':'w1','post':{'post_id':'fb_456','post_url':'https://www.facebook.com/reel/456/','caption':'gốc'}}
            api = Mock()
            api.extract.side_effect = RuntimeError('AI offline')
            with patch('collector.worker.download_video', return_value=Path(temp)/'source.mp4'):
                process_post(cfg, Mock(), store, job, api)
            self.assertEqual(store.pending()[0]['action'],'fail_post')
            self.assertIsNone(store.get_artifact('script:fb_456'))

