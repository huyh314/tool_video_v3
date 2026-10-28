import hashlib
import json
import re
from urllib.parse import urlparse, parse_qs


def safe_id(value):
    value = str(value)
    clean = re.sub(r'[^a-zA-Z0-9_-]', '_', value)[:100]
    if not clean or clean != value:
        clean = clean + '_' + hashlib.sha256(value.encode()).hexdigest()[:12]
    return clean


def canonical_facebook_video(url):
    parsed = urlparse(str(url))
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or not (host == 'facebook.com' or host.endswith('.facebook.com')):
        raise ValueError('Chỉ nhận URL HTTPS của Facebook.')
    match = re.search(r'/(?:reel|videos)/(?:[^/?]+/)?(\d+)(?:/|$)', parsed.path)
    query = parse_qs(parsed.query)
    video_id = match.group(1) if match else (query.get('v',[''])[0] if parsed.path.rstrip('/') in ('/watch','/video.php') else '')
    if not re.fullmatch(r'\d+', video_id):
        raise ValueError('Không xác định được ID video từ URL.')
    canonical = f'https://www.facebook.com/reel/{video_id}/' if '/reel/' in parsed.path else f'https://www.facebook.com/watch/?v={video_id}'
    return f'fb_{video_id}', video_id, canonical


def normalized_content(script):
    items = script.get('items', [])
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except ValueError:
            items = [s for s in items.splitlines() if s.strip()]
    if not isinstance(items, list) or any(not isinstance(x, str) for x in items):
        raise ValueError('Các ý kịch bản phải là danh sách văn bản.')
    duration = script.get('duration_seconds', 0) or 0
    if isinstance(duration, bool) or float(duration) != int(float(duration)):
        raise ValueError('Thời lượng phải là số giây nguyên.')
    return [str(script.get('hook', '')).strip(), [s.strip() for s in items],
            str(script.get('caption', '')).strip(), str(script.get('brand', '')).strip(),
            str(script.get('template', 'auto') or 'auto').strip(), int(float(duration))]


def script_hash(script):
    text = json.dumps(normalized_content(script), ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def validate_script(script):
    hook, items, caption, brand, template, duration = normalized_content(script)
    if not hook or len(hook) > 240:
        raise ValueError('Hook phải có 1–240 ký tự.')
    if not 1 <= len(items) <= 20 or any(not s or len(s) > 500 for s in items):
        raise ValueError('Cần 1–20 ý, mỗi ý có 1–500 ký tự.')
    if len(set(x.casefold() for x in items)) != len(items):
        raise ValueError('Kịch bản có ý trùng nhau.')
    if template not in ('auto', 'list', 'pages') or not 0 <= duration <= 600:
        raise ValueError('Mẫu hoặc thời lượng video không hợp lệ.')
    if len(brand) > 100 or len(caption) > 5000:
        raise ValueError('Thương hiệu/caption vượt giới hạn.')
    return dict(script, hook=hook, items=items, caption=caption, brand=brand,
                template=template, duration_seconds=duration)

