"""Render measured pages with local FFmpeg, then validate before publishing."""
from dataclasses import asdict
import json
import subprocess
from pathlib import Path

from PIL import Image

from renderer.layout import build_layout, write_overlays
from shared.media import ffmpeg_path, validate_video


def _run(command, timeout=120):
    result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace")[-1800:]
        raise RuntimeError(f"FFmpeg không hoàn tất (mã {result.returncode}): {detail}")


def choose_background_video(script: dict, config: dict, root: Path) -> Path:
    bg_dir = root / "assets" / "backgrounds"

    # 1. Script explicit request
    requested = script.get("bg_video") or script.get("background")
    if requested and requested not in ("auto", "Tự động", "random", "🎲 Tự động đổi nền"):
        req_path = Path(requested)
        if req_path.is_file():
            return req_path
        if bg_dir.is_dir():
            for f in sorted(bg_dir.glob("*.mp4")):
                if requested.lower() in f.name.lower():
                    return f

    # 1b. Check local preference file (if user chose a specific background in app)
    pref_file = root / "data" / "script_bg_preferences.json"
    if pref_file.is_file():
        try:
            prefs = json.loads(pref_file.read_text(encoding="utf-8"))
            sid = script.get("script_id")
            if sid and sid in prefs:
                target_bg = prefs[sid]
                cand = bg_dir / target_bg if not Path(target_bg).is_absolute() else Path(target_bg)
                if cand.is_file():
                    return cand
        except Exception:
            pass

    # 2. Config explicit request (non-default)
    cfg_bg = config.get("bg_video")
    if cfg_bg:
        cfg_path = Path(cfg_bg)
        if cfg_path.is_file() and cfg_path.name != "bg_underwater.mp4":
            return cfg_path

    # 3. Dynamic rotation from assets/backgrounds
    if bg_dir.is_dir():
        all_bgs = sorted([f for f in bg_dir.glob("*.mp4") if f.stat().st_size > 50000])
        if all_bgs:
            seed = str(script.get("script_id") or script.get("post_id") or "default_seed")
            import hashlib
            idx = int(hashlib.md5(seed.encode("utf-8")).hexdigest()[:8], 16) % len(all_bgs)
            return all_bgs[idx]

    # 4. Fallback
    fallback = root / "assets" / "bg_underwater.mp4"
    if fallback.is_file():
        return fallback
    if bg_dir.is_dir():
        first = next(bg_dir.glob("*.mp4"), None)
        if first:
            return first
    raise FileNotFoundError("Không tìm thấy video nền trong thư mục assets.")


