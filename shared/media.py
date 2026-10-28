import json
import re
import shutil
import subprocess
from pathlib import Path


def ffmpeg_path(config=None):
    configured = (config or {}).get('ffmpeg_path')
    if configured:
        return str(configured)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        found = shutil.which('ffmpeg')
        if found:
            return found
        raise RuntimeError('Chưa cài FFmpeg/imageio-ffmpeg.') from None


def probe_media(path, config=None):
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError('File video không tồn tại hoặc rỗng.')
    probe = (config or {}).get('ffprobe_path') or shutil.which('ffprobe')
    if probe:
        proc = subprocess.run([str(probe), '-v','error','-show_format','-show_streams','-of','json',str(path)], capture_output=True, timeout=60)
        if proc.returncode:
            raise RuntimeError('FFprobe không đọc được file video.')
        data = json.loads(proc.stdout)
        stream = next((s for s in data.get('streams',[]) if s.get('codec_type') == 'video'), None)
        if not stream:
            raise RuntimeError('File không có luồng video.')
        return dict(duration=float(data.get('format',{}).get('duration', stream.get('duration',0))),
                    width=int(stream['width']),height=int(stream['height']),
                    has_audio=any(s.get('codec_type')=='audio' for s in data['streams']))
    proc = subprocess.run([ffmpeg_path(config),'-hide_banner','-i',str(path)], capture_output=True, timeout=60)
    info = proc.stderr.decode('utf-8', errors='replace')
    duration = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', info)
    video = re.search(r'Stream[^\n]*Video:[^\n]*?\b(\d{2,5})x(\d{2,5})\b', info)
    if not duration or not video:
        raise RuntimeError('FFmpeg không nhận diện được video/thời lượng.')
    h,m,s = duration.groups()
    return dict(duration=int(h)*3600+int(m)*60+float(s), width=int(video[1]),height=int(video[2]),has_audio=bool(re.search(r'Stream[^\n]*Audio:',info)))


def validate_video(path, config=None, expected_width=None, expected_height=None, expected_duration=None):
    info = probe_media(path, config)
    if info['duration'] <= 0:
        raise RuntimeError('Video không có thời lượng hợp lệ.')
    for key,value in [('width',expected_width),('height',expected_height)]:
        if value is not None and info[key] != value:
            raise RuntimeError(f'Video sai {key}: {info[key]} thay vì {value}.')
    if expected_duration is not None and abs(info['duration'] - expected_duration) > max(0.6, expected_duration*.02):
        raise RuntimeError('Video sai thời lượng dự kiến.')
    proc = subprocess.run([ffmpeg_path(config),'-v','error','-xerror','-i',str(path),'-map','0:v:0','-map','0:a?','-f','null','-'], capture_output=True, timeout=max(90,min(900,info['duration']*3)))
    if proc.returncode:
        raise RuntimeError('Video không giải mã được đầy đủ.')
    return info
