import json
import contextlib
import sqlite3
import time
from pathlib import Path


class Store:
    def __init__(self, db_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS artifacts (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, action TEXT NOT NULL, payload TEXT NOT NULL,
                    created REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '');
            ''')

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, event_id, action, payload):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO outbox(id,action,payload,created) VALUES (?,?,?,?)',
                       (event_id, action, json.dumps(payload, ensure_ascii=False), time.time()))

    def pending(self):
        with self.connect() as db:
            return [dict(row, payload=json.loads(row['payload'])) for row in db.execute('SELECT * FROM outbox ORDER BY created')]

    def flush(self, client):
        sent = 0
        for event in self.pending():
            try:
                client.call(event['action'], **event['payload'])
            except Exception as exc:
                from shared.runtime import safe_error
                cfg = getattr(client, 'config', {})
                if not isinstance(cfg, dict):
                    cfg = {}
                if getattr(exc,'code','') in ('STALE_OWNER','STALE_JOB','STALE_WORKER','JOB_SUPERSEDED'):
                    # Keep full audit payload locally but don't block new jobs forever.
                    self.put_artifact('quarantine:'+event['id'],dict(event,error=safe_error(exc,cfg)))
                    with self.connect() as db:
                        db.execute('DELETE FROM outbox WHERE id=?',(event['id'],))
                    continue
                with self.connect() as db:
                    db.execute('UPDATE outbox SET attempts=attempts+1,error=? WHERE id=?', (safe_error(exc,cfg),event['id']))
                continue
            with self.connect() as db:
                db.execute('DELETE FROM outbox WHERE id=?', (event['id'],))
            sent += 1
        return sent

    def get_artifact(self, key):
        with self.connect() as db:
            row = db.execute('SELECT value FROM artifacts WHERE key=?', (key,)).fetchone()
            return json.loads(row['value']) if row else None

    def put_artifact(self, key, value):
        with self.connect() as db:
            db.execute('INSERT INTO artifacts(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                       (key, json.dumps(value, ensure_ascii=False, default=str)))

    def save_scan_result(self, payload):
        """Atomically save a browser result and queue its Sheet update before ACK."""
        event_id = 'scan:' + payload['job_id']
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO outbox(id,action,payload,created) VALUES (?,?,?,?)',
                       (event_id, 'complete_scan', json.dumps(payload, ensure_ascii=False), time.time()))
            db.execute('INSERT OR REPLACE INTO artifacts(key,value) VALUES (?,?)', ('scan_done:'+payload['job_id'], json.dumps({'done':True})))
            db.execute('DELETE FROM artifacts WHERE key=?', ('active_scan',))

    def update_active_scan(self, job_id, patch):
        """Compare/update under one write lock; never resurrect an acknowledged job."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT value FROM artifacts WHERE key=?',('active_scan',)).fetchone()
            current=json.loads(row['value']) if row else None
            if not current or current.get('job_id')!=job_id:
                return False
            current.update(patch)
            db.execute('UPDATE artifacts SET value=? WHERE key=?',(json.dumps(current,ensure_ascii=False),'active_scan'))
            return True

