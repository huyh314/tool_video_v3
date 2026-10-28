"""Compatibility entry point; production uses tool2.py and approved snapshots."""
from pathlib import Path
import shutil
import uuid

from renderer.engine import render_script
from shared.config import load_config
from shared.media import ffmpeg_path


def get_ffmpeg_path():
    return ffmpeg_path(load_config())


def render_reels_video(hook_text, items_list, brand_signature="chú Dũng Sức", output_filename="reels_output.mp4"):
    config = load_config()
    work = Path(config["data_dir"]) / "renders" / ("legacy_" + uuid.uuid4().hex[:12])
    script = {"hook": hook_text, "items": items_list, "caption": "", "brand": brand_signature,
              "template": "auto", "duration_seconds": 0}
    result = render_script(script, config, work)
    destination = Path(output_filename)
    if not destination.is_absolute():
        destination = Path(config["data_dir"]) / "exports" / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(result["output_path"], destination)
    return str(destination.resolve())


if __name__ == "__main__":
    from tool2 import main
    raise SystemExit(main(["--demo"]))