def choose_background_music(script: dict, config: dict, root: Path) -> Path:
    """Select the best background music:
    1. Explicit script override ('bg_music' or 'music')
    2. Per-script saved preference from data/script_music_preferences.json
    3. Global config override ('music_file')
    4. Deterministic rotation across assets/music/
    5. Fallback to assets/bg_music_nocopyright.m4a
    """
    music_dir = root / "assets" / "music"
    requested = script.get("bg_music") or script.get("music") or ""

    # 1a. Direct script request
    if requested and requested not in ("auto", "Tự động", "random", "🎲 Tự động đổi nhạc"):
        req_path = Path(requested)
        if req_path.is_file():
            return req_path
        if music_dir.is_dir():
            for f in sorted(list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.m4a"))):
                if requested.lower() in f.name.lower():
                    return f

    # 1b. Check local preference file (if user chose a specific music in app)
    pref_file = root / "data" / "script_music_preferences.json"
    if pref_file.is_file():
        try:
            prefs = json.loads(pref_file.read_text(encoding="utf-8"))
            sid = script.get("script_id") or script.get("post_id")
            if sid and sid in prefs:
                target_music = prefs[sid]
                cand = music_dir / target_music if not Path(target_music).is_absolute() else Path(target_music)
                if cand.is_file():
                    return cand
        except Exception:
            pass

    # 2. Config explicit request (non-default)
    cfg_music = config.get("music_file")
    if cfg_music:
        cfg_path = Path(cfg_music)
        if cfg_path.is_file() and cfg_path.name != "bg_music_nocopyright.m4a":
            return cfg_path

    cfg_def_music = config.get("default_music")
    if cfg_def_music and cfg_def_music not in ("auto", "Tự động", "random", "🎲 Tự động đổi nhạc"):
        if music_dir.is_dir():
            for f in sorted(list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.m4a"))):
                if cfg_def_music.lower() in f.name.lower():
                    return f

    # 3. Dynamic deterministic rotation from assets/music/
    if music_dir.is_dir():
        all_tracks = sorted([f for f in list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.m4a")) if f.stat().st_size > 10000])
        if all_tracks:
            seed = str(script.get("script_id") or script.get("post_id") or "default_music_seed")
            idx = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % len(all_tracks)
            return all_tracks[idx]

    # 4. Fallback default
    fallback = root / "assets" / "bg_music_nocopyright.m4a"
    if fallback.is_file():
        return fallback

    raise FileNotFoundError("Không tìm thấy tệp nhạc nền nào trong assets/music/ hoặc assets/bg_music_nocopyright.m4a")


def render_script(script: dict, config: dict, output_dir: Path) -> dict:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    width = int(config.get("width", 720))
    height = int(config.get("height", 1280))
    layout = build_layout(script, width, height, config=config)
    root = Path(config.get("root_dir", Path(__file__).resolve().parents[1]))
    background = choose_background_video(script, config, root)
    music = choose_background_music(script, config, root)
    for path in (background, music):
        if not path.is_file():
            raise FileNotFoundError(f"Thiếu tài nguyên: {path}")
    executable = ffmpeg_path(config)
    overlays = write_overlays(layout, output_dir)
    (output_dir / "layout.json").write_text(json.dumps(asdict(layout), ensure_ascii=False, indent=2), encoding="utf-8")
    scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1"
    bg_frame = output_dir / "background_preview.png"
    _run([executable, "-hide_banner", "-loglevel", "error", "-y", "-i", str(background),
          "-vf", scale_filter, "-frames:v", "1", str(bg_frame)])
    with Image.open(bg_frame) as source:
        base = source.convert("RGBA")
    previews = []
    for index, overlay in enumerate(overlays, 1):
        with Image.open(overlay) as source:
            page = Image.alpha_composite(base, source.convert("RGBA")).convert("RGB")
        preview = output_dir / f"preview_{index:03d}.png"
        page.save(preview)
        previews.append(preview)
    thumb_w = 360
    thumb_h = round(height * thumb_w / width)
    columns = min(3, len(previews))
    rows = (len(previews) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_w, rows * thumb_h), "#081524")
    for index, path in enumerate(previews):
        with Image.open(path) as im:
            sheet.paste(im.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS),
                        ((index % columns) * thumb_w, (index // columns) * thumb_h))
    preview_path = output_dir / "preview.png"
    sheet.save(preview_path)
    segments = []
    for index, (overlay, duration) in enumerate(zip(overlays, layout.durations), 1):
        segment = output_dir / f"page_{index:03d}.mp4"
        filters = f"[0:v]{scale_filter},fps=30[bg];[bg][1:v]overlay=0:0:shortest=1,format=yuv420p[v]"
        _run([executable, "-hide_banner", "-loglevel", "error", "-y",
              "-stream_loop", "-1", "-i", str(background),
              "-loop", "1", "-framerate", "30", "-i", str(overlay),
              "-filter_complex", filters, "-map", "[v]", "-an",
              "-c:v", "libx264", "-preset", str(config.get("render_preset", "veryfast")),
              "-crf", "22", "-threads", "2", "-t", f"{duration:.3f}",
              "-pix_fmt", "yuv420p", str(segment)], timeout=max(120, duration * 25))
        segments.append(segment)
    concat_file = output_dir / "concat.txt"
    concat_file.write_text("\n".join(f"file '{p.name}'" for p in segments) + "\n", encoding="utf-8")
    partial = output_dir / "video.partial.mp4"
    volume = float(config.get("music_volume", 0.18))
    if not 0 <= volume <= 1:
        raise ValueError("Âm lượng nhạc phải nằm trong 0–1.")
    audio_filter = f"volume={volume},afade=t=in:st=0:d=0.5,afade=t=out:st={max(0, layout.duration - 1.5):.3f}:d=1.5"
    _run([executable, "-hide_banner", "-loglevel", "error", "-y",
          "-f", "concat", "-safe", "1", "-i", str(concat_file),
          "-stream_loop", "-1", "-i", str(music),
          "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-af", audio_filter,
          "-c:a", "aac", "-b:a", "192k", "-t", f"{layout.duration:.3f}",
          "-movflags", "+faststart", str(partial)], timeout=max(120, layout.duration * 10))
    checked = validate_video(partial, config, expected_width=width, expected_height=height,
                             expected_duration=layout.duration)
    if not checked.get("has_audio"):
        raise RuntimeError("Video thành phẩm không có âm thanh; chưa được đánh dấu hoàn thành.")
    output_path = output_dir / "video.mp4"
    partial.replace(output_path)
    return {"output_path": str(output_path), "preview_path": str(preview_path),
            "preview_pages": [str(p) for p in previews], "duration_seconds": layout.duration,
            "width": width, "height": height, "page_count": len(layout.pages), "status": "VALIDATED"}

