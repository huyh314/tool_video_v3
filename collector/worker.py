from pathlib import Path
import json

from collector.downloader import download_video
from collector.gemini import GeminiClient, validate_extraction
from shared.models import validate_script, safe_id
from shared.runtime import LeaseHeartbeat, safe_error


def process_post(config, client, store, job, gemini=None):
    post = job['post']
    post_id = post['post_id']
    event_id = 'post:'+job['job_id']
    done = store.get_artifact('completed:'+job['job_id'])
    if done:
        store.enqueue(event_id, done['action'], done['payload'])
        return done['action']=='complete_post'
    gemini = gemini or GeminiClient(config)
    downloaded = None
    extraction = None
    base = dict(job_id=job['job_id'],worker_id=job['worker_id'],post_id=post_id)
    try:
        with LeaseHeartbeat(client,job) as lease:
            downloaded = download_video(post,config)
            extraction = store.get_artifact('extraction:'+post_id)
            if extraction is not None:
                try:
                    extraction = validate_extraction(extraction)
                    if extraction['uncertain']:
                        extraction = None
                except ValueError:
                    extraction = None
            if extraction is None:
                extraction = gemini.extract(downloaded,post.get('caption',''))
                store.put_artifact('extraction:'+post_id,extraction)
            extraction = validate_extraction(extraction)
            if extraction['uncertain']:
                raise ValueError('NEEDS_REVIEW: nội dung nguồn chưa chắc chắn; cần kiểm tra video.')
            script = store.get_artifact('script:'+post_id)
            if script is None:
                script = gemini.write_script(extraction,job.get('brand') or config['default_signature'])
                script = validate_script(dict(script,script_id='script_'+post_id,post_id=post_id,version=1))
                store.put_artifact('script:'+post_id,script)
            lease.check()
        output_dir = Path(config['data_dir'])/'analysis'/safe_id(post_id)
        output_dir.mkdir(parents=True,exist_ok=True)
        (output_dir/'extraction.json').write_text(json.dumps(extraction,ensure_ascii=False,indent=2),encoding='utf-8')
        (output_dir/'script.json').write_text(json.dumps(script,ensure_ascii=False,indent=2),encoding='utf-8')
        payload = dict(base,download_path=str(downloaded),extraction=extraction,script=script)
        action = 'complete_post'
    except Exception as exc:
        payload = dict(base,error=safe_error(exc,config))
        if downloaded:
            payload['download_path']=str(downloaded)
        if extraction:
            payload['extraction']=extraction
        action = 'fail_post'
    store.put_artifact('completed:'+job['job_id'],dict(action=action,payload=payload))
    store.enqueue(event_id,action,payload)
    return action=='complete_post'
