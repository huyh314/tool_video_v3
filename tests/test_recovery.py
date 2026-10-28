import hashlib
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from collector.downloader import download_video
from collector.worker import process_post
from shared.sheet import SheetError
from shared.store import Store


def test_uncertain_source_is_reanalyzed_on_explicit_retry(tmp_path):
    cfg={'data_dir':tmp_path,'default_signature':'Kênh'}
    store=Store(tmp_path/'state.sqlite3')
    store.put_artifact('extraction:fb_123',{'source_text':'Chữ chưa rõ','segments':[],'uncertain':True})
    api=Mock()
    api.extract.return_value={'source_text':'Chữ đã rõ','segments':[],'uncertain':False}
    api.write_script.return_value={'hook':'Tiêu đề','items':['Ý một'],'caption':'','brand':'Kênh'}
    job={'job_id':'retry','worker_id':'w','post':{'post_id':'fb_123','post_url':'https://www.facebook.com/reel/123/'}}
    with patch('collector.worker.download_video',return_value=tmp_path/'source.mp4'):
        assert process_post(cfg,Mock(),store,job,api)
    assert api.extract.call_count==1


@pytest.mark.parametrize('cache_problem',['broken_json','corrupt_file'])
def test_download_recovery_uses_fresh_attempt(tmp_path,cache_problem):
    cfg={'data_dir':tmp_path}
    directory=tmp_path/'raw'/'ch'/'fb_123'
    directory.mkdir(parents=True)
    (directory/'source.mp4').write_bytes(b'bad')
    manifest=directory/'download.json'
    manifest.write_text('{' if cache_problem=='broken_json' else json.dumps({'video_id':'123','sha256':hashlib.sha256(b'bad').hexdigest()}),encoding='utf-8')
    def run(command,**kwargs):
        template=Path(command[command.index('-o')+1])
        assert template.parent!=directory
        template.with_name('source.mp4').write_bytes(b'valid')
        template.with_name('source.info.json').write_text(json.dumps({'id':'123','ext':'mp4'}))
        return Mock(returncode=0)
    def validate(path,config):
        if Path(path).read_bytes()==b'bad':
            raise RuntimeError('invalid')
        return {'duration':10,'width':720,'height':1280,'has_audio':True}
    with patch('collector.downloader.subprocess.run',side_effect=run),patch('collector.downloader.validate_video',side_effect=validate):
        path=download_video({'post_id':'fb_123','channel_id':'ch','post_url':'https://www.facebook.com/reel/123/'},cfg)
    assert path.read_bytes()==b'valid'
    assert json.loads(manifest.read_text())['video_id']=='123'


def test_cached_download_obeys_new_limits(tmp_path):
    directory=tmp_path/'raw'/'ch'/'fb_123'
    directory.mkdir(parents=True)
    (directory/'source.mp4').write_bytes(b'valid')
    (directory/'download.json').write_text(json.dumps({'video_id':'123','sha256':hashlib.sha256(b'valid').hexdigest()}))
    with patch('collector.downloader.validate_video',return_value={'duration':70}),patch('collector.downloader.subprocess.run') as run:
        with pytest.raises(RuntimeError,match='giới hạn'):
            download_video({'post_id':'fb_123','channel_id':'ch','post_url':'https://www.facebook.com/reel/123/'},
                           {'data_dir':tmp_path,'max_video_seconds':60})
        run.assert_not_called()


def test_superseded_outbox_is_audited_without_blocking(tmp_path):
    store=Store(tmp_path/'state.sqlite3')
    store.enqueue('old','fail_render',{'job_id':'old'})
    client=Mock(config={})
    client.call.side_effect=SheetError('superseded','STALE_OWNER')
    store.flush(client)
    assert not store.pending()
    assert store.get_artifact('quarantine:old')['payload']['job_id']=='old'


def test_late_scan_renewal_cannot_resurrect_completed_job(tmp_path):
    store=Store(tmp_path/'state.sqlite3')
    store.put_artifact('active_scan',{'job_id':'j'})
    store.save_scan_result({'job_id':'j','posts':[]})
    assert not store.update_active_scan('j',{'renewed_at':100})
    assert store.get_artifact('active_scan') is None

