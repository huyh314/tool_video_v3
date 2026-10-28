import contextlib
import re
import threading
from pathlib import Path


def safe_error(exc, config=None):
    text = str(exc)
    for key in ('gemini_api_key', 'sheet_token', 'local_api_token'):
        secret = (config or {}).get(key)
        if secret:
            text = text.replace(str(secret), '[REDACTED]')
    text = re.sub(r'(?i)(key|token|authorization)=([^&\s]+)', r'\1=[REDACTED]', text)
    text = re.sub(r'https://[^\s]+', '[URL]', text)
    return text[:700]


@contextlib.contextmanager
def instance_lock(data_dir, name):
    path = Path(data_dir) / (name + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    file = path.open('a+b')
    file.seek(0)
    file.write(b'0')
    file.flush()
    file.seek(0)
    try:
        if __import__('os').name == 'nt':
            import msvcrt
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        file.close()
        raise RuntimeError(f'{name} đang chạy ở cửa sổ khác.') from None
    try:
        yield
    finally:
        file.close()


class LeaseHeartbeat:
    def __init__(self, client, job, seconds=900):
        self.client, self.job, self.seconds = client, job, seconds
        self.stop = threading.Event()
        self.error = None

    def _run(self):
        while not self.stop.wait(min(60, self.seconds / 3)):
            try:
                self.client.call('renew_lease', job_id=self.job['job_id'], worker_id=self.job['worker_id'], lease_seconds=self.seconds)
            except Exception as exc:
                self.error = exc
                return

    def __enter__(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self

    def check(self):
        if self.error:
            raise RuntimeError('Không xác nhận được quyền giữ công việc: ' + str(self.error))

    def __exit__(self, exc_type, exc, tb):
        self.stop.set()
        self.thread.join(timeout=2)
        if not exc_type:
            self.check()

