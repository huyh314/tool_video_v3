"""
Facebook Fanpage Reels & Video Publishing Bridge
Hỗ trợ đăng ngay hoặc hẹn giờ đăng bài (Scheduled Publishing) lên Fanpage bằng Facebook Graph API chính thức.
"""

import datetime
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


GRAPH_API_VERSION = "v19.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def check_token_info(token: str) -> dict:
    """Kiểm tra token người dùng hoặc token Page:
    - Lấy thông tin tài khoản (ID, Tên)
    - Lấy danh sách các Fanpage quản trị (ID, Tên, Category, Page Token)
    - Kiểm tra các quyền đã được cấp và các quyền còn thiếu.
    """
    token = token.strip()
    if not token:
        return {"ok": False, "error": "Token rỗng"}

    # 1. Query /me
    user_info = {}
    try:
        url_me = f"{GRAPH_URL}/me?fields=id,name&access_token={token}"
        req = urllib.request.Request(url_me, headers={"User-Agent": "FBAutoStudio/3.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            user_info = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"Không thể xác thực token với Facebook: {exc}"}

    # 2. Query /me/permissions
    granted_perms = []
    try:
        url_perms = f"{GRAPH_URL}/me/permissions?access_token={token}"
        req = urllib.request.Request(url_perms, headers={"User-Agent": "FBAutoStudio/3.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            p_data = json.loads(r.read().decode("utf-8"))
            for p in p_data.get("data", []):
                if p.get("status") == "granted":
                    granted_perms.append(p.get("permission"))
    except Exception:
        pass

    # 3. Query /me/accounts (Fanpages)
    pages = []
    try:
        url_acc = f"{GRAPH_URL}/me/accounts?fields=id,name,category,access_token,tasks&limit=50&access_token={token}"
        req = urllib.request.Request(url_acc, headers={"User-Agent": "FBAutoStudio/3.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            acc_data = json.loads(r.read().decode("utf-8"))
            for p in acc_data.get("data", []):
                pages.append({
                    "id": str(p.get("id")),
                    "name": p.get("name"),
                    "category": p.get("category", ""),
                    "page_token": p.get("access_token", ""),
                    "tasks": p.get("tasks", [])
                })
    except Exception as exc:
        # Nếu token truyền vào vốn là Page Access Token trực tiếp
        pass

    # Kiểm tra quyền đăng bài
    required_perms = ["pages_manage_posts", "publish_video"]
    missing_perms = [perm for perm in required_perms if perm not in granted_perms]
    can_publish = (len(missing_perms) == 0)

    return {
        "ok": True,
        "user_id": user_info.get("id", ""),
        "user_name": user_info.get("name", ""),
        "pages": pages,
        "granted_perms": granted_perms,
        "missing_perms": missing_perms,
        "can_publish": can_publish
    }


def publish_reel_to_page(
    page_id: str,
    page_token: str,
    video_path: str | Path,
    caption: str = "",
    scheduled_timestamp: int | None = None
) -> dict:
    """Tải và đăng Facebook Reel lên Fanpage qua Meta Reels Publishing API:
    - Nếu scheduled_timestamp được truyền vào: Hẹn giờ đăng (scheduled_publish_time).
      Lưu ý: Facebook quy định hẹn giờ từ 10 phút đến 75 ngày trong tương lai.
    - Nếu scheduled_timestamp = None: Đăng ngay lập tức (PUBLISHED).
    """
    video_file = Path(video_path).resolve()
    if not video_file.is_file():
        return {"ok": False, "error": f"Không tìm thấy tệp video: {video_file}"}

    file_size = video_file.stat().st_size
    if file_size < 1000:
        return {"ok": False, "error": "Tệp video quá nhỏ hoặc bị lỗi."}

    # BƯỚC 1: Khởi tạo phiên upload Reel (upload_phase = start)
    start_data = urllib.parse.urlencode({
        "upload_phase": "start",
        "access_token": page_token
    }).encode("utf-8")

    start_url = f"{GRAPH_URL}/{page_id}/video_reels"
    try:
        req = urllib.request.Request(start_url, data=start_data, headers={"User-Agent": "FBAutoStudio/3.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            start_res = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"Lỗi khởi tạo upload Reel (HTTP {exc.code}): {err_msg}"}
    except Exception as exc:
        return {"ok": False, "error": f"Không thể kết nối Facebook: {exc}"}

    video_id = start_res.get("video_id")
    upload_url = start_res.get("upload_url")
    if not video_id or not upload_url:
        return {"ok": False, "error": f"Facebook không trả về video_id hoặc upload_url: {start_res}"}

    # BƯỚC 2: Tải dữ liệu video lên máy chủ Facebook (Binary upload)
    try:
        with open(video_file, "rb") as f:
            video_bytes = f.read()

        req_upload = urllib.request.Request(
            upload_url,
            data=video_bytes,
            headers={
                "Authorization": f"OAuth {page_token}",
                "offset": "0",
                "file_size": str(file_size),
                "Content-Type": "application/octet-stream",
                "User-Agent": "FBAutoStudio/3.0"
            }
        )
        with urllib.request.urlopen(req_upload, timeout=120) as r:
            upload_res = json.loads(r.read().decode("utf-8"))
            if not upload_res.get("success"):
                return {"ok": False, "error": f"Upload video không thành công: {upload_res}"}
    except Exception as exc:
        return {"ok": False, "error": f"Lỗi khi truyền tải tệp video lên Facebook: {exc}"}

    # BƯỚC 3: Hoàn tất & Đăng bài / Hẹn giờ (upload_phase = finish)
    finish_params = {
        "upload_phase": "finish",
        "access_token": page_token,
        "video_id": video_id,
        "description": caption.strip()
    }

    if scheduled_timestamp:
        # Hẹn giờ đăng
        finish_params["video_state"] = "SCHEDULED"
        finish_params["scheduled_publish_time"] = str(int(scheduled_timestamp))
    else:
        # Đăng ngay
        finish_params["video_state"] = "PUBLISHED"

    finish_data = urllib.parse.urlencode(finish_params).encode("utf-8")
    try:
        req_finish = urllib.request.Request(start_url, data=finish_data, headers={"User-Agent": "FBAutoStudio/3.0"})
        with urllib.request.urlopen(req_finish, timeout=30) as r:
            finish_res = json.loads(r.read().decode("utf-8"))
            if finish_res.get("success"):
                return {
                    "ok": True,
                    "video_id": video_id,
                    "page_id": page_id,
                    "is_scheduled": bool(scheduled_timestamp),
                    "scheduled_timestamp": scheduled_timestamp,
                    "result": finish_res
                }
            else:
                return {"ok": False, "error": f"Lỗi khi xác nhận hoàn tất: {finish_res}"}
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"Lỗi hoàn tất đăng Reel (HTTP {exc.code}): {err_msg}"}
    except Exception as exc:
        return {"ok": False, "error": f"Lỗi không xác định khi hoàn tất: {exc}"}
