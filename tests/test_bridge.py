import threading

import pytest
import requests

from collector.bridge import make_server
from shared.store import Store


@pytest.fixture
def bridge(tmp_path):
    store=Store(tmp_path/'state.sqlite3')
    server=make_server({'port':0,'local_api_token':'local-test-token'},store)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    yield base,store
    server.shutdown()
    server.server_close()
    thread.join()


def test_bridge_rejects_missing_token_and_web_origins(bridge):
    base,_=bridge
    assert requests.get(base+'/api/health',timeout=5).status_code==401
    headers={'X-Local-Token':'local-test-token','Origin':'https://evil.example'}
    assert requests.get(base+'/api/health',headers=headers,timeout=5).status_code==401


def test_scan_ack_requires_durable_result_and_is_idempotent(bridge):
    base,store=bridge
    job={'job_id':'j1','channel_id':'ch1','worker_id':'w','channel':{'url':'https://www.facebook.com/source'}}
    store.put_artifact('active_scan',job)
    headers={'X-Local-Token':'local-test-token','Origin':'chrome-extension://test'}
    body={'job_id':'j1','channel_id':'ch1','posts':[{'post_id':'fb_123','post_url':'https://www.facebook.com/watch/?v=123&ref=x','caption':'Nội dung'}]}
    response=requests.post(base+'/api/scan/result',json=body,headers=headers,timeout=5)
    assert response.status_code==200
    assert response.json()['saved']==1
    assert store.get_artifact('active_scan') is None
    assert len(store.pending())==1
    assert store.pending()[0]['payload']['posts'][0]['post_url']=='https://www.facebook.com/watch/?v=123'
    assert store.pending()[0]['payload']['posts'][0]['likes'] is None
    assert requests.post(base+'/api/scan/result',json=body,headers=headers,timeout=5).json()['duplicate']
    assert len(store.pending())==1
