import hmac
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from shared.models import canonical_facebook_video


def make_server(config, store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            print(f"[BRIDGE] {format % args}", flush=True)

        def _origin(self):
            origin = self.headers.get('Origin','')
            return not origin or origin.startswith('chrome-extension://')

        def _authorized(self):
            ok_host = self.headers.get('Host') == f"127.0.0.1:{self.server.server_port}"
            ok_orig = self._origin()
            ok_tok = hmac.compare_digest(self.headers.get('X-Local-Token',''),config['local_api_token'])
            if not (ok_host and ok_orig and ok_tok):
                print(f"[BRIDGE AUTH FAIL] host={ok_host}, origin={ok_orig} ({self.headers.get('Origin')}), tok={ok_tok}", flush=True)
                return False
            return True

        def _reply(self, code, data):
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type','application/json;charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body)))
            origin = self.headers.get('Origin','')
            if origin.startswith('chrome-extension://'):
                self.send_header('Access-Control-Allow-Origin',origin)
                self.send_header('Vary','Origin')
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            if not self._origin() or self.headers.get('Host') != f"127.0.0.1:{self.server.server_port}":
                self._reply(403,{'ok':False})
                return
            self.send_response(204)
            origin=self.headers.get('Origin','')
            if origin:
                self.send_header('Access-Control-Allow-Origin',origin)
            self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers','Content-Type, X-Local-Token')
            self.end_headers()

        def do_GET(self):
            if not self._authorized():
                self._reply(401,{'ok':False,'error':'Mã kết nối không hợp lệ.'})
                return
            path=urlparse(self.path).path
            if path=='/api/health':
                state=store.get_artifact('collector_status') or {}
                self._reply(200,{'ok':True,'protocol':3,'pending_sync':len(store.pending()),**state})
            elif path=='/api/scan':
                self._reply(200,{'job':store.get_artifact('active_scan')})
            else:
                self._reply(404,{'ok':False})

        def do_POST(self):
            if not self._authorized():
                self._reply(401,{'ok':False,'error':'Mã kết nối không hợp lệ.'})
                return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=1024*1024:
                    raise ValueError('Payload vượt giới hạn.')
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict):
                    raise ValueError('Payload phải là object.')
                job_id=str(body.get('job_id',''))
                if not job_id or len(job_id)>200:
                    raise ValueError('Job ID không hợp lệ.')
                if store.get_artifact('scan_done:'+job_id):
                    self._reply(200,{'ok':True,'duplicate':True})
                    return
                job=store.get_artifact('active_scan')
                if not job or job.get('job_id')!=job_id:
                    raise ValueError('Công việc đã hết hạn hoặc không khớp.')
                if urlparse(self.path).path=='/api/scan/heartbeat':
                    store.put_artifact('scan_heartbeat',{'job_id':job_id,'time':time.time()})
                    self._reply(200,{'ok':True})
                    return
                if urlparse(self.path).path!='/api/scan/result':
                    self._reply(404,{'ok':False})
                    return
                if body.get('channel_id')!=job['channel_id']:
                    raise ValueError('Kênh của kết quả không khớp công việc.')
                posts=body.get('posts',[])
                if not isinstance(posts,list) or len(posts)>100:
                    raise ValueError('Danh sách bài không hợp lệ.')
                normalized={}
                rejected=0
                for p in posts:
                    try:
                        pid,vid,url=canonical_facebook_video(p['post_url'])
                        if p.get('post_id')!=pid:
                            raise ValueError('ID không khớp.')
                        normalized[pid]=dict(post_id=pid,video_id=vid,post_url=url,channel_id=job['channel_id'],
                            caption=str(p.get('caption',''))[:12000],published_at=p.get('published_at'),
                            collected_at=p.get('collected_at'),likes=p.get('likes'),comments=p.get('comments'),shares=p.get('shares'),
                            direct_video_url='')
                    except (KeyError,ValueError,TypeError):
                        rejected+=1
                payload=dict(job_id=job_id,worker_id=job['worker_id'],channel_id=job['channel_id'],posts=list(normalized.values()),
                             partial=bool(body.get('partial') or rejected),error=str(body.get('error') or '')[:500])
                store.save_scan_result(payload)
                self._reply(200,{'ok':True,'saved':len(normalized),'rejected':rejected})
            except (ValueError,KeyError,TypeError) as exc:
                self._reply(400,{'ok':False,'error':str(exc)[:200]})

    return ThreadingHTTPServer(('127.0.0.1',int(config.get('port',8765))),Handler)

