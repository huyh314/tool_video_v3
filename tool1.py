"""Tool 1: authenticated browser bridge + download, analysis and script queue."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import threading
import time
import uuid

from collector.bridge import make_server
from collector.gemini import GeminiClient
from collector.worker import process_post
from shared.config import load_config
from shared.media import validate_video
from shared.runtime import instance_lock, safe_error
from shared.sheet import SheetClient
from shared.store import Store


def check_protocol(client, config):
    result=client.call('ping')
    if result.get('protocol')!=3:
        raise RuntimeError('Web App đang dùng mã cũ. Cập nhật GoogleAppsScript_Code.gs v3 và triển khai phiên bản mới.')
    expected=config.get('spreadsheet_id')
    if expected and result.get('spreadsheet_id')!=expected:
        raise RuntimeError('Web App không trỏ tới Google Sheet đã cấu hình.')


def tick(config, client, store, worker_id, allow_scan=True):
    store.flush(client)
    if store.pending():
        return 'Chờ đồng bộ kết quả: '+str(len(store.pending()))+' sự kiện.'
    scan=store.get_artifact('active_scan')
    if scan:
        if time.time()-scan.get('claimed_at',0)>600:
            store.save_scan_result(dict(job_id=scan['job_id'],worker_id=scan['worker_id'],channel_id=scan['channel_id'],
                                        posts=[],partial=True,error='Extension không hoàn tất lượt quét trong 10 phút.'))
            return 'Quét quá thời gian; kiểm tra extension.'
        if time.time()-scan.get('renewed_at',0)>60:
            client.call('renew_lease',job_id=scan['job_id'],worker_id=scan['worker_id'],lease_seconds=900)
            # Never resurrect a scan completed by the HTTP thread during renewal.
            store.update_active_scan(scan['job_id'],{'renewed_at':time.time()})
        return 'Chờ extension quét: '+scan['channel'].get('name','')
    day=datetime.now(timezone(timedelta(hours=7))).date().isoformat()
    quota=store.get_artifact('quota:'+day) or {'count':0}
    if config.get('auto_analyze',True) and quota['count']<int(config.get('max_analysis_per_day',30)):
        job=client.call('claim_post',worker_id=worker_id,lease_seconds=900).get('job')
        if job:
            # Count attempts before external API calls; restart cannot reset budget.
            store.put_artifact('quota:'+day,{'count':quota['count']+1})
            print('Đang tải/phân tích và tạo kịch bản:',job['post']['post_id'],flush=True)
            store.put_artifact('collector_status',{'status':'Đang phân tích '+job['post']['post_id']})
            ok=process_post(config,client,store,job)
            store.flush(client)
            return ('Đã tạo kịch bản: ' if ok else 'Bài cần xử lý lỗi: ')+job['post']['post_id']
    if allow_scan:
        job=client.call('claim_scan',worker_id=worker_id,lease_seconds=900).get('job')
        if job:
            job.update(claimed_at=time.time(),renewed_at=time.time())
            store.put_artifact('active_scan',job)
            return 'Đã giao lượt quét cho extension: '+job['channel'].get('name','')
    return 'Đang chờ công việc mới.'


def main(argv=None):
    parser=argparse.ArgumentParser(description='Tool 1 — Theo dõi Facebook và tạo kịch bản')
    parser.add_argument('--once',action='store_true',help='Xử lý tối đa một bài đã có trên Sheet; không mở lượt quét mới')
    parser.add_argument('--watch',action='store_true',help='Theo dõi liên tục (mặc định)')
    parser.add_argument('--analyze-file',type=Path,help='Phân tích một MP4 local bằng Gemini, lưu nháp local')
    args=parser.parse_args(argv)
    config=load_config()
    store=Store(config['data_dir']/'state.sqlite3')
    try:
        with instance_lock(config['data_dir'],'collector'):
            if args.analyze_file:
                info=validate_video(args.analyze_file,config)
                if info['duration']>config['max_video_seconds'] or args.analyze_file.stat().st_size>config['max_video_mb']*1024*1024:
                    raise RuntimeError('Video vượt giới hạn kích thước/thời lượng.')
                api=GeminiClient(config)
                extraction=api.extract(args.analyze_file)
                script=api.write_script(extraction,config['default_signature'])
                output=config['data_dir']/'manual_analysis'
                output.mkdir(exist_ok=True)
                (output/'result.json').write_text(json.dumps({'extraction':extraction,'script':script},ensure_ascii=False,indent=2),encoding='utf-8')
                print('Đã phân tích video và lưu nháp:',output/'result.json')
                return 0
            client=SheetClient(config)
            check_protocol(client,config)
            identity=store.get_artifact('collector_identity') or {'worker_id':'collector_'+uuid.uuid4().hex[:16]}
            store.put_artifact('collector_identity',identity)
            if args.once:
                print(tick(config,client,store,identity['worker_id'],allow_scan=False))
                return 0 if not store.pending() else 1
            server=make_server(config,store)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            print('🟢 TOOL 1 ĐANG CHẠY VÀ LẮNG NGHE LỆNH QUÉT TỪ GOOGLE SHEET...',flush=True)
            print('👉 Bạn có thể mở Chrome Extension kiểm tra (sẽ báo ĐÃ KẾT NỐI).',flush=True)
            last=''
            try:
                while True:
                    try:
                        status=tick(config,client,store,identity['worker_id'])
                    except Exception as exc:
                        status='Lỗi: '+safe_error(exc,config)
                    store.put_artifact('collector_status',{'status':status,'updated_at':datetime.now(timezone.utc).isoformat()})
                    if status!=last:
                        print(status,flush=True)
                        last=status
                    time.sleep(max(10,int(config.get('poll_seconds',30))))
            finally:
                server.shutdown()
                server.server_close()
    except KeyboardInterrupt:
        print('\nĐã dừng tool 1; tiến độ được lưu.')
        return 0
    except Exception as exc:
        print('Lỗi:',safe_error(exc,config))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
