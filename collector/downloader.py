import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

from shared.media import validate_video
from shared.models import canonical_facebook_video, safe_id


def _check_limits(path, info, config):
    if info['duration']>int(config.get('max_video_seconds',600)) or path.stat().st_size>int(config.get('max_video_mb',150))*1024*1024:
        raise RuntimeError('Video vượt giới hạn phân tích; giảm độ dài/kích thước hoặc chỉnh cấu hình.')


def download_video(post, config):
    post_id, video_id, url = canonical_facebook_video(post['post_url'])
    if post_id != post['post_id']:
        raise ValueError('ID video không khớp ID bài; dừng để tránh tải nhầm.')
    directory = Path(config['data_dir'])/'raw'/safe_id(post.get('channel_id','manual'))/safe_id(post_id)
    directory.mkdir(parents=True,exist_ok=True)
    existing = directory/'source.mp4'
    manifest = directory/'download.json'
    if existing.exists() and manifest.exists():
        try:
            meta = json.loads(manifest.read_text(encoding='utf-8'))
            valid = meta.get('video_id') == video_id and meta.get('sha256') == hashlib.sha256(existing.read_bytes()).hexdigest()
            info = validate_video(existing,config) if valid else None
        except (ValueError, OSError, RuntimeError):
            info = None
        if info:
            _check_limits(existing,info,config)
            return existing
    # A new attempt can never be mistaken by yt-dlp for a completed corrupt file.
    attempt_dir = directory/('attempt_'+uuid.uuid4().hex[:12])
    attempt_dir.mkdir()
    command = [sys.executable,'-m','yt_dlp','--no-playlist','--no-progress','--no-warnings',
               '--socket-timeout','25','--retries','2','--fragment-retries','2',
               '--max-filesize',f"{int(config.get('max_video_mb',150))}M",
               '-f','best[ext=mp4]/best','--write-info-json','-o',str(attempt_dir/'source.%(ext)s'),url]
    browser = config.get('cookies_browser','')
    if browser:
        if browser not in ('chrome','edge','firefox'):
            raise ValueError('cookies_browser chỉ hỗ trợ chrome/edge/firefox.')
        command[3:3] = ['--cookies-from-browser',browser]
    try:
        result = subprocess.run(command,capture_output=True,timeout=int(config.get('download_timeout',180)))
    except subprocess.TimeoutExpired:
        raise RuntimeError('Tải video quá thời gian; có thể thử lại công đoạn tải.') from None
    if result.returncode:
        # yt-dlp stderr can include URLs/session details. Keep error actionable, not raw.
        raise RuntimeError('Không tải được video Facebook. Kiểm tra video công khai/phiên đăng nhập; có thể cấu hình cookies_browser nếu cần.')
    info_file = attempt_dir/'source.info.json'
    if not info_file.exists():
        raise RuntimeError('Thiếu thông tin ID của video tải về.')
    metadata = json.loads(info_file.read_text(encoding='utf-8'))
    if str(metadata.get('id')) != video_id:
        raise RuntimeError('Video tải về không khớp ID nguồn; không phân tích file này.')
    ext = metadata.get('ext','mp4')
    if ext != 'mp4':
        raise RuntimeError('Video tải về không phải MP4; cần chuyển định dạng trước khi phân tích.')
    downloaded = attempt_dir/'source.mp4'
    info = validate_video(downloaded,config)
    _check_limits(downloaded,info,config)
    downloaded.replace(existing)
    tmp = manifest.with_suffix('.tmp')
    tmp.write_text(json.dumps(dict(video_id=video_id,sha256=hashlib.sha256(existing.read_bytes()).hexdigest(),**info),ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(manifest)
    return existing


