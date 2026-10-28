"""Render an immutable approved snapshot and durably enqueue its completion."""
from datetime import datetime, timezone
import json
from pathlib import Path

from renderer.engine import render_script
from shared.media import validate_video
from shared.models import safe_id, script_hash, validate_script
from shared.runtime import LeaseHeartbeat


def _atomic_json(path: Path, value: dict):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _valid_cache(cached, job, config):
    if not isinstance(cached, dict) or cached.get("content_hash") != job["content_hash"]:
        return False
    if cached.get("script_id") != job["script"]["script_id"]:
        return False
    if int(cached.get("version", 0)) != int(job["script"].get("version", 1)):
        return False
    try:
        check = validate_video(Path(cached["output_path"]), config,
                               expected_width=cached["width"], expected_height=cached["height"],
                               expected_duration=cached["duration_seconds"])
        return bool(check.get("has_audio")) and Path(cached["preview_path"]).is_file()
    except (KeyError, OSError, ValueError, RuntimeError):
        return False


def process_job(config, client, store, job):
    original = job["script"]
    script = {**original, **validate_script(original)}
    digest = script_hash(script)
    if digest != job.get("content_hash") or digest != original.get("approved_hash"):
        raise ValueError("Kịch bản thay đổi so với phiên bản đã duyệt; cần duyệt lại.")
    render_id = job["render_id"]
    directory = Path(config["data_dir"]) / "renders" / safe_id(render_id)
    directory.mkdir(parents=True, exist_ok=True)
    key = "render:" + render_id
    manifest = directory / "render.json"
    cached = store.get_artifact(key)
    if not cached and manifest.is_file():
        try:
            cached = json.loads(manifest.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            cached = None
    with LeaseHeartbeat(client, job, seconds=900):
        if _valid_cache(cached, job, config):
            result = cached
        else:
            snapshot = {"script": script, "content_hash": digest,
                        "render_id": render_id, "captured_at": datetime.now(timezone.utc).isoformat(),
                        "settings": {name: str(config[name]) for name in
                                     ("width", "height", "bg_video", "music_file", "music_volume", "render_preset") if name in config}}
            _atomic_json(directory / "snapshot.json", snapshot)
            result = render_script(script, config, directory)
            result.update(render_id=render_id, script_id=script["script_id"],
                          version=int(script.get("version", 1)), content_hash=digest,
                          created_at=datetime.now(timezone.utc).isoformat())
            _atomic_json(manifest, result)
            store.put_artifact(key, result)
    payload = {"job_id": job["job_id"], "worker_id": job["worker_id"], "render": result}
    store.enqueue("complete_render:" + job["job_id"], "complete_render", payload)
    return result

