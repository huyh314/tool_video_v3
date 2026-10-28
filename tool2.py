"""Tool 2 — render approved Sheet scripts, or an explicitly labelled offline demo."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import socket
import time
import uuid

from renderer.engine import render_script
from renderer.worker import process_job
from shared.config import load_config
from shared.models import script_hash
from shared.runtime import instance_lock, safe_error
from shared.sheet import SheetClient
from shared.store import Store


def demo_script():
    return {"script_id": "demo_offline", "post_id": "demo", "version": 1,
            "hook": "MỖI NGÀY MỘT THAY ĐỔI NHỎ",
            "items": ["Chọn việc quan trọng — hoàn thành từng bước",
                      "Dành thời gian — lắng nghe người thân",
                      "Ghi nhận điều tốt — trân trọng hôm nay"],
            "caption": "Bản kiểm thử cục bộ, không lấy từ Facebook và không gửi lên Sheet.",
            "brand": "BẢN XEM THỬ", "template": "auto", "duration_seconds": 0}


def run_once(config, client, store, worker_id):
    store.flush(client)
    pending = [event for event in store.pending() if event["action"] in ("complete_render", "fail_render")]
    if pending:
        print(f"Còn {len(pending)} kết quả dựng đang chờ đồng bộ; giữ nguyên file và thử lại kết nối.")
        return None
    reply = client.call("claim_render", worker_id=worker_id, lease_seconds=900)
    job = reply.get("job")
    if not job:
        print("Chưa có kịch bản đã duyệt cần dựng.")
        return False
    job["worker_id"] = worker_id
    try:
        result = process_job(config, client, store, job)
    except Exception as error:
        message = safe_error(error, config)
        store.enqueue("fail_render:" + job["job_id"], "fail_render",
                      {"job_id": job["job_id"], "worker_id": worker_id,
                       "script_id": job["script"]["script_id"], "error": message})
        print("Lỗi dựng video: " + message)
        store.flush(client)
        return True
    print("Đã kiểm tra video: " + result["output_path"])
    store.flush(client)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tool 2: tạo video từ kịch bản đã duyệt trên Sheet.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--once", action="store_true", help="Xử lý hết các job đã duyệt hiện có rồi thoát")
    modes.add_argument("--watch", action="store_true", help="Tiếp tục chờ các job mới")
    modes.add_argument("--demo", action="store_true", help="Dựng bản thử cục bộ; không gọi Sheet/Gemini")
    parser.add_argument("--duration", type=int, default=0, help="Thời lượng demo, 0 = tự tính đủ đọc")
    parser.add_argument("--resolution", type=int, choices=[720, 1080], help="Chiều rộng video 9:16")
    args = parser.parse_args(argv)
    config = load_config()
    if args.resolution:
        config.update(width=args.resolution, height=args.resolution * 16 // 9)
    try:
        with instance_lock(config["data_dir"], "renderer"):
            if args.demo:
                script = demo_script()
                script["duration_seconds"] = args.duration
                directory = Path(config["data_dir"]) / "renders" / ("demo_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
                result = render_script(script, config, directory)
                result.update(script_id=script["script_id"], content_hash=script_hash(script), demo=True)
                (directory / "render.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                print("DEMO CỤC BỘ — " + result["output_path"])
                print("Ảnh xem trước: " + result["preview_path"])
                return 0
            client = SheetClient(config)
            if not client.configured:
                raise RuntimeError("Chưa cấu hình Web App và mã xác thực Sheet. Chạy thiết lập trước.")
            from tool1 import check_protocol
            check_protocol(client,config)
            store = Store(Path(config["data_dir"]) / "state.sqlite3")
            worker_id = "renderer_" + socket.gethostname() + "_" + uuid.uuid4().hex[:10]
            print("🟢 TOOL 2 ĐANG CHẠY VÀ CHỜ KỊCH BẢN ĐÃ DUYỆT TỪ GOOGLE SHEET...", flush=True)
            while True:
                try:
                    worked = run_once(config, client, store, worker_id)
                    if worked is None and not args.watch:
                        return 1
                    if not args.watch and not worked:
                        break
                except Exception as error:
                    print("Chờ kết nối/đồng bộ: " + safe_error(error, config))
                    if not args.watch:
                        return 1
                    worked = False
                if not worked:
                    time.sleep(max(5, int(config.get("poll_seconds", 30))))
            return 0
    except KeyboardInterrupt:
        print("Đã dừng. Kết quả đã lưu sẽ được đồng bộ khi chạy lại.")
        return 130
    except Exception as error:
        print("Không thể chạy tool 2: " + safe_error(error, config))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
