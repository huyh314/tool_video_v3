import json
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_config(root=None):
    root = Path(root or ROOT).resolve()
    cfg = dict(webhook_url='', spreadsheet_id='', default_signature='chú Dũng Sức',
               gemini_model='auto', poll_seconds=30, width=720, height=1280,
               max_video_mb=150, max_video_seconds=600, port=8765,
               ffmpeg_path='', ffprobe_path='', auto_analyze=True,
               max_analysis_per_day=30, download_timeout=180, gemini_timeout=180,
               cookies_browser='', data_dir='data',
               font_size_mode='auto', color_theme='gold',
               hook_color='', item_color='',
               default_music='auto', music_volume=0.18)
    config_file = root / 'config.json'
    if config_file.exists():
        cfg.update(json.loads(config_file.read_text(encoding='utf-8-sig')))
    private = root / '.local'
    private.mkdir(exist_ok=True)
    secret_file = private / 'secrets.json'
    stored = json.loads(secret_file.read_text(encoding='utf-8-sig')) if secret_file.exists() else {}
    changed = False
    for key in ('sheet_token', 'local_api_token'):
        if not stored.get(key):
            stored[key] = secrets.token_urlsafe(32)
            changed = True
    if changed:
        tmp = secret_file.with_suffix('.tmp')
        tmp.write_text(json.dumps(stored, indent=2), encoding='utf-8')
        tmp.replace(secret_file)
    cfg.update(stored)
    key_file = private / 'gemini.key'
    if key_file.exists():
        cfg['gemini_api_key'] = key_file.read_text(encoding='utf-8').strip()
    cfg['gemini_api_key'] = os.environ.get('GEMINI_API_KEY', cfg.get('gemini_api_key', ''))
    cfg['root_dir'] = root
    data = Path(cfg['data_dir'])
    cfg['data_dir'] = (data if data.is_absolute() else root / data).resolve()
    cfg['data_dir'].mkdir(parents=True, exist_ok=True)
    for key, default in [('bg_video', 'assets/bg_underwater.mp4'), ('music_file', 'assets/bg_music_nocopyright.m4a')]:
        path = Path(cfg.get(key) or default)
        cfg[key] = path if path.is_absolute() else root / path
    cfg['port'] = 8765
    return cfg


def save_config(updates: dict, root=None):
    root = Path(root or ROOT).resolve()
    config_file = root / 'config.json'
    cfg = {}
    if config_file.exists():
        try:
            cfg = json.loads(config_file.read_text(encoding='utf-8-sig'))
        except Exception:
            cfg = {}
    cfg.update(updates)
    config_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    return cfg


