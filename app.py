"""
FB Auto Video Studio Pro v3 — Ứng dụng điều khiển trung tâm Desktop (Giao diện tinh gọn chuẩn chức năng)

Quy trình 3 bước cốt lõi:
1. BẬT TỰ ĐỘNG: Quét bài Facebook ➜ Gemini AI trích xuất & viết kịch bản 9:16
2. KIỂM DUYỆT & SỬA KỊCH BẢN: Đọc kịch bản, sửa trực tiếp chữ trên App ➜ Bấm Duyệt (APPROVED)
3. KHO VIDEO THÀNH PHẨM: Nhận video 9:16 hoàn chỉnh ➜ Xem video ngay & Sao chép caption dán đăng bài
"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter.colorchooser as colorchooser
import webbrowser

import customtkinter as ctk

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from shared.config import load_config, save_config
from shared.models import script_hash
from renderer.layout import THEMES

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ProcessRunner:
    def __init__(self, name, command, log_queue, tag="SYS"):
        self.name = name
        self.command = command
        self.log_queue = log_queue
        self.tag = tag
        self.process = None
        self.thread = None
        self.running = False

    def start(self):
        if self.running and self.process and self.process.poll() is None:
            return True
        try:
            creation_flags = 0x08000000 if sys.platform == "win32" else 0
            self.process = subprocess.Popen(
                self.command,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creation_flags
            )
            self.running = True
            self.thread = threading.Thread(target=self._reader, daemon=True)
            self.thread.start()
            self.log_queue.put((self.tag, f"🟢 Khởi động {self.name} thành công."))
            return True
        except Exception as exc:
            self.log_queue.put(("ERR", f"❌ Lỗi khi khởi động {self.name}: {exc}"))
            self.running = False
            return False

    def _reader(self):
        while self.running and self.process:
            line = self.process.stdout.readline()
            if not line:
                break
            line_str = line.strip()
            if line_str:
                self.log_queue.put((self.tag, line_str))
        self.running = False

    def stop(self):
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
            self.log_queue.put((self.tag, f"⏹ Đã dừng {self.name}."))


class SheetBridge:
    def __init__(self, config):
        self.config = config
        self.token_file = ROOT / "token.json"
        self.spreadsheet_id = config.get("spreadsheet_id", "")
        self._client = None
        self._spreadsheet = None

    def get_spreadsheet(self):
        if self._spreadsheet:
            return self._spreadsheet
        if not self.token_file.exists():
            return None
        import gspread
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(str(self.token_file))
        self._client = gspread.authorize(creds)
        self._spreadsheet = self._client.open_by_key(self.spreadsheet_id)
        return self._spreadsheet

    def fetch_stats(self):
        try:
            ss = self.get_spreadsheet()
            if not ss:
                return {"posts": 0, "pending_scripts": 0, "renders": 0}
            ws_p = ss.worksheet("V3 · Bài và video gốc")
            ws_s = ss.worksheet("V3 · Kịch bản")
            ws_v = ss.worksheet("V3 · Video thành phẩm")

            p_rows = ws_p.get_all_values()
            s_rows = ws_s.get_all_values()
            v_rows = ws_v.get_all_values()

            posts_cnt = max(0, len(p_rows) - 1)

            # Count scripts waiting for human approval
            pending_cnt = 0
            if len(s_rows) > 1:
                headers = s_rows[0]
                status_idx = headers.index("Trạng thái duyệt") if "Trạng thái duyệt" in headers else 9
                for r in s_rows[1:]:
                    if len(r) > status_idx and r[status_idx].strip() == "READY_FOR_REVIEW":
                        pending_cnt += 1

            # Count completed video renders
            renders_cnt = 0
            if len(v_rows) > 1:
                headers = v_rows[0]
                st_idx = headers.index("Trạng thái dựng") if "Trạng thái dựng" in headers else 4
                for r in v_rows[1:]:
                    if len(r) > st_idx and r[st_idx].strip() == "DONE":
                        renders_cnt += 1
            if renders_cnt == 0:
                renders_dir = ROOT / "data" / "renders"
                if renders_dir.exists():
                    renders_cnt = len([d for d in renders_dir.iterdir() if d.is_dir() and (d / "video.mp4").exists()])

            return {
                "posts": posts_cnt,
                "pending_scripts": pending_cnt,
                "renders": renders_cnt
            }
        except Exception:
            return {"posts": 0, "pending_scripts": 0, "renders": 0}

    def fetch_channels(self):
        try:
            ss = self.get_spreadsheet()
            if not ss:
                return []
            ws_c = ss.worksheet("V3 · Kênh theo dõi")
            rows = ws_c.get_all_values()
            if len(rows) < 2:
                return []
            channels = []
            for idx, r in enumerate(rows[1:], start=2):
                if any(r):
                    channels.append({
                        "row": idx,
                        "id": r[0].strip().replace("'", "") if len(r) > 0 else str(idx - 1),
                        "name": r[1].strip() if len(r) > 1 else f"Kênh #{idx - 1}",
                        "url": r[2].strip() if len(r) > 2 else "",
                        "enabled": r[3].strip().upper() == "TRUE" if len(r) > 3 else True,
                        "max_posts": r[6].strip() if len(r) > 6 else "5",
                        "status": r[9].strip() if len(r) > 9 else "Sẵn sàng",
                        "error": r[10].strip() if len(r) > 10 else "",
                        "cmd": r[11].strip() if len(r) > 11 else ""
                    })
            return channels
        except Exception:
            return []

    def add_channel(self, name, url, signature="Chú Dũng Sức Khỏe", max_posts="5"):
        try:
            ss = self.get_spreadsheet()
            if not ss:
                return False, "Không kết nối được Google Sheet."
            ws_c = ss.worksheet("V3 · Kênh theo dõi")
            rows = ws_c.get_all_values()
            existing_ids = []
            for r in rows[1:]:
                if r and r[0].strip().replace("'", "").isdigit():
                    existing_ids.append(int(r[0].strip().replace("'", "")))
            next_id = max(existing_ids + [0]) + 1

            new_row = [
                f"'{next_id}'",
                name.strip(),
                url.strip(),
                "TRUE",
                "720",
                "7",
                str(max_posts),
                signature.strip(),
                "",
                "Sẵn sàng",
                "",
                "",
                ""
            ]
            ws_c.append_row(new_row, value_input_option="USER_ENTERED")
            return True, f"Đã thêm kênh #{next_id}: {name}"
        except Exception as exc:
            return False, f"Lỗi khi thêm kênh: {exc}"

    def delete_channel(self, row_idx):
        try:
            ss = self.get_spreadsheet()
            if not ss:
                return False, "Không kết nối được Google Sheet."
            ws_c = ss.worksheet("V3 · Kênh theo dõi")
            ws_c.delete_rows(row_idx)
            return True, "Đã xóa kênh khỏi Google Sheet."
        except Exception as exc:
            return False, f"Lỗi khi xóa kênh: {exc}"

    def trigger_scan_channels(self, selected_rows, max_posts="5"):
        try:
            ss = self.get_spreadsheet()
            if not ss:
                return False, "Không kết nối được Google Sheet."
            ws_c = ss.worksheet("V3 · Kênh theo dõi")
            for r in selected_rows:
                ws_c.update_acell(f"G{r}", str(max_posts))
                ws_c.update_acell(f"J{r}", "Sẵn sàng")
                ws_c.update_acell(f"K{r}", "")
                ws_c.update_acell(f"L{r}", "SCAN")
                ws_c.update_acell(f"M{r}", "")
            return True, f"Đã kích hoạt quét {len(selected_rows)} kênh."
        except Exception as exc:
            return False, f"Lỗi khi gửi lệnh quét: {exc}"

    def fetch_scripts(self):
        try:
            ss = self.get_spreadsheet()
            if not ss:
                return []
            ws_s = ss.worksheet("V3 · Kịch bản")
            s_rows = ws_s.get_all_values()
            if len(s_rows) < 2:
                return []
            s_headers = s_rows[0]

            # Get raw post captions, extractions and links for comparison
            posts_map = {}
            extractions_map = {}
            post_urls_map = {}
            try:
                ws_p = ss.worksheet("V3 · Bài và video gốc")
                p_rows = ws_p.get_all_values()
                if len(p_rows) > 1:
                    p_headers = p_rows[0]
                    pid_idx = p_headers.index("Mã bài") if "Mã bài" in p_headers else 0
                    cap_idx = p_headers.index("Caption gốc") if "Caption gốc" in p_headers else 4
                    ext_idx = p_headers.index("Nội dung trích xuất (JSON)") if "Nội dung trích xuất (JSON)" in p_headers else 12
                    url_idx = p_headers.index("Link video gốc") if "Link video gốc" in p_headers else 2
                    for r in p_rows[1:]:
                        if len(r) > pid_idx:
                            pid = r[pid_idx].strip()
                            posts_map[pid] = r[cap_idx] if len(r) > cap_idx else ""
                            extractions_map[pid] = r[ext_idx] if len(r) > ext_idx else ""
                            post_urls_map[pid] = r[url_idx] if len(r) > url_idx else ""
            except Exception:
                pass

            renders_dir = ROOT / "data" / "renders"

            scripts = []
            for idx, r in enumerate(s_rows[1:], start=2):
                if not any(r):
                    continue
                d = {s_headers[i]: r[i] if i < len(r) else "" for i in range(len(s_headers))}
                d["__row"] = idx
                source_id = d.get("Mã bài nguồn", "")
                d["__source_caption"] = posts_map.get(source_id, "")
                d["__source_extraction"] = extractions_map.get(source_id, "")
                d["__source_url"] = post_urls_map.get(source_id, "")

                # Check if matching rendered video exists
                sid = d.get("Mã kịch bản", "")
                matching_video = None
                if renders_dir.exists():
                    for sub in renders_dir.iterdir():
                        if sub.is_dir() and (sid in sub.name or (source_id and source_id in sub.name)):
                            vp = sub / "video.mp4"
                            if vp.exists():
                                matching_video = str(vp)
                                break
                d["__has_video"] = bool(matching_video)
                d["__video_path"] = matching_video

                scripts.append(d)
            return list(reversed(scripts))
        except Exception:
            return []

    def fetch_raw_posts(self):
        try:
            ss = self.get_spreadsheet()
            if not ss:
                return []
            ws_p = ss.worksheet("V3 · Bài và video gốc")
            p_rows = ws_p.get_all_values()
            if len(p_rows) < 2:
                return []
            headers = p_rows[0]
            posts = []
            for idx, r in enumerate(p_rows[1:], start=2):
                if not any(r):
                    continue
                d = {headers[i]: r[i] if i < len(r) else "" for i in range(len(headers))}
                d["__row"] = idx
                dl_path = d.get("File video trên máy", "")
                d["__has_video"] = bool(dl_path and Path(dl_path).exists())
                posts.append(d)
            return list(reversed(posts))
        except Exception:
            return []

    def approve_script_with_edits(self, row_idx, script_dict):
        try:
            ss = self.get_spreadsheet()
            if not ss:
                return False
            ws = ss.worksheet("V3 · Kịch bản")
            h = script_hash(script_dict)
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            items = script_dict.get("items", [])
            items_str = "\n".join(items) if isinstance(items, list) else str(items)

            # Columns D to O:
            # D: HOOK, E: Các ý, F: Caption mới, G: Thương hiệu đầu ra, H: Mẫu, I: Thời lượng,
            # J: Trạng thái duyệt, K: Mã nội dung đã duyệt, L: Trạng thái dựng, M: Lỗi, N: Lệnh, O: Thời điểm duyệt
            row_values = [
                script_dict.get("hook", "").strip(),
                items_str.strip(),
                script_dict.get("caption", "").strip(),
                script_dict.get("brand", "Chú Dũng Sức Khỏe").strip(),
                script_dict.get("template", "auto") or "auto",
                str(script_dict.get("duration_seconds", 0) or 0),
                "APPROVED",
                h,
                "",  # reset render status so tool 2 picks it up
                "",  # clear error
                "",  # clear command
                now
            ]
            ws.update(range_name=f"D{row_idx}:O{row_idx}", values=[row_values])
            return True
        except Exception as exc:
            return False

    def save_script_edits_only(self, row_idx, script_dict):
        try:
            ss = self.get_spreadsheet()
            if not ss:
                return False
            ws = ss.worksheet("V3 · Kịch bản")
            items = script_dict.get("items", [])
            items_str = "\n".join(items) if isinstance(items, list) else str(items)

            # Update D to G (Hook, Items, Caption, Brand)
            row_values = [
                script_dict.get("hook", "").strip(),
                items_str.strip(),
                script_dict.get("caption", "").strip(),
                script_dict.get("brand", "Chú Dũng Sức Khỏe").strip(),
            ]
            ws.update(range_name=f"D{row_idx}:G{row_idx}", values=[row_values])
            return True
        except Exception as exc:
            return False

    def batch_approve_scripts(self, script_items):
        try:
            ss = self.get_spreadsheet()
            if not ss:
                return 0, len(script_items)
            ws = ss.worksheet("V3 · Kịch bản")
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            success_count = 0
            for item in script_items:
                row_idx = item.get("__row")
                if not row_idx:
                    continue
                s_dict = {
                    "hook": item.get("HOOK") or item.get("hook", ""),
                    "items": item.get("Các ý (mỗi dòng một ý)") or item.get("items", []),
                    "caption": item.get("Caption mới") or item.get("caption", ""),
                    "brand": item.get("Thương hiệu đầu ra") or item.get("brand", "Chú Dũng Sức Khỏe"),
                    "template": item.get("Mẫu (auto/list/pages)") or item.get("template", "auto") or "auto",
                    "duration_seconds": int(item.get("Thời lượng giây (0=tự động)") or item.get("duration_seconds", 0) or 0)
                }
                if isinstance(s_dict["items"], str):
                    s_dict["items"] = [x.strip() for x in s_dict["items"].splitlines() if x.strip()]
                h = script_hash(s_dict)
                items_str = "\n".join(s_dict["items"])
                row_values = [
                    s_dict["hook"].strip(),
                    items_str.strip(),
                    s_dict["caption"].strip(),
                    s_dict["brand"].strip(),
                    s_dict["template"],
                    str(s_dict["duration_seconds"]),
                    "APPROVED",
                    h,
                    "",
                    "",
                    "",
                    now
                ]
                try:
                    ws.update(range_name=f"D{row_idx}:O{row_idx}", values=[row_values])
                    success_count += 1
                except Exception:
                    pass
            return success_count, len(script_items)
        except Exception:
            return 0, len(script_items)


class AddChannelDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save):
        super().__init__(parent)
        self.title("➕ Thêm Kênh Facebook Mới")
        self.geometry("520x430")
        self.resizable(False, False)
        self.on_save = on_save

        # Center on parent
        self.transient(parent)
        self.grab_set()

        container = ctk.CTkFrame(self, fg_color="#131b2e", corner_radius=0)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            container,
            text="➕ THÊM KÊNH FACEBOOK THEO DÕI",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor="w", pady=(8, 4))

        ctk.CTkLabel(
            container,
            text="Nhập thông tin kênh để lưu trực tiếp vào Google Sheet.",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        ).pack(anchor="w", pady=(0, 14))

        # Tên Kênh
        ctk.CTkLabel(container, text="1. Tên Kênh / Fanpage:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(2, 2))
        self.entry_name = ctk.CTkEntry(container, placeholder_text="Ví dụ: Chăm Sóc Sức Khỏe Gia Đình, Bác Sĩ Cương...")
        self.entry_name.pack(fill="x", pady=(0, 8))

        # URL Fanpage
        ctk.CTkLabel(container, text="2. Link Facebook Fanpage / Reels (URL):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(2, 2))
        self.entry_url = ctk.CTkEntry(container, placeholder_text="https://www.facebook.com/.../reels")
        self.entry_url.pack(fill="x", pady=(0, 8))

        # Chữ Ký Thương Hiệu
        ctk.CTkLabel(container, text="3. Chữ Ký Thương Hiệu Đầu Ra (Watermark):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(2, 2))
        self.entry_brand = ctk.CTkEntry(container)
        self.entry_brand.insert(0, "Chú Dũng Sức Khỏe")
        self.entry_brand.pack(fill="x", pady=(0, 8))

        # Số Video Quét Mặc Định
        ctk.CTkLabel(container, text="4. Số Video Muốn Quét Mỗi Lượt:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(2, 2))
        self.combo_posts = ctk.CTkComboBox(container, values=["3", "5", "10", "15", "20"], width=120)
        self.combo_posts.set("5")
        self.combo_posts.pack(anchor="w", pady=(0, 16))

        # Buttons
        btn_box = ctk.CTkFrame(container, fg_color="transparent")
        btn_box.pack(fill="x", pady=(4, 8))

        ctk.CTkButton(
            btn_box,
            text="✔ Lưu Vào Google Sheet",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=36,
            command=self._save
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            btn_box,
            text="Hủy",
            font=ctk.CTkFont(size=12),
            fg_color="#475569",
            hover_color="#334155",
            height=36,
            width=80,
            command=self.destroy
        ).pack(side="left")

    def _save(self):
        name = self.entry_name.get().strip()
        url = self.entry_url.get().strip()
        brand = self.entry_brand.get().strip() or "Chú Dũng Sức Khỏe"
        posts = self.combo_posts.get().strip() or "5"

        if not name or not url:
            return

        self.on_save(name, url, brand, posts)
        self.destroy()


class RawPostDetailDialog(ctk.CTkToplevel):
    def __init__(self, parent, post_data):
        super().__init__(parent)
        pid = post_data.get("Mã bài") or post_data.get("post_id", "Bài viết FB")
        self.title(f"📄 Chi Tiết Bài Viết & Video Gốc — {pid}")
        self.geometry("860x650")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        container = ctk.CTkFrame(self, fg_color="#0b101d", corner_radius=0)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        # Header
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(hdr, text=f"📌 {pid}", font=ctk.CTkFont(size=16, weight="bold"), text_color="#38bdf8").pack(side="left")

        status = post_data.get("Trạng thái phân tích") or post_data.get("analysis_status", "DONE")
        st_color = "#10b981" if status == "DONE" else ("#ef4444" if status == "ERROR" else "#f59e0b")
        ctk.CTkLabel(hdr, text=f" {status} ", font=ctk.CTkFont(size=11, weight="bold"), fg_color=st_color, corner_radius=6, text_color="#ffffff").pack(side="right")

        # URL & Links bar
        url_bar = ctk.CTkFrame(container, fg_color="#131b2e", corner_radius=8)
        url_bar.pack(fill="x", pady=(0, 10), padx=2)
        url = post_data.get("Link video gốc") or post_data.get("post_url", "")
        if url:
            ctk.CTkLabel(url_bar, text=f"🔗 Link Facebook: {url}", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left", padx=12, pady=8)
            ctk.CTkButton(url_bar, text="Mở Trình Duyệt", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#2563eb", hover_color="#1d4ed8", width=120, height=28, command=lambda: webbrowser.open(url)).pack(side="right", padx=10, pady=6)

        # Meta info
        meta_box = ctk.CTkFrame(container, fg_color="transparent")
        meta_box.pack(fill="x", pady=(0, 10))
        pub = post_data.get("Ngày đăng", "") or "Không rõ"
        col = post_data.get("Lần thu thập", "") or "Không rõ"
        likes = post_data.get("Lượt thích", "0")
        comments = post_data.get("Bình luận", "0")
        ctk.CTkLabel(meta_box, text=f"🕒 Thu thập: {col} | 📅 Đăng: {pub} | 👍 Thích: {likes} | 💬 Bình luận: {comments}", font=ctk.CTkFont(size=11), text_color="#64748b").pack(anchor="w", padx=4)

        # Content split
        content_box = ctk.CTkFrame(container, fg_color="transparent")
        content_box.pack(fill="both", expand=True, pady=(0, 10))
        content_box.grid_columnconfigure((0, 1), weight=1)
        content_box.grid_rowconfigure(0, weight=1)

        # Left: Caption gốc
        left_box = ctk.CTkFrame(content_box, fg_color="#131b2e", corner_radius=8, border_width=1, border_color="#1f293d")
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(left_box, text="💬 CAPTION BÀI VIẾT GỐC", font=ctk.CTkFont(size=12, weight="bold"), text_color="#cbd5e1").pack(anchor="w", padx=12, pady=(10, 4))
        txt_cap = ctk.CTkTextbox(left_box, font=ctk.CTkFont(size=11), fg_color="#070a13", text_color="#cbd5e1", corner_radius=6)
        txt_cap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        txt_cap.insert("1.0", post_data.get("Caption gốc", "").strip() or "Không có caption")
        txt_cap.configure(state="disabled")

        # Right: Trích xuất OCR & Voice JSON
        right_box = ctk.CTkFrame(content_box, fg_color="#131b2e", corner_radius=8, border_width=1, border_color="#1f293d")
        right_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(right_box, text="🎙 VĂN BẢN TRÍCH XUẤT (OCR / GIỌNG NÓI)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=12, pady=(10, 4))

        raw_ext = post_data.get("Nội dung trích xuất (JSON)", "").strip()
        display_ext = raw_ext
        try:
            parsed = json.loads(raw_ext)
            if isinstance(parsed, dict) and "source_text" in parsed:
                display_ext = parsed["source_text"]
                if "segments" in parsed and parsed["segments"]:
                    display_ext += "\n\n--- CÁC PHÂN ĐOẠN VIDEO ---\n"
                    for seg in parsed["segments"]:
                        display_ext += f"[{seg.get('start_seconds', 0)}s]: {seg.get('text', '')}\n"
        except Exception:
            pass

        txt_ext = ctk.CTkTextbox(right_box, font=ctk.CTkFont(size=11), fg_color="#070a13", text_color="#cbd5e1", corner_radius=6)
        txt_ext.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        txt_ext.insert("1.0", display_ext or "Chưa có nội dung trích xuất")
        txt_ext.configure(state="disabled")

        # Footer
        footer = ctk.CTkFrame(container, fg_color="transparent")
        footer.pack(fill="x", pady=(4, 0))

        dl_path = post_data.get("File video trên máy", "")
        if dl_path and Path(dl_path).exists():
            ctk.CTkButton(
                footer,
                text="▶ Mở File Video Gốc",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#8b5cf6",
                hover_color="#7c3aed",
                width=160,
                height=34,
                command=lambda p=dl_path: os.startfile(str(p))
            ).pack(side="left")

        ctk.CTkButton(
            footer,
            text="Đóng",
            font=ctk.CTkFont(size=12),
            fg_color="#475569",
            hover_color="#334155",
            width=100,
            height=34,
            command=self.destroy
        ).pack(side="right")


class ScriptEditorDialog(ctk.CTkToplevel):
    def __init__(self, parent, script_data, on_save_approve, on_save_only=None):
        super().__init__(parent)
        self.script_data = script_data
        self.on_save_approve = on_save_approve
        self.on_save_only = on_save_only
        self.row_idx = script_data.get("__row", 0)

        sid = script_data.get("Mã kịch bản") or script_data.get("Mã bài nguồn", f"Kịch bản #{self.row_idx}")
        self.title(f"✏ Biên Tập Kịch Bản 9:16 & Tạo Video Mẫu — {sid}")
        self.geometry("1060x820")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        container = ctk.CTkFrame(self, fg_color="#0b101d", corner_radius=0)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        # Header Row
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(hdr, text=f"🎬 {sid}", font=ctk.CTkFont(size=16, weight="bold"), text_color="#38bdf8").pack(side="left")

        status = script_data.get("Trạng thái duyệt", "READY_FOR_REVIEW")
        st_text = "🟠 CHỜ DUYỆT" if status == "READY_FOR_REVIEW" else ("🟢 ĐÃ DUYỆT (APPROVED)" if status == "APPROVED" else status)
        st_color = "#f59e0b" if status == "READY_FOR_REVIEW" else ("#10b981" if status == "APPROVED" else "#64748b")
        ctk.CTkLabel(hdr, text=f" {st_text} ", font=ctk.CTkFont(size=11, weight="bold"), fg_color=st_color, corner_radius=6, text_color="#ffffff").pack(side="right")

        # Split 2 Columns: Left (Source Context) vs Right (Editable 9:16 Script)
        body = ctk.CTkFrame(container, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=(0, 10))
        body.grid_columnconfigure(0, weight=4)
        body.grid_columnconfigure(1, weight=6)
        body.grid_rowconfigure(0, weight=1)

        # Left Column: Source context
        left_box = ctk.CTkFrame(body, fg_color="#131b2e", corner_radius=8, border_width=1, border_color="#1f293d")
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(left_box, text="📄 NỘI DUNG GỐC TỪ FACEBOOK", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94a3b8").pack(anchor="w", padx=12, pady=(10, 4))

        src_url = script_data.get("__source_url", "")
        if src_url:
            ctk.CTkButton(left_box, text="🔗 Mở Facebook Xem Bài Gốc", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#1e293b", hover_color="#2563eb", height=28, command=lambda: webbrowser.open(src_url)).pack(anchor="w", padx=12, pady=(0, 6))

        src_cap = script_data.get("__source_caption", "").strip() or "Không có caption"
        ctk.CTkLabel(left_box, text="Caption bài viết gốc:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#64748b").pack(anchor="w", padx=12, pady=(4, 2))
        txt_src_cap = ctk.CTkTextbox(left_box, height=130, font=ctk.CTkFont(size=11), fg_color="#070a13", text_color="#cbd5e1", corner_radius=6)
        txt_src_cap.pack(fill="x", padx=10, pady=(0, 8))
        txt_src_cap.insert("1.0", src_cap)
        txt_src_cap.configure(state="disabled")

        src_ext = script_data.get("__source_extraction", "").strip()
        disp_ext = src_ext
        try:
            parsed = json.loads(src_ext)
            if isinstance(parsed, dict) and "source_text" in parsed:
                disp_ext = parsed["source_text"]
        except Exception:
            pass
        ctk.CTkLabel(left_box, text="Trích xuất âm thanh & chữ trên video:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#64748b").pack(anchor="w", padx=12, pady=(4, 2))
        txt_src_ext = ctk.CTkTextbox(left_box, height=220, font=ctk.CTkFont(size=11), fg_color="#070a13", text_color="#cbd5e1", corner_radius=6)
        txt_src_ext.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        txt_src_ext.insert("1.0", disp_ext or "Chưa có dữ liệu trích xuất")
        txt_src_ext.configure(state="disabled")

        # Right Column: Editable 9:16 Script with Scrollable Frame for seamless fit
        right_box = ctk.CTkScrollableFrame(body, fg_color="#131b2e", corner_radius=8, border_width=1, border_color="#1f293d")
        right_box.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ctk.CTkLabel(right_box, text="🎬 KỊCH BẢN 9:16 CHUẨN HÓA (CHỈNH SỬA & DUYỆT)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=12, pady=(10, 6))

        # Field 1: Hook
        ctk.CTkLabel(right_box, text="🎯 1. HOOK MỞ ĐẦU (Câu giật tít 3s đầu tiên):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#facc15").pack(anchor="w", padx=12, pady=(2, 2))
        self.entry_hook = ctk.CTkEntry(right_box, font=ctk.CTkFont(size=12, weight="bold"), fg_color="#070a13", text_color="#ffffff")
        self.entry_hook.pack(fill="x", padx=10, pady=(0, 8))
        self.entry_hook.insert(0, script_data.get("HOOK", "").strip())

        # Field 2: Bullet points
        ctk.CTkLabel(right_box, text="📝 2. LUẬN ĐIỂM VIDEO 9:16 (Mỗi dòng một ý ngắn gọn, súc tích):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=12, pady=(2, 2))
        self.txt_items = ctk.CTkTextbox(right_box, height=150, font=ctk.CTkFont(size=11), fg_color="#070a13", text_color="#f8fafc", corner_radius=6)
        self.txt_items.pack(fill="x", padx=10, pady=(0, 8))
        self.txt_items.insert("1.0", script_data.get("Các ý (mỗi dòng một ý)", "").strip())

        # Field 3: Caption
        ctk.CTkLabel(right_box, text="💬 3. CAPTION BÀI VIẾT & HASHTAGS:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#a78bfa").pack(anchor="w", padx=12, pady=(2, 2))
        self.txt_caption = ctk.CTkTextbox(right_box, height=65, font=ctk.CTkFont(size=11), fg_color="#070a13", text_color="#e2e8f0", corner_radius=6)
        self.txt_caption.pack(fill="x", padx=10, pady=(0, 8))
        self.txt_caption.insert("1.0", script_data.get("Caption mới", "").strip())

        # Field 4: Brand
        ctk.CTkLabel(right_box, text="🏷 4. CHỮ KÝ THƯƠNG HIỆU (WATERMARK):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").pack(anchor="w", padx=12, pady=(2, 2))
        self.entry_brand = ctk.CTkEntry(right_box, font=ctk.CTkFont(size=11), fg_color="#070a13", text_color="#ffffff")
        self.entry_brand.pack(fill="x", padx=10, pady=(0, 8))
        self.entry_brand.insert(0, script_data.get("Thương hiệu đầu ra", "Chú Dũng Sức Khỏe").strip())

        # Load existing background preference
        saved_bg = ""
        try:
            bg_pref_file = ROOT / "data" / "script_bg_preferences.json"
            if bg_pref_file.is_file():
                bgprefs = json.loads(bg_pref_file.read_text(encoding="utf-8"))
                saved_bg = bgprefs.get(sid, "")
        except Exception:
            pass

        # Load existing music preference
        saved_music = ""
        try:
            music_pref_file = ROOT / "data" / "script_music_preferences.json"
            if music_pref_file.is_file():
                mprefs = json.loads(music_pref_file.read_text(encoding="utf-8"))
                saved_music = mprefs.get(sid, "")
        except Exception:
            pass

        # Load existing style preferences (font size, theme, custom colors)
        saved_theme = "gold"
        saved_size = "auto"
        saved_hook_col = ""
        saved_item_col = ""
        try:
            style_pref_file = ROOT / "data" / "script_style_preferences.json"
            if style_pref_file.is_file():
                sprefs = json.loads(style_pref_file.read_text(encoding="utf-8"))
                if sid in sprefs and isinstance(sprefs[sid], dict):
                    saved_theme = sprefs[sid].get("color_theme", "gold")
                    saved_size = sprefs[sid].get("font_size_mode", "auto")
                    saved_hook_col = sprefs[sid].get("hook_color", "")
                    saved_item_col = sprefs[sid].get("item_color", "")
        except Exception:
            pass

        # Field 5: Background Video Selection
        ctk.CTkLabel(right_box, text="🎬 5. CHỌN VIDEO NỀN 9:16 (HOẶC ĐỂ TỰ ĐỘNG ĐỔI):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#34d399").pack(anchor="w", padx=12, pady=(2, 2))
        self.bg_options = [
            "🎲 Tự động đổi nền (Auto Rotation theo kịch bản)",
            "01 · Tia nắng rừng xanh trong lành",
            "02 · Thác nước đại ngàn tươi mát",
            "03 · Rừng tre trúc thiền định an yên",
            "04 · Nắng sớm qua tán cây tươi mới",
            "05 · Sóng biển êm đềm bãi cát vàng",
            "06 · Sương mù núi thu tĩnh lặng",
            "07 · Giọt sương sớm trên phiến lá",
            "08 · Đồi thông sương mù bình minh",
            "09 · Bay trên tầng mây hoàng hôn",
            "10 · Hoàng hôn chân trời ấm áp",
            "11 · Dòng suối đá trong lành sảng khoái",
            "12 · Thế giới đại dương sâu thẳm"
        ]
        self.combo_bg = ctk.CTkOptionMenu(right_box, values=self.bg_options, fg_color="#070a13", button_color="#1e293b", text_color="#ffffff", dropdown_fg_color="#131b2e")
        default_bg_choice = self.bg_options[0]
        if saved_bg:
            for opt in self.bg_options:
                if saved_bg in opt or (len(saved_bg) > 2 and saved_bg[:2] == opt[:2]):
                    default_bg_choice = opt
                    break
        self.combo_bg.set(default_bg_choice)
        self.combo_bg.pack(fill="x", padx=10, pady=(0, 8))

        # Field 6: Background Music Selection
        ctk.CTkLabel(right_box, text="🎵 6. CHỌN NHẠC NỀN 9:16 (HOẶC ĐỂ TỰ ĐỘNG ĐỔI):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ec4899").pack(anchor="w", padx=12, pady=(2, 2))
        self.music_options = [
            "🎲 Tự động đổi nhạc (Xoay tua đa dạng theo kịch bản)",
            "01 · Thiền định an yên (Infinite Peace - Sâu lắng, chữa lành)",
            "02 · Piano truyền cảm hứng (Lovely Piano - Ấm áp, vui khỏe)",
            "03 · Nắng mai khởi đầu (Adding The Sun - Tươi sáng, tích cực)",
            "04 · Ánh sáng hy vọng (See The Light - Động lực, thấu hiểu)",
            "05 · Bay bổng khát vọng (Inventing Flight - Mở mang, sảng khoái)",
            "06 · Guitar mộc mạc (Mellow Acoustic - Gần gũi, thư thái)",
            "07 · Sáo trúc thanh tao (Chinese Flute - Dưỡng sinh, Á Đông)",
            "08 · Piano sâu lắng (Nostalgic Piano - Chiêm nghiệm, chân thành)",
            "09 · Buổi chiều êm ả (Sunset Melody - Hoàng hôn nhẹ dịu)",
            "10 · Nhạc nền gốc mặc định (Original Ambient)"
        ]
        self.combo_music = ctk.CTkOptionMenu(right_box, values=self.music_options, fg_color="#070a13", button_color="#1e293b", text_color="#ffffff", dropdown_fg_color="#131b2e")
        default_music_choice = self.music_options[0]
        if saved_music:
            for opt in self.music_options:
                if saved_music in opt or (len(saved_music) > 2 and saved_music[:2] == opt[:2]):
                    default_music_choice = opt
                    break
        self.combo_music.set(default_music_choice)
        self.combo_music.pack(fill="x", padx=10, pady=(0, 8))

        # Field 7 & 8: Font Size Mode & Color Theme in 2 Columns
        style_row = ctk.CTkFrame(right_box, fg_color="transparent")
        style_row.pack(fill="x", padx=10, pady=(0, 6))
        style_row.grid_columnconfigure(0, weight=1)
        style_row.grid_columnconfigure(1, weight=1)

        # Field 7: Font Size Mode
        col_size = ctk.CTkFrame(style_row, fg_color="transparent")
        col_size.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(col_size, text="📐 7. CỠ CHỮ & BỐ CỤC:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(0, 2))
        self.size_options = [
            "⚡ Tự động (Thích ứng số ý)",
            "🔍 Lớn (+20% - Nổi bật, ít ý)",
            "📐 Vừa (Kích cỡ chuẩn)",
            "🔎 Nhỏ (-15% - Nhiều chữ)"
        ]
        self.combo_size = ctk.CTkOptionMenu(col_size, values=self.size_options, fg_color="#070a13", button_color="#1e293b", text_color="#ffffff", dropdown_fg_color="#131b2e")
        size_idx = 0
        if saved_size == "large":
            size_idx = 1
        elif saved_size == "medium":
            size_idx = 2
        elif saved_size == "small":
            size_idx = 3
        self.combo_size.set(self.size_options[size_idx])
        self.combo_size.pack(fill="x")

        # Field 8: Color Theme
        col_theme = ctk.CTkFrame(style_row, fg_color="transparent")
        col_theme.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(col_theme, text="🌈 8. BỘ MÀU CHỮ & THẺ NỀN:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#f59e0b").pack(anchor="w", pady=(0, 2))
        self.theme_options = [
            "🌟 Vàng Kim Sang Trọng",
            "🌊 Xanh Biển Hiện Đại",
            "🌿 Xanh Ngọc Sức Khỏe",
            "🌸 Đỏ Hồng Nổi Bật",
            "⚪ Trắng Tinh Tế Tối Giản"
        ]
        self.combo_theme = ctk.CTkOptionMenu(col_theme, values=self.theme_options, fg_color="#070a13", button_color="#1e293b", text_color="#ffffff", dropdown_fg_color="#131b2e", command=self._on_theme_changed)
        theme_idx = 0
        if "cyan" in saved_theme:
            theme_idx = 1
        elif "emerald" in saved_theme:
            theme_idx = 2
        elif "ruby" in saved_theme:
            theme_idx = 3
        elif "white" in saved_theme:
            theme_idx = 4
        self.combo_theme.set(self.theme_options[theme_idx])
        self.combo_theme.pack(fill="x")

        # Field 8: Fine-tune custom colors (Hook Color & Item Color)
        color_custom_frame = ctk.CTkFrame(right_box, fg_color="#0d1424", corner_radius=6, border_width=1, border_color="#1e293b")
        color_custom_frame.pack(fill="x", padx=10, pady=(6, 12))

        ctk.CTkLabel(color_custom_frame, text="🎨 Tùy Chỉnh Màu Sắc Chi Tiết (Tùy chọn mã màu Hex / Bấm nút để chọn):", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(anchor="w", padx=10, pady=(6, 2))

        custom_row = ctk.CTkFrame(color_custom_frame, fg_color="transparent")
        custom_row.pack(fill="x", padx=8, pady=(0, 8))
        custom_row.grid_columnconfigure(0, weight=1)
        custom_row.grid_columnconfigure(1, weight=1)

        # Hook color
        c_hook_box = ctk.CTkFrame(custom_row, fg_color="transparent")
        c_hook_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(c_hook_box, text="Màu tiêu đề (Hook):", font=ctk.CTkFont(size=10), text_color="#cbd5e1").pack(anchor="w")
        hook_sub = ctk.CTkFrame(c_hook_box, fg_color="transparent")
        hook_sub.pack(fill="x", pady=(2, 0))
        self.entry_hook_color = ctk.CTkEntry(hook_sub, font=ctk.CTkFont(family="Consolas", size=10), fg_color="#070a13", text_color="#ffffff", height=26)
        self.entry_hook_color.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.entry_hook_color.insert(0, saved_hook_col or THEMES.get(saved_theme, THEMES["gold"])["hook_color"])
        ctk.CTkButton(hook_sub, text="🎨 Chọn", width=54, height=26, font=ctk.CTkFont(size=10, weight="bold"), fg_color="#334155", hover_color="#475569", command=self._pick_hook_color).pack(side="right")

        # Item color
        c_item_box = ctk.CTkFrame(custom_row, fg_color="transparent")
        c_item_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(c_item_box, text="Màu chữ nội dung:", font=ctk.CTkFont(size=10), text_color="#cbd5e1").pack(anchor="w")
        item_sub = ctk.CTkFrame(c_item_box, fg_color="transparent")
        item_sub.pack(fill="x", pady=(2, 0))
        self.entry_item_color = ctk.CTkEntry(item_sub, font=ctk.CTkFont(family="Consolas", size=10), fg_color="#070a13", text_color="#ffffff", height=26)
        self.entry_item_color.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.entry_item_color.insert(0, saved_item_col or THEMES.get(saved_theme, THEMES["gold"])["item_color"])
        ctk.CTkButton(item_sub, text="🎨 Chọn", width=54, height=26, font=ctk.CTkFont(size=10, weight="bold"), fg_color="#334155", hover_color="#475569", command=self._pick_item_color).pack(side="right")

        # Footer Actions
        footer = ctk.CTkFrame(container, fg_color="transparent")
        footer.pack(fill="x", pady=(4, 0))

        # Main Button: Save & Approve & Render Sample
        ctk.CTkButton(
            footer,
            text="🎬 LƯU SỬA ĐỔI & TẠO VIDEO MẪU NGAY",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=38,
            command=self._on_save_and_approve
        ).pack(side="left", padx=(0, 8))

        if self.on_save_only:
            ctk.CTkButton(
                footer,
                text="💾 Chỉ Lưu Sửa Đổi (Chưa Dựng)",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                height=38,
                command=self._on_save_only
            ).pack(side="left", padx=4)

        ctk.CTkButton(
            footer,
            text="Đóng",
            font=ctk.CTkFont(size=12),
            fg_color="#475569",
            hover_color="#334155",
            width=90,
            height=38,
            command=self.destroy
        ).pack(side="right")

    def _pick_hook_color(self):
        curr = self.entry_hook_color.get().strip() or "#facc15"
        res = colorchooser.askcolor(color=curr, title="Chọn màu tiêu đề Hook")
        if res and res[1]:
            self.entry_hook_color.delete(0, "end")
            self.entry_hook_color.insert(0, res[1].upper())

    def _pick_item_color(self):
        curr = self.entry_item_color.get().strip() or "#ffffff"
        res = colorchooser.askcolor(color=curr, title="Chọn màu chữ nội dung")
        if res and res[1]:
            self.entry_item_color.delete(0, "end")
            self.entry_item_color.insert(0, res[1].upper())

    def _on_theme_changed(self, choice):
        tkey = "gold"
        if "Xanh Biển" in choice:
            tkey = "cyan"
        elif "Xanh Ngọc" in choice:
            tkey = "emerald"
        elif "Đỏ Hồng" in choice:
            tkey = "ruby"
        elif "Trắng" in choice:
            tkey = "white"
        th = THEMES.get(tkey, THEMES["gold"])
        self.entry_hook_color.delete(0, "end")
        self.entry_hook_color.insert(0, th["hook_color"])
        self.entry_item_color.delete(0, "end")
        self.entry_item_color.insert(0, th["item_color"])

    def _get_payload(self):
        hook_val = self.entry_hook.get().strip()
        items_val = [x.strip() for x in self.txt_items.get("1.0", "end").strip().splitlines() if x.strip()]
        caption_val = self.txt_caption.get("1.0", "end").strip()
        brand_val = self.entry_brand.get().strip() or "Chú Dũng Sức Khỏe"

        # Background choice
        bg_choice = self.combo_bg.get()
        bg_map = {
            "01": "01_tia_nang_rung_xanh.mp4",
            "02": "02_thac_nuoc_dai_ngan.mp4",
            "03": "03_rung_tre_thien_dinh.mp4",
            "04": "04_nang_som_qua_tan_cay.mp4",
            "05": "05_song_bien_em_dem.mp4",
            "06": "06_suong_mu_nui_thu.mp4",
            "07": "07_giot_suong_tren_la.mp4",
            "08": "08_doi_thong_binh_minh.mp4",
            "09": "09_bay_tren_tang_may.mp4",
            "10": "10_hoang_hon_chan_troi.mp4",
            "11": "11_dong_suoi_chay_xiet.mp4",
            "12": "12_the_gioi_dai_duong.mp4",
        }
        chosen_bg = ""
        for k, fname in bg_map.items():
            if bg_choice.startswith(k):
                chosen_bg = fname
                break

        # Music choice
        music_choice = self.combo_music.get()
        music_map = {
            "01": "01_thien_dinh_an_yen.mp3",
            "02": "02_piano_truyen_cam_hung.mp3",
            "03": "03_nang_mai_khoi_dau.mp3",
            "04": "04_anh_sang_hy_vong.mp3",
            "05": "05_bay_bong_khat_vong.mp3",
            "06": "06_guitar_moc_mac.mp3",
            "07": "07_sao_truc_thanh_tao.mp3",
            "08": "08_piano_sau_lang.mp3",
            "09": "09_buoi_chieu_em_a.mp3",
            "10": "10_nhac_nen_goc_ambient.m4a",
        }
        chosen_music = ""
        for k, fname in music_map.items():
            if music_choice.startswith(k):
                chosen_music = fname
                break

        # Font size mode choice
        size_choice = self.combo_size.get()
        chosen_size = "auto"
        if "Lớn" in size_choice:
            chosen_size = "large"
        elif "Vừa" in size_choice:
            chosen_size = "medium"
        elif "Nhỏ" in size_choice:
            chosen_size = "small"

        # Theme choice
        theme_choice = self.combo_theme.get()
        chosen_theme = "gold"
        if "Xanh Biển" in theme_choice:
            chosen_theme = "cyan"
        elif "Xanh Ngọc" in theme_choice:
            chosen_theme = "emerald"
        elif "Đỏ Hồng" in theme_choice:
            chosen_theme = "ruby"
        elif "Trắng" in theme_choice:
            chosen_theme = "white"

        hook_color_val = self.entry_hook_color.get().strip()
        item_color_val = self.entry_item_color.get().strip()

        sid = self.script_data.get("Mã kịch bản") or self.script_data.get("Mã bài nguồn")
        if sid and chosen_bg:
            try:
                pref_file = ROOT / "data" / "script_bg_preferences.json"
                pref_file.parent.mkdir(parents=True, exist_ok=True)
                prefs = {}
                if pref_file.is_file():
                    try:
                        prefs = json.loads(pref_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                prefs[sid] = chosen_bg
                pref_file.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        if sid and chosen_music:
            try:
                mpref_file = ROOT / "data" / "script_music_preferences.json"
                mpref_file.parent.mkdir(parents=True, exist_ok=True)
                mprefs = {}
                if mpref_file.is_file():
                    try:
                        mprefs = json.loads(mpref_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                mprefs[sid] = chosen_music
                mpref_file.write_text(json.dumps(mprefs, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        if sid:
            try:
                spref_file = ROOT / "data" / "script_style_preferences.json"
                spref_file.parent.mkdir(parents=True, exist_ok=True)
                sprefs = {}
                if spref_file.is_file():
                    try:
                        sprefs = json.loads(spref_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                sprefs[sid] = {
                    "color_theme": chosen_theme,
                    "font_size_mode": chosen_size,
                    "hook_color": hook_color_val,
                    "item_color": item_color_val
                }
                spref_file.write_text(json.dumps(sprefs, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        return {
            "hook": hook_val,
            "items": items_val,
            "caption": caption_val,
            "brand": brand_val,
            "template": self.script_data.get("Mẫu (auto/list/pages)", "auto") or "auto",
            "duration_seconds": int(self.script_data.get("Thời lượng giây (0=tự động)", 0) or 0),
            "bg_video": chosen_bg,
            "bg_music": chosen_music,
            "font_size_mode": chosen_size,
            "color_theme": chosen_theme,
            "hook_color": hook_color_val,
            "item_color": item_color_val
        }

    def _on_save_and_approve(self):
        payload = self._get_payload()
        self.destroy()
        self.on_save_approve(self.row_idx, payload)

    def _on_save_only(self):
        payload = self._get_payload()
        self.destroy()
        if self.on_save_only:
            self.on_save_only(self.row_idx, payload)


class VideoStudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("🎬 FB Auto Video Studio Pro v3.0 (Quy trình 3 bước)")
        self.geometry("1160x820")
        self.minsize(1040, 720)

        # App Icon
        icon_path = ROOT / "assets" / "app_icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        self.config = load_config()
        self.log_queue = queue.Queue()
        self.sheet_bridge = SheetBridge(self.config)
        self.channel_checks = {}

        # Tab 2 state (Excel-like subtabs, tables, selection)
        self.active_scripts_subtab = "scripts"
        self._cached_scripts = []
        self._cached_posts = []
        self.script_checkbox_vars = {}
        self.scripts_filter_mode = "Tất cả"

        # Background runners
        self.tool1 = ProcessRunner(
            "Tool 1 (Quét bài & Kịch bản AI)",
            [sys.executable, "-u", "-X", "utf8", "tool1.py", "--watch"],
            self.log_queue,
            tag="TOOL1"
        )
        self.tool2 = ProcessRunner(
            "Tool 2 (Dựng Video 9:16)",
            [sys.executable, "-u", "-X", "utf8", "tool2.py", "--watch"],
            self.log_queue,
            tag="TOOL2"
        )

        self._init_layout()
        self._init_sidebar()
        self._init_views()
        self.show_view("dashboard")

        # Periodic tasks
        self.after(100, self._process_logs)
        self.after(1000, self._refresh_dashboard_stats)
        self.after(500, self.refresh_channels_list)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.log_queue.put(("SYS", "🚀 Ứng dụng FB Auto Video Studio v3 (Giao diện tinh gọn) đã sẵn sàng."))

    def _init_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def _init_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color="#0b0f19")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)

        # App Logo & Branding
        brand_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_box.pack(fill="x", padx=16, pady=(20, 14))

        lbl_logo = ctk.CTkLabel(brand_box, text="🎬 VIDEO STUDIO", font=ctk.CTkFont(size=20, weight="bold"), text_color="#38bdf8")
        lbl_logo.pack(anchor="w")
        lbl_sub = ctk.CTkLabel(brand_box, text="Tự Động Hóa Reels FB v3", font=ctk.CTkFont(size=12), text_color="#64748b")
        lbl_sub.pack(anchor="w")

        # 1-Click Master Run Button
        self.btn_master = ctk.CTkButton(
            self.sidebar,
            text="▶ BẬT TỰ ĐỘNG TOÀN BỘ",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=46,
            corner_radius=8,
            command=self.toggle_all_tools
        )
        self.btn_master.pack(fill="x", padx=16, pady=(4, 16))

        # Main Navigation (Strictly 3 workflow tabs + settings)
        nav_label = ctk.CTkLabel(self.sidebar, text="QUY TRÌNH 3 BƯỚC", font=ctk.CTkFont(size=10, weight="bold"), text_color="#475569")
        nav_label.pack(anchor="w", padx=18, pady=(8, 4))

        self.nav_btns = {}
        nav_items = [
            ("dashboard", "📊 1. Tổng Quan & Vận Hành"),
            ("scripts", "📝 2. Duyệt & Sửa Kịch Bản"),
            ("renders", "🎬 3. Kho Video 9:16"),
            ("settings", "⚙ Cài Đặt & Kết Nối"),
        ]
        for key, text in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                anchor="w",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="transparent",
                text_color="#94a3b8",
                hover_color="#1e293b",
                height=40,
                corner_radius=6,
                command=lambda k=key: self.show_view(k)
            )
            btn.pack(fill="x", padx=12, pady=3)
            self.nav_btns[key] = btn

        # System Status Badges at Bottom
        status_box = ctk.CTkFrame(self.sidebar, fg_color="#131b2e", corner_radius=8, border_width=1, border_color="#1f293d")
        status_box.pack(side="bottom", fill="x", padx=14, pady=16)

        ctk.CTkLabel(status_box, text="TRẠNG THÁI HỆ THỐNG", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").pack(anchor="w", padx=12, pady=(8, 4))
        ctk.CTkLabel(status_box, text="🟢 Google Sheet: Sẵn sàng", font=ctk.CTkFont(size=11), text_color="#38bdf8").pack(anchor="w", padx=12, pady=2)
        ctk.CTkLabel(status_box, text="🟢 Extension: Port 8765", font=ctk.CTkFont(size=11), text_color="#34d399").pack(anchor="w", padx=12, pady=2)
        ctk.CTkLabel(status_box, text="🟢 AI: gemini-3.6-flash", font=ctk.CTkFont(size=11), text_color="#f472b6").pack(anchor="w", padx=12, pady=(2, 8))

    def _init_views(self):
        self.views = {}
        for key in ["dashboard", "scripts", "renders", "settings"]:
            if key == "settings":
                frame = ctk.CTkScrollableFrame(self, fg_color="#070a13", corner_radius=0)
            else:
                frame = ctk.CTkFrame(self, fg_color="#070a13", corner_radius=0)
            self.views[key] = frame

        self._build_dashboard_view()
        self._build_scripts_view()
        self._build_renders_view()
        self._build_settings_view()

    def show_view(self, key):
        for k, frame in self.views.items():
            frame.grid_forget()
            if k in self.nav_btns:
                self.nav_btns[k].configure(fg_color="transparent", text_color="#94a3b8")
        self.views[key].grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        if key in self.nav_btns:
            self.nav_btns[key].configure(fg_color="#1e293b", text_color="#38bdf8")

        if key == "scripts":
            if getattr(self, "active_scripts_subtab", "scripts") == "scripts":
                self.refresh_scripts_list()
            else:
                self.refresh_raw_posts_list()
        elif key == "renders":
            self.refresh_renders_list()

    # ================= VIEW 1: DASHBOARD =================
    def _build_dashboard_view(self):
        v = self.views["dashboard"]

        # Header Banner
        header = ctk.CTkFrame(v, fg_color="#131b2e", corner_radius=10, border_width=1, border_color="#1f293d")
        header.pack(fill="x", pady=(0, 12))

        title = ctk.CTkLabel(header, text="🎬 BẢNG ĐIỀU KHIỂN VẬN HÀNH V3", font=ctk.CTkFont(size=18, weight="bold"), text_color="#ffffff")
        title.pack(anchor="w", padx=18, pady=(12, 2))
        subtitle = ctk.CTkLabel(
            header,
            text="Quy trình 3 bước: Quét bài FB ➜ Con người duyệt & sửa kịch bản ➜ Tự động xuất video 9:16",
            font=ctk.CTkFont(size=12),
            text_color="#94a3b8"
        )
        subtitle.pack(anchor="w", padx=18, pady=(0, 12))

        # 3 Core Workflow KPI Cards (Mapped strictly to business stages)
        cards_box = ctk.CTkFrame(v, fg_color="transparent")
        cards_box.pack(fill="x", pady=(0, 12))
        cards_box.grid_columnconfigure((0, 1, 2), weight=1)

        self.stat_cards = {}
        stats_def = [
            ("posts", "1. BÀI VIẾT THU THẬP", "0", "#3b82f6", "Bài đã cào từ kênh FB"),
            ("pending_scripts", "2. KỊCH BẢN CHỜ DUYỆT", "0", "#f59e0b", "Cần con người kiểm duyệt"),
            ("renders", "3. VIDEO 9:16 ĐÃ XUẤT", "0", "#10b981", "Sẵn sàng đăng Reels/TikTok"),
        ]
        for col, (k, title_text, init_val, border_col, sub_desc) in enumerate(stats_def):
            card = ctk.CTkFrame(cards_box, fg_color="#131b2e", corner_radius=10, border_width=1, border_color=border_col)
            card.grid(row=0, column=col, padx=5, sticky="ew")

            ctk.CTkLabel(card, text=title_text, font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").pack(anchor="w", padx=14, pady=(10, 2))
            lbl_val = ctk.CTkLabel(card, text=init_val, font=ctk.CTkFont(size=26, weight="bold"), text_color="#ffffff")
            lbl_val.pack(anchor="w", padx=14, pady=(0, 2))
            ctk.CTkLabel(card, text=sub_desc, font=ctk.CTkFont(size=10), text_color="#64748b").pack(anchor="w", padx=14, pady=(0, 10))
            self.stat_cards[k] = lbl_val

        # ================= CHANNELS MANAGER & SCAN CONTROLS =================
        channels_box = ctk.CTkFrame(v, fg_color="#131b2e", corner_radius=10, border_width=1, border_color="#1f293d")
        channels_box.pack(fill="x", pady=(0, 12))

        # Channel Box Header
        ch_header = ctk.CTkFrame(channels_box, fg_color="transparent")
        ch_header.pack(fill="x", padx=14, pady=(10, 6))

        ctk.CTkLabel(
            ch_header,
            text="📡 DANH SÁCH KÊNH FACEBOOK (Chọn kênh để quét & thêm kênh mới)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        ).pack(side="left")

        ctk.CTkButton(
            ch_header,
            text="➕ Thêm Kênh Mới",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=28,
            width=130,
            command=self.open_add_channel_dialog
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            ch_header,
            text="🔄 Tải Lại",
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            height=28,
            width=70,
            command=self.refresh_channels_list
        ).pack(side="right")

        # Scrollable list of channels
        self.channels_scroll = ctk.CTkScrollableFrame(channels_box, height=130, fg_color="#070a13", corner_radius=6)
        self.channels_scroll.pack(fill="x", padx=12, pady=(0, 8))

        # Bottom Scan Trigger Bar
        scan_bar = ctk.CTkFrame(channels_box, fg_color="transparent")
        scan_bar.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(scan_bar, text="Số lượng video quét:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(side="left", padx=(4, 6))

        self.combo_max_posts = ctk.CTkComboBox(
            scan_bar,
            values=["3 video", "5 video (Chuẩn)", "10 video", "15 video", "20 video"],
            width=140,
            height=32,
            font=ctk.CTkFont(size=11)
        )
        self.combo_max_posts.set("5 video (Chuẩn)")
        self.combo_max_posts.pack(side="left", padx=(0, 10))

        self.btn_scan_selected = ctk.CTkButton(
            scan_bar,
            text="🔍 BẮT ĐẦU QUÉT CÁC KÊNH ĐÃ CHỌN",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#d97706",
            hover_color="#b45309",
            height=34,
            command=self.trigger_scan_selected_channels
        )
        self.btn_scan_selected.pack(side="left", fill="x", expand=True, padx=4)

        # Quick Actions Bar
        actions_bar = ctk.CTkFrame(v, fg_color="#131b2e", corner_radius=10, border_width=1, border_color="#1f293d")
        actions_bar.pack(fill="x", pady=(0, 12))

        act_inner = ctk.CTkFrame(actions_bar, fg_color="transparent")
        act_inner.pack(fill="x", padx=10, pady=8)

        ctk.CTkButton(
            act_inner,
            text="🌐 Mở Google Sheet",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            height=32,
            command=self.open_google_sheet
        ).pack(side="left", padx=4, fill="x", expand=True)

        ctk.CTkButton(
            act_inner,
            text="📁 Mở Thư Mục Video",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#475569",
            hover_color="#334155",
            height=32,
            command=self.open_renders_folder
        ).pack(side="left", padx=4, fill="x", expand=True)

        ctk.CTkButton(
            act_inner,
            text="🎬 Dựng Video Thủ Công (1 lần)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            height=32,
            command=self.trigger_render_once
        ).pack(side="left", padx=4, fill="x", expand=True)

        # Realtime Activity Terminal Box
        log_box = ctk.CTkFrame(v, fg_color="#131b2e", corner_radius=10, border_width=1, border_color="#1f293d")
        log_box.pack(fill="both", expand=True)

        log_top = ctk.CTkFrame(log_box, fg_color="transparent")
        log_top.pack(fill="x", padx=14, pady=(8, 4))

        ctk.CTkLabel(log_top, text="📋 NHẬT KÝ VẬN HÀNH THỜI GIAN THỰC", font=ctk.CTkFont(size=12, weight="bold"), text_color="#cbd5e1").pack(side="left")

        ctk.CTkButton(
            log_top,
            text="🗑 Xóa",
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            width=60,
            height=26,
            command=self.clear_logs
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            log_top,
            text="📋 Sao Chép",
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            width=80,
            height=26,
            command=self.copy_logs
        ).pack(side="right")

        self.dash_log_text = ctk.CTkTextbox(
            log_box,
            fg_color="#070a13",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#a7f3d0",
            corner_radius=6
        )
        self.dash_log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ================= CHANNELS LIST CONTROLS =================
    def refresh_channels_list(self):
        for widget in self.channels_scroll.winfo_children():
            widget.destroy()

        lbl_loading = ctk.CTkLabel(self.channels_scroll, text="Đang tải danh sách kênh từ Google Sheet...", font=ctk.CTkFont(size=12), text_color="#94a3b8")
        lbl_loading.pack(pady=20)

        def _bg():
            channels = self.sheet_bridge.fetch_channels()
            try:
                if self.winfo_exists():
                    self.after(0, lambda: self._render_channels_items(channels))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def _render_channels_items(self, channels):
        for widget in self.channels_scroll.winfo_children():
            widget.destroy()

        self.channel_checks = {}

        if not channels:
            ctk.CTkLabel(
                self.channels_scroll,
                text="Chưa có kênh nào trên Google Sheet. Hãy bấm nút [➕ Thêm Kênh Mới] ở trên.",
                font=ctk.CTkFont(size=12),
                text_color="#94a3b8"
            ).pack(pady=20)
            return

        for ch in channels:
            row_idx = ch["row"]
            card = ctk.CTkFrame(self.channels_scroll, fg_color="#131b2e", corner_radius=6, border_width=1, border_color="#1f293d")
            card.pack(fill="x", padx=4, pady=3)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=10, pady=6)

            # Checkbox with Channel Name
            var = ctk.BooleanVar(value=True)
            self.channel_checks[row_idx] = var

            chk = ctk.CTkCheckBox(
                inner,
                text=f"Kênh #{ch['id']}: {ch['name']}",
                variable=var,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#ffffff",
                checkbox_height=20,
                checkbox_width=20
            )
            chk.pack(side="left")

            # URL summary
            url_display = ch["url"]
            if len(url_display) > 45:
                url_display = url_display[:42] + "..."
            ctk.CTkLabel(inner, text=f"({url_display})", font=ctk.CTkFont(size=11), text_color="#64748b").pack(side="left", padx=8)

            # Status Badge & Error if any
            st_text = ch["status"] or "Sẵn sàng"
            if st_text == "FAILED":
                badge_color = "#ef4444"
            elif st_text == "Sẵn sàng" or st_text == "DONE":
                badge_color = "#10b981"
            elif "quét" in st_text.lower() or "scanning" in st_text.lower():
                badge_color = "#f59e0b"
            else:
                badge_color = "#64748b"

            ctk.CTkLabel(
                inner,
                text=f" {st_text} ",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=badge_color,
                corner_radius=4,
                text_color="#ffffff"
            ).pack(side="right", padx=(6, 0))

            if ch.get("error"):
                err_disp = ch["error"]
                if len(err_disp) > 35:
                    err_disp = err_disp[:32] + "..."
                ctk.CTkLabel(
                    inner,
                    text=f"⚠️ {err_disp}",
                    font=ctk.CTkFont(size=10),
                    text_color="#f87171"
                ).pack(side="right", padx=6)

            # Delete button
            ctk.CTkButton(
                inner,
                text="🗑 Xóa",
                font=ctk.CTkFont(size=10),
                fg_color="#ef4444",
                hover_color="#dc2626",
                width=50,
                height=24,
                command=lambda r=row_idx, n=ch["name"]: self.action_delete_channel(r, n)
            ).pack(side="right")

    def open_add_channel_dialog(self):
        AddChannelDialog(self, on_save=self.action_add_channel)

    def action_add_channel(self, name, url, brand, max_posts):
        def _bg():
            self.log_queue.put(("SYS", f"Đang thêm kênh '{name}' vào Google Sheet..."))
            ok, msg = self.sheet_bridge.add_channel(name, url, brand, max_posts)
            if ok:
                self.log_queue.put(("SYS", f"✅ {msg}"))
                self.after(500, self.refresh_channels_list)
            else:
                self.log_queue.put(("ERR", f"❌ {msg}"))

        threading.Thread(target=_bg, daemon=True).start()

    def action_delete_channel(self, row_idx, name):
        def _bg():
            self.log_queue.put(("SYS", f"Đang xóa kênh '{name}' khỏi Google Sheet..."))
            ok, msg = self.sheet_bridge.delete_channel(row_idx)
            if ok:
                self.log_queue.put(("SYS", f"✅ {msg}"))
                self.after(500, self.refresh_channels_list)
            else:
                self.log_queue.put(("ERR", f"❌ {msg}"))

        threading.Thread(target=_bg, daemon=True).start()

    def trigger_scan_selected_channels(self):
        # Gather selected rows
        selected = [r for r, var in self.channel_checks.items() if var.get()]
        if not selected:
            self.log_queue.put(("SYS", "⚠️ Bạn chưa tích chọn kênh nào để quét. Hãy tích vào ô vuông trước tên kênh!"))
            return

        # Extract number of posts from combo (e.g. '10 video' -> '10')
        combo_val = self.combo_max_posts.get()
        m = re.search(r"\d+", combo_val)
        posts_num = m.group(0) if m else "5"

        # Auto-start tool1 if not running
        if not self.tool1.running:
            self.tool1.start()
            self.btn_master.configure(text="⏹ DỪNG HỆ THỐNG", fg_color="#ef4444", hover_color="#dc2626")
            self.log_queue.put(("SYS", "🟢 Đã tự động kích hoạt Tool 1 (Mở cổng 8765 kết nối Chrome Extension)."))

        def _bg():
            self.log_queue.put(("SYS", f"Đang gửi lệnh quét cho {len(selected)} kênh đã chọn (giới hạn {posts_num} video/kênh)..."))
            ok, msg = self.sheet_bridge.trigger_scan_channels(selected, posts_num)
            if ok:
                self.log_queue.put(("SYS", f"🟢 {msg}"))
                self.log_queue.put(("SYS", "👉 Hãy đảm bảo trình duyệt Chrome đang mở và Extension 'FB Video Studio v3' đang bật."))
                self.log_queue.put(("SYS", "⏳ Extension sẽ tự động mở tab Facebook Reels để quét sau vài giây..."))
                self.after(1000, self.refresh_channels_list)
            else:
                self.log_queue.put(("ERR", f"❌ {msg}"))

        threading.Thread(target=_bg, daemon=True).start()

    # ================= VIEW 2: SCRIPTS & RAW POSTS (EXCEL-LIKE SUBTABS & TABLES) =================
    def _build_scripts_view(self):
        v = self.views["scripts"]

        # Top Bar: Title & Refresh
        top_bar = ctk.CTkFrame(v, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 6))

        title = ctk.CTkLabel(
            top_bar,
            text="📝 TRẠM KIỂM DUYỆT & TẠO VIDEO MẪU TỪ BẢNG TÍNH",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(side="left")

        # Excel-style Sheet Subtab Bar
        self.subtab_bar = ctk.CTkFrame(v, fg_color="#0b101d", corner_radius=8, height=44)
        self.subtab_bar.pack(fill="x", pady=(0, 10))

        self.btn_subtab_scripts = ctk.CTkButton(
            self.subtab_bar,
            text="📋 V3 · Kịch Bản AI & Duyệt (Tạo Video Mẫu)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=34,
            corner_radius=6,
            command=lambda: self.switch_scripts_subtab("scripts")
        )
        self.btn_subtab_scripts.pack(side="left", padx=(6, 4), pady=5)

        self.btn_subtab_posts = ctk.CTkButton(
            self.subtab_bar,
            text="📥 V3 · Bài Viết & Video Gốc (Đã Thu Thập)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#131b2e",
            text_color="#94a3b8",
            hover_color="#1e293b",
            height=34,
            corner_radius=6,
            command=lambda: self.switch_scripts_subtab("posts")
        )
        self.btn_subtab_posts.pack(side="left", padx=4, pady=5)

        # Quick Refresh Button on right side of subtab bar
        self.btn_refresh_subtab = ctk.CTkButton(
            self.subtab_bar,
            text="🔄 Tải Lại",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            width=90,
            height=30,
            command=self._on_subtab_refresh_clicked
        )
        self.btn_refresh_subtab.pack(side="right", padx=8, pady=7)

        # Container 1: Subtab Scripts (Kịch bản AI)
        self.subtab_scripts_container = ctk.CTkFrame(v, fg_color="transparent")
        self.subtab_scripts_container.pack(fill="both", expand=True)

        # Container 2: Subtab Posts (Bài viết & video gốc)
        self.subtab_posts_container = ctk.CTkFrame(v, fg_color="transparent")
        # will pack when switched

        # Build UI for both containers
        self._init_subtab_scripts_ui()
        self._init_subtab_posts_ui()

    def _init_subtab_scripts_ui(self):
        c = self.subtab_scripts_container

        # Toolbar Frame
        tb = ctk.CTkFrame(c, fg_color="#131b2e", corner_radius=8, height=50)
        tb.pack(fill="x", pady=(0, 8))

        # Master Checkbox
        self.chk_all_scripts_var = ctk.BooleanVar(value=False)
        self.chk_all_scripts = ctk.CTkCheckBox(
            tb,
            text="Chọn tất cả",
            font=ctk.CTkFont(size=12, weight="bold"),
            variable=self.chk_all_scripts_var,
            command=self._toggle_select_all_scripts,
            fg_color="#10b981",
            hover_color="#059669"
        )
        self.chk_all_scripts.pack(side="left", padx=(14, 10), pady=8)

        self.lbl_scripts_selected_count = ctk.CTkLabel(
            tb,
            text="(Đã chọn: 0 kịch bản)",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        self.lbl_scripts_selected_count.pack(side="left", padx=4, pady=8)

        # MASTER CTA BUTTON: TẠO VIDEO MẪU CHO CÁC MỤC ĐÃ CHỌN
        self.btn_batch_approve = ctk.CTkButton(
            tb,
            text="🎬 TẠO VIDEO MẪU CHO CÁC MỤC ĐÃ CHỌN",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#059669",
            hover_color="#10b981",
            height=34,
            corner_radius=6,
            command=self.action_batch_approve_and_render
        )
        self.btn_batch_approve.pack(side="left", padx=16, pady=8)

        # Filter Segmented / Option
        ctk.CTkLabel(tb, text="Lọc:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#64748b").pack(side="left", padx=(10, 4))
        self.combo_scripts_filter = ctk.CTkOptionMenu(
            tb,
            values=["Tất cả", "Chờ duyệt", "Đã duyệt", "Đã xuất video"],
            width=120,
            height=28,
            command=self._apply_scripts_filter
        )
        self.combo_scripts_filter.set("Tất cả")
        self.combo_scripts_filter.pack(side="left", padx=4)

        # Table Header Frame
        hdr = ctk.CTkFrame(c, fg_color="#182234", corner_radius=6, height=36)
        hdr.pack(fill="x", pady=(0, 4))
        hdr.grid_columnconfigure(0, minsize=40, weight=0)
        hdr.grid_columnconfigure(1, minsize=165, weight=0)
        hdr.grid_columnconfigure(2, weight=1)
        hdr.grid_columnconfigure(3, minsize=70, weight=0)
        hdr.grid_columnconfigure(4, minsize=125, weight=0)
        hdr.grid_columnconfigure(5, minsize=120, weight=0)
        hdr.grid_columnconfigure(6, minsize=240, weight=0)

        ctk.CTkLabel(hdr, text="", width=40).grid(row=0, column=0, padx=4, pady=8)
        ctk.CTkLabel(hdr, text="MÃ KỊCH BẢN", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="w").grid(row=0, column=1, sticky="w", padx=6, pady=8)
        ctk.CTkLabel(hdr, text="HOOK MỞ ĐẦU (3s ĐẦU TIÊN)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="w").grid(row=0, column=2, sticky="w", padx=6, pady=8)
        ctk.CTkLabel(hdr, text="SỐ Ý", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="center").grid(row=0, column=3, sticky="nsew", padx=4, pady=8)
        ctk.CTkLabel(hdr, text="TRẠNG THÁI DUYỆT", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="center").grid(row=0, column=4, sticky="nsew", padx=4, pady=8)
        ctk.CTkLabel(hdr, text="VIDEO 9:16", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="center").grid(row=0, column=5, sticky="nsew", padx=4, pady=8)
        ctk.CTkLabel(hdr, text="THAO TÁC", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="e").grid(row=0, column=6, sticky="e", padx=12, pady=8)

        # Table Scrollable Area
        self.scripts_table_scroll = ctk.CTkScrollableFrame(c, fg_color="#070a13", corner_radius=8)
        self.scripts_table_scroll.pack(fill="both", expand=True)

    def _init_subtab_posts_ui(self):
        c = self.subtab_posts_container

        # Toolbar Frame
        tb = ctk.CTkFrame(c, fg_color="#131b2e", corner_radius=8, height=50)
        tb.pack(fill="x", pady=(0, 8))

        self.lbl_posts_count = ctk.CTkLabel(
            tb,
            text="Tổng số bài viết/video gốc đã thu thập: 0 bài",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_posts_count.pack(side="left", padx=14, pady=10)

        # Table Header Frame
        hdr = ctk.CTkFrame(c, fg_color="#182234", corner_radius=6, height=36)
        hdr.pack(fill="x", pady=(0, 4))
        hdr.grid_columnconfigure(0, minsize=165, weight=0)
        hdr.grid_columnconfigure(1, minsize=130, weight=0)
        hdr.grid_columnconfigure(2, weight=1)
        hdr.grid_columnconfigure(3, minsize=150, weight=0)
        hdr.grid_columnconfigure(4, minsize=125, weight=0)
        hdr.grid_columnconfigure(5, minsize=180, weight=0)

        ctk.CTkLabel(hdr, text="MÃ BÀI (POST ID)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="w").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        ctk.CTkLabel(hdr, text="LINK FACEBOOK", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="center").grid(row=0, column=1, sticky="nsew", padx=4, pady=8)
        ctk.CTkLabel(hdr, text="CAPTION GỐC TỪ FACEBOOK", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="w").grid(row=0, column=2, sticky="w", padx=6, pady=8)
        ctk.CTkLabel(hdr, text="THỜI GIAN THU THẬP", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="center").grid(row=0, column=3, sticky="nsew", padx=4, pady=8)
        ctk.CTkLabel(hdr, text="TRẠNG THÁI", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="center").grid(row=0, column=4, sticky="nsew", padx=4, pady=8)
        ctk.CTkLabel(hdr, text="THAO TÁC", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", anchor="e").grid(row=0, column=5, sticky="e", padx=12, pady=8)

        # Table Scrollable Area
        self.posts_table_scroll = ctk.CTkScrollableFrame(c, fg_color="#070a13", corner_radius=8)
        self.posts_table_scroll.pack(fill="both", expand=True)

    def switch_scripts_subtab(self, subtab_key):
        self.active_scripts_subtab = subtab_key
        if subtab_key == "scripts":
            self.subtab_posts_container.pack_forget()
            self.subtab_scripts_container.pack(fill="both", expand=True)
            self.btn_subtab_scripts.configure(fg_color="#2563eb", text_color="#ffffff")
            self.btn_subtab_posts.configure(fg_color="#131b2e", text_color="#94a3b8")
            self.refresh_scripts_list()
        else:
            self.subtab_scripts_container.pack_forget()
            self.subtab_posts_container.pack(fill="both", expand=True)
            self.btn_subtab_posts.configure(fg_color="#2563eb", text_color="#ffffff")
            self.btn_subtab_scripts.configure(fg_color="#131b2e", text_color="#94a3b8")
            self.refresh_raw_posts_list()

    def _on_subtab_refresh_clicked(self):
        if self.active_scripts_subtab == "scripts":
            self.refresh_scripts_list()
        else:
            self.refresh_raw_posts_list()

    def refresh_scripts_list(self):
        for widget in self.scripts_table_scroll.winfo_children():
            widget.destroy()

        lbl_loading = ctk.CTkLabel(self.scripts_table_scroll, text="Đang đồng bộ danh sách kịch bản từ Google Sheet...", font=ctk.CTkFont(size=13), text_color="#94a3b8")
        lbl_loading.pack(pady=40)

        def _bg():
            scripts = self.sheet_bridge.fetch_scripts()
            try:
                if self.winfo_exists():
                    self.after(0, lambda: self._render_scripts_table(scripts))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def _render_scripts_table(self, scripts):
        self._cached_scripts = scripts
        for widget in self.scripts_table_scroll.winfo_children():
            widget.destroy()

        self.script_checkbox_vars.clear()
        self.chk_all_scripts_var.set(False)

        # Update tab badge text
        pending_cnt = sum(1 for s in scripts if s.get("Trạng thái duyệt") == "READY_FOR_REVIEW")
        badge_txt = f" ({pending_cnt} Chờ duyệt)" if pending_cnt > 0 else f" ({len(scripts)})"
        self.btn_subtab_scripts.configure(text=f"📋 V3 · Kịch Bản AI & Duyệt{badge_txt}")

        # Filter items
        filtered = self._get_filtered_scripts()
        if not filtered:
            msg = "Chưa có kịch bản nào trên Sheet.\nHãy tích chọn kênh ở trang Tổng quan và bấm 'BẮT ĐẦU QUÉT' để thu thập bài viết." if not scripts else "Không có kịch bản nào phù hợp với bộ lọc đã chọn."
            lbl_empty = ctk.CTkLabel(
                self.scripts_table_scroll,
                text=msg,
                font=ctk.CTkFont(size=13),
                text_color="#94a3b8"
            )
            lbl_empty.pack(pady=40)
            self._update_selected_count_label()
            return

        for idx, s in enumerate(filtered):
            row_idx = s.get("__row", 0)
            sid = s.get("Mã kịch bản") or s.get("Mã bài nguồn") or f"Kịch bản #{row_idx}"
            status = s.get("Trạng thái duyệt", "DRAFT")
            render_st = s.get("Trạng thái dựng", "")
            has_video = s.get("__has_video", False)
            video_path = s.get("__video_path", "")

            # Alternating background colors
            bg_col = "#0e1526" if idx % 2 == 0 else "#131b2e"
            border_col = "#f59e0b" if status == "READY_FOR_REVIEW" else ("#10b981" if status == "APPROVED" else "#1e293b")

            row_frame = ctk.CTkFrame(self.scripts_table_scroll, fg_color=bg_col, corner_radius=6, border_width=1, border_color=border_col)
            row_frame.pack(fill="x", pady=2, padx=2)

            row_frame.grid_columnconfigure(0, minsize=40, weight=0)
            row_frame.grid_columnconfigure(1, minsize=165, weight=0)
            row_frame.grid_columnconfigure(2, weight=1)
            row_frame.grid_columnconfigure(3, minsize=70, weight=0)
            row_frame.grid_columnconfigure(4, minsize=125, weight=0)
            row_frame.grid_columnconfigure(5, minsize=120, weight=0)
            row_frame.grid_columnconfigure(6, minsize=240, weight=0)

            # Col 0: Checkbox
            var = ctk.BooleanVar(value=(status == "READY_FOR_REVIEW"))
            self.script_checkbox_vars[sid] = var
            chk = ctk.CTkCheckBox(
                row_frame,
                text="",
                width=24,
                variable=var,
                command=self._on_script_select_change,
                fg_color="#10b981",
                hover_color="#059669"
            )
            chk.grid(row=0, column=0, padx=(10, 2), pady=8)

            # Col 1: Mã kịch bản
            short_sid = sid if len(sid) <= 22 else (sid[:10] + "..." + sid[-8:])
            lbl_sid = ctk.CTkLabel(row_frame, text=short_sid, font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8", anchor="w")
            lbl_sid.grid(row=0, column=1, sticky="w", padx=6, pady=8)

            # Col 2: Hook Mở Đầu
            hook_text = s.get("HOOK", "").strip() or "Chưa có Hook"
            lbl_hook = ctk.CTkLabel(row_frame, text=hook_text, font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc", anchor="w", wraplength=420)
            lbl_hook.grid(row=0, column=2, sticky="w", padx=6, pady=8)

            # Col 3: Số ý
            items_raw = s.get("Các ý (mỗi dòng một ý)", "")
            items_count = len([x for x in items_raw.splitlines() if x.strip()]) if isinstance(items_raw, str) else len(items_raw)
            badge_items = ctk.CTkLabel(row_frame, text=f" {items_count} ý ", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#1e293b", corner_radius=6, text_color="#cbd5e1")
            badge_items.grid(row=0, column=3, padx=4, pady=8)

            # Col 4: Trạng Thái Duyệt Badge
            st_text = "🟠 CHỜ DUYỆT" if status == "READY_FOR_REVIEW" else ("🟢 ĐÃ DUYỆT" if status == "APPROVED" else status)
            st_bg = "#78350f" if status == "READY_FOR_REVIEW" else ("#064e3b" if status == "APPROVED" else "#1e293b")
            st_fg = "#fef3c7" if status == "READY_FOR_REVIEW" else ("#d1fae5" if status == "APPROVED" else "#94a3b8")
            badge_status = ctk.CTkLabel(row_frame, text=f" {st_text} ", font=ctk.CTkFont(size=11, weight="bold"), fg_color=st_bg, text_color=st_fg, corner_radius=6)
            badge_status.grid(row=0, column=4, padx=4, pady=8)

            # Col 5: Video 9:16 Badge
            if has_video:
                v_text = "🟣 ĐÃ XUẤT"
                v_bg = "#581c87"
                v_fg = "#f3e8ff"
            elif render_st == "DONE":
                v_text = "🟣 ĐÃ XUẤT"
                v_bg = "#581c87"
                v_fg = "#f3e8ff"
            elif render_st == "RUNNING":
                v_text = "🟡 ĐANG DỰNG"
                v_bg = "#713f12"
                v_fg = "#fef08a"
            else:
                v_text = "⚪ CHƯA DỰNG"
                v_bg = "#1e293b"
                v_fg = "#64748b"
            badge_video = ctk.CTkLabel(row_frame, text=f" {v_text} ", font=ctk.CTkFont(size=10, weight="bold"), fg_color=v_bg, text_color=v_fg, corner_radius=6)
            badge_video.grid(row=0, column=5, padx=4, pady=8)

            # Col 6: Action Buttons
            btn_box = ctk.CTkFrame(row_frame, fg_color="transparent")
            btn_box.grid(row=0, column=6, sticky="e", padx=(4, 10), pady=6)

            # Button 1: Xem & Sửa
            ctk.CTkButton(
                btn_box,
                text="✏ Sửa",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                width=65,
                height=28,
                corner_radius=4,
                command=lambda sc=s: self.open_script_editor_dialog(sc)
            ).pack(side="left", padx=2)

            # Button 2: Tạo Video Mẫu
            ctk.CTkButton(
                btn_box,
                text="🎬 Tạo Mẫu",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#059669",
                hover_color="#10b981",
                width=85,
                height=28,
                corner_radius=4,
                command=lambda sc=s: self.action_single_approve_and_render(sc)
            ).pack(side="left", padx=2)

            # Button 3: Phát Video (if exists)
            if has_video and video_path:
                ctk.CTkButton(
                    btn_box,
                    text="▶ Phát",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color="#8b5cf6",
                    hover_color="#7c3aed",
                    width=65,
                    height=28,
                    corner_radius=4,
                    command=lambda vp=video_path: os.startfile(str(vp))
                ).pack(side="left", padx=2)

        self._update_selected_count_label()

    def _apply_scripts_filter(self, choice=None):
        self._render_scripts_table(self._cached_scripts)

    def _get_filtered_scripts(self):
        choice = self.combo_scripts_filter.get() if hasattr(self, "combo_scripts_filter") else "Tất cả"
        if choice == "Chờ duyệt":
            return [s for s in self._cached_scripts if s.get("Trạng thái duyệt") == "READY_FOR_REVIEW"]
        elif choice == "Đã duyệt":
            return [s for s in self._cached_scripts if s.get("Trạng thái duyệt") == "APPROVED"]
        elif choice == "Đã xuất video":
            return [s for s in self._cached_scripts if s.get("__has_video") or s.get("Trạng thái dựng") == "DONE"]
        return self._cached_scripts

    def _toggle_select_all_scripts(self):
        val = self.chk_all_scripts_var.get()
        for var in self.script_checkbox_vars.values():
            var.set(val)
        self._update_selected_count_label()

    def _on_script_select_change(self):
        self._update_selected_count_label()
        all_checked = all(var.get() for var in self.script_checkbox_vars.values()) if self.script_checkbox_vars else False
        self.chk_all_scripts_var.set(all_checked)

    def _update_selected_count_label(self):
        cnt = sum(1 for var in self.script_checkbox_vars.values() if var.get())
        total = len(self.script_checkbox_vars)
        self.lbl_scripts_selected_count.configure(text=f"(Đã chọn: {cnt}/{total} kịch bản)")
        if cnt > 0:
            self.btn_batch_approve.configure(text=f"🎬 TẠO VIDEO MẪU CHO {cnt} MỤC ĐÃ CHỌN")
        else:
            self.btn_batch_approve.configure(text="🎬 TẠO VIDEO MẪU CHO CÁC MỤC ĐÃ CHỌN")

    def action_batch_approve_and_render(self):
        selected_sids = [sid for sid, var in self.script_checkbox_vars.items() if var.get()]
        if not selected_sids:
            self.log_queue.put(("WARN", "⚠️ Bạn chưa chọn kịch bản nào! Hãy tích chọn ít nhất 1 ô để tạo video mẫu."))
            return

        selected_items = [s for s in self._cached_scripts if (s.get("Mã kịch bản") in selected_sids or s.get("Mã bài nguồn") in selected_sids)]
        if not selected_items:
            return

        def _bg():
            self.log_queue.put(("SYS", f"Đang gửi duyệt và tạo video mẫu cho {len(selected_items)} kịch bản đã chọn..."))
            ok_count, total = self.sheet_bridge.batch_approve_scripts(selected_items)
            if ok_count > 0:
                self.log_queue.put(("SYS", f"🟢 Đã gửi duyệt thành công {ok_count}/{total} kịch bản!"))
                self.log_queue.put(("SYS", "🚀 Đang kích hoạt Tool 2 để dựng video mẫu..."))
                self.trigger_render_once()
                self.after(2000, self.refresh_scripts_list)
            else:
                self.log_queue.put(("ERR", f"❌ Lỗi khi gửi duyệt các kịch bản đã chọn lên Google Sheet."))

        threading.Thread(target=_bg, daemon=True).start()

    def action_single_approve_and_render(self, script_data):
        sid = script_data.get("Mã kịch bản") or script_data.get("Mã bài nguồn", "kịch bản")
        def _bg():
            self.log_queue.put(("SYS", f"Đang gửi duyệt kịch bản '{sid}' để tạo video mẫu..."))
            ok_count, total = self.sheet_bridge.batch_approve_scripts([script_data])
            if ok_count > 0:
                self.log_queue.put(("SYS", f"🟢 Đã gửi duyệt thành công '{sid}'!"))
                self.log_queue.put(("SYS", "🚀 Đang kích hoạt Tool 2 để dựng video mẫu..."))
                self.trigger_render_once()
                self.after(2000, self.refresh_scripts_list)
            else:
                self.log_queue.put(("ERR", f"❌ Không thể gửi duyệt kịch bản '{sid}' lên Google Sheet."))

        threading.Thread(target=_bg, daemon=True).start()

    def open_script_editor_dialog(self, script_data):
        ScriptEditorDialog(
            self,
            script_data,
            on_save_approve=self.action_save_and_approve_from_editor,
            on_save_only=self.action_save_only_from_editor
        )

    def action_save_and_approve_from_editor(self, row_idx, script_dict):
        def _bg():
            self.log_queue.put(("SYS", f"Đang lưu sửa đổi và gửi duyệt kịch bản hàng #{row_idx}..."))
            ok = self.sheet_bridge.approve_script_with_edits(row_idx, script_dict)
            if ok:
                self.log_queue.put(("SYS", f"✅ Đã lưu và duyệt kịch bản #{row_idx}. Đang kích hoạt Tool 2 dựng video..."))
                self.trigger_render_once()
                self.after(2000, self.refresh_scripts_list)
            else:
                self.log_queue.put(("ERR", f"❌ Lỗi: Không thể lưu và duyệt kịch bản #{row_idx} lên Google Sheet."))
        threading.Thread(target=_bg, daemon=True).start()

    def action_save_only_from_editor(self, row_idx, script_dict):
        def _bg():
            self.log_queue.put(("SYS", f"Đang lưu sửa đổi kịch bản hàng #{row_idx} lên Google Sheet..."))
            ok = self.sheet_bridge.save_script_edits_only(row_idx, script_dict)
            if ok:
                self.log_queue.put(("SYS", f"✅ Đã lưu thành công kịch bản #{row_idx} lên Google Sheet."))
                self.after(1500, self.refresh_scripts_list)
            else:
                self.log_queue.put(("ERR", f"❌ Lỗi: Không thể lưu kịch bản #{row_idx} lên Google Sheet."))
        threading.Thread(target=_bg, daemon=True).start()

    def refresh_raw_posts_list(self):
        for widget in self.posts_table_scroll.winfo_children():
            widget.destroy()

        lbl_loading = ctk.CTkLabel(self.posts_table_scroll, text="Đang đồng bộ danh sách bài viết gốc từ Google Sheet...", font=ctk.CTkFont(size=13), text_color="#94a3b8")
        lbl_loading.pack(pady=40)

        def _bg():
            posts = self.sheet_bridge.fetch_raw_posts()
            try:
                if self.winfo_exists():
                    self.after(0, lambda: self._render_raw_posts_table(posts))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def _render_raw_posts_table(self, posts):
        self._cached_posts = posts
        for widget in self.posts_table_scroll.winfo_children():
            widget.destroy()

        self.lbl_posts_count.configure(text=f"Tổng số bài viết/video gốc đã thu thập: {len(posts)} bài")
        self.btn_subtab_posts.configure(text=f"📥 V3 · Bài Viết & Video Gốc ({len(posts)})")

        if not posts:
            lbl_empty = ctk.CTkLabel(
                self.posts_table_scroll,
                text="Chưa có bài viết nào được thu thập.\nHãy bật quét kênh ở trang Tổng quan để thu thập bài viết mới từ Facebook.",
                font=ctk.CTkFont(size=13),
                text_color="#94a3b8"
            )
            lbl_empty.pack(pady=40)
            return

        for idx, p in enumerate(posts):
            pid = p.get("Mã bài") or f"Post #{idx+1}"
            post_url = p.get("Link video gốc", "")
            caption = p.get("Caption gốc", "").strip() or "Không có caption"
            collected_at = p.get("Lần thu thập", "") or p.get("Ngày đăng", "")
            if len(collected_at) >= 16 and "T" in collected_at:
                try:
                    dt = datetime.datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
                    time_str = dt.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    time_str = collected_at[:16]
            else:
                time_str = collected_at[:16]

            st = p.get("Trạng thái phân tích", "DONE")
            has_file = p.get("__has_video", False)

            bg_col = "#0e1526" if idx % 2 == 0 else "#131b2e"
            border_col = "#10b981" if st == "DONE" else ("#ef4444" if st == "ERROR" else "#1e293b")

            row_frame = ctk.CTkFrame(self.posts_table_scroll, fg_color=bg_col, corner_radius=6, border_width=1, border_color=border_col)
            row_frame.pack(fill="x", pady=2, padx=2)

            row_frame.grid_columnconfigure(0, minsize=165, weight=0)
            row_frame.grid_columnconfigure(1, minsize=130, weight=0)
            row_frame.grid_columnconfigure(2, weight=1)
            row_frame.grid_columnconfigure(3, minsize=150, weight=0)
            row_frame.grid_columnconfigure(4, minsize=125, weight=0)
            row_frame.grid_columnconfigure(5, minsize=180, weight=0)

            # Col 0: Mã bài
            ctk.CTkLabel(row_frame, text=pid, font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8", anchor="w").grid(row=0, column=0, sticky="w", padx=10, pady=8)

            # Col 1: Link FB Button
            if post_url:
                ctk.CTkButton(
                    row_frame,
                    text="🔗 Mở Facebook",
                    font=ctk.CTkFont(size=11),
                    fg_color="#1e293b",
                    hover_color="#2563eb",
                    width=110,
                    height=26,
                    corner_radius=4,
                    command=lambda u=post_url: webbrowser.open(u)
                ).grid(row=0, column=1, padx=4, pady=8)
            else:
                ctk.CTkLabel(row_frame, text="-", text_color="#64748b").grid(row=0, column=1, padx=4, pady=8)

            # Col 2: Caption
            short_cap = caption.replace("\n", " ")
            if len(short_cap) > 75:
                short_cap = short_cap[:72] + "..."
            ctk.CTkLabel(row_frame, text=short_cap, font=ctk.CTkFont(size=11), text_color="#cbd5e1", anchor="w").grid(row=0, column=2, sticky="w", padx=6, pady=8)

            # Col 3: Thời gian
            ctk.CTkLabel(row_frame, text=time_str, font=ctk.CTkFont(size=11), text_color="#94a3b8", anchor="center").grid(row=0, column=3, sticky="nsew", padx=4, pady=8)

            # Col 4: Trạng thái
            st_text = "🟢 ĐÃ BÓC TÁCH" if st == "DONE" else ("🔴 LỖI" if st == "ERROR" else st)
            st_bg = "#064e3b" if st == "DONE" else ("#7f1d1d" if st == "ERROR" else "#1e293b")
            st_fg = "#d1fae5" if st == "DONE" else ("#fecaca" if st == "ERROR" else "#94a3b8")
            ctk.CTkLabel(row_frame, text=f" {st_text} ", font=ctk.CTkFont(size=10, weight="bold"), fg_color=st_bg, text_color=st_fg, corner_radius=6).grid(row=0, column=4, padx=4, pady=8)

            # Col 5: Thao tác
            btn_box = ctk.CTkFrame(row_frame, fg_color="transparent")
            btn_box.grid(row=0, column=5, sticky="e", padx=(4, 10), pady=6)

            ctk.CTkButton(
                btn_box,
                text="📄 Chi Tiết",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                width=80,
                height=28,
                corner_radius=4,
                command=lambda pd=p: self.open_raw_post_detail_dialog(pd)
            ).pack(side="left", padx=2)

            if has_file:
                dl_path = p.get("File video trên máy", "")
                ctk.CTkButton(
                    btn_box,
                    text="▶ Video",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color="#8b5cf6",
                    hover_color="#7c3aed",
                    width=65,
                    height=28,
                    corner_radius=4,
                    command=lambda vp=dl_path: os.startfile(str(vp))
                ).pack(side="left", padx=2)

    def open_raw_post_detail_dialog(self, post_data):
        RawPostDetailDialog(self, post_data)

    # ================= VIEW 3: RENDERS GALLERY =================
    def _build_renders_view(self):
        v = self.views["renders"]

        top_bar = ctk.CTkFrame(v, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 10))

        title = ctk.CTkLabel(top_bar, text="🎬 KHO VIDEO 9:16 THÀNH PHẨM", font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(side="left")

        btn_folder = ctk.CTkButton(
            top_bar,
            text="📁 Mở Thư Mục Chứa Video",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#475569",
            hover_color="#334155",
            width=180,
            height=34,
            command=self.open_renders_folder
        )
        btn_folder.pack(side="right", padx=(8, 0))

        btn_refresh = ctk.CTkButton(
            top_bar,
            text="🔄 Làm Mới",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            width=100,
            height=34,
            command=self.refresh_renders_list
        )
        btn_refresh.pack(side="right")

        self.renders_scroll = ctk.CTkScrollableFrame(v, fg_color="#070a13", corner_radius=10)
        self.renders_scroll.pack(fill="both", expand=True)

    def refresh_renders_list(self):
        for widget in self.renders_scroll.winfo_children():
            widget.destroy()

        renders_dir = ROOT / "data" / "renders"
        if not renders_dir.exists():
            lbl = ctk.CTkLabel(self.renders_scroll, text="Chưa có video thành phẩm nào được dựng.", font=ctk.CTkFont(size=13), text_color="#94a3b8")
            lbl.pack(pady=40)
            return

        videos = []
        for d in renders_dir.iterdir():
            if d.is_dir():
                vpath = d / "video.mp4"
                if vpath.exists():
                    stat = vpath.stat()
                    meta = {}
                    if (d / "render.json").exists():
                        try:
                            meta = json.loads((d / "render.json").read_text(encoding="utf-8"))
                        except Exception:
                            pass
                    videos.append({
                        "dir": d,
                        "path": vpath,
                        "size_mb": stat.st_size / (1024 * 1024),
                        "mtime": stat.st_mtime,
                        "time_str": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M:%S"),
                        "meta": meta
                    })

        videos.sort(key=lambda x: x["mtime"], reverse=True)

        if not videos:
            lbl = ctk.CTkLabel(self.renders_scroll, text="Chưa có video thành phẩm nào được dựng.", font=ctk.CTkFont(size=13), text_color="#94a3b8")
            lbl.pack(pady=40)
            return

        for v in videos:
            card = ctk.CTkFrame(self.renders_scroll, fg_color="#131b2e", corner_radius=10, border_width=1, border_color="#1f293d")
            card.pack(fill="x", padx=6, pady=8)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=14, pady=(12, 4))

            title = v["dir"].name
            hook_text = v["meta"].get("hook", "")
            title_display = f"📹 {hook_text}" if hook_text else f"📹 {title}"
            ctk.CTkLabel(top_row, text=title_display, font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8", wraplength=650, justify="left").pack(side="left")

            lbl_time = ctk.CTkLabel(top_row, text=f"⏱ {v['time_str']} • {v['size_mb']:.1f} MB", font=ctk.CTkFont(size=11), text_color="#94a3b8")
            lbl_time.pack(side="right")

            # Video Specs
            lbl_info = ctk.CTkLabel(
                card,
                text="Chuẩn tỷ lệ 9:16 dọc (720x1280) • Nhạc không bản quyền • Chữ ký Chú Dũng Sức Khỏe",
                font=ctk.CTkFont(size=11),
                text_color="#64748b"
            )
            lbl_info.pack(anchor="w", padx=14, pady=2)

            # Caption Preview (For easy copy & paste)
            caption_text = v["meta"].get("caption", "").strip()
            if caption_text:
                cap_box = ctk.CTkFrame(card, fg_color="#0b0f19", corner_radius=6)
                cap_box.pack(fill="x", padx=14, pady=6)
                ctk.CTkLabel(cap_box, text=f"💬 Caption: {caption_text}", font=ctk.CTkFont(size=11), text_color="#cbd5e1", wraplength=850, justify="left").pack(anchor="w", padx=10, pady=6)

            # Action Buttons
            btn_box = ctk.CTkFrame(card, fg_color="transparent")
            btn_box.pack(fill="x", padx=14, pady=(6, 12))

            ctk.CTkButton(
                btn_box,
                text="▶ PHÁT VIDEO",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#10b981",
                hover_color="#059669",
                height=34,
                command=lambda p=v["path"]: os.startfile(str(p))
            ).pack(side="left", padx=4)

            if caption_text:
                ctk.CTkButton(
                    btn_box,
                    text="📋 SAO CHÉP CAPTION & TAGS",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    fg_color="#2563eb",
                    hover_color="#1d4ed8",
                    height=34,
                    command=lambda c=caption_text: self.copy_caption_to_clipboard(c)
                ).pack(side="left", padx=4)

            ctk.CTkButton(
                btn_box,
                text="📂 Mở Thư Mục Chứa",
                font=ctk.CTkFont(size=12),
                fg_color="#475569",
                hover_color="#334155",
                height=34,
                command=lambda d=v["dir"]: os.startfile(str(d))
            ).pack(side="left", padx=4)

    def copy_caption_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log_queue.put(("SYS", "📋 Đã sao chép Caption & Hashtags vào bộ nhớ tạm. Bạn có thể dán (Ctrl+V) đăng bài ngay."))

    # ================= VIEW 4: SETTINGS & DOCTOR =================
    def _build_settings_view(self):
        v = self.views["settings"]

        title = ctk.CTkLabel(v, text="⚙ CÀI ĐẶT & KẾT NỐI HỆ THỐNG", font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(anchor="w", pady=(0, 14))

        box = ctk.CTkFrame(v, fg_color="#131b2e", corner_radius=10, border_width=1, border_color="#1f293d")
        box.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(box, text="🔑 MÃ GHÉP NỐI CHROME EXTENSION (LOCAL API TOKEN)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=16, pady=(14, 4))

        sec_file = ROOT / ".local" / "secrets.json"
        token = "Chưa có"
        if sec_file.exists():
            try:
                token = json.loads(sec_file.read_text(encoding="utf-8")).get("local_api_token", "")
            except Exception:
                pass

        token_row = ctk.CTkFrame(box, fg_color="transparent")
        token_row.pack(fill="x", padx=14, pady=(0, 14))

        self.entry_token = ctk.CTkEntry(token_row, font=ctk.CTkFont(family="Consolas", size=12), width=500, fg_color="#0b0f19")
        self.entry_token.insert(0, token)
        self.entry_token.configure(state="readonly")
        self.entry_token.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            token_row,
            text="📋 Sao Chép Mã",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            command=lambda: [self.clipboard_clear(), self.clipboard_append(token), self.log_queue.put(("SYS", "Đã sao chép local_api_token."))]
        ).pack(side="left")

        # Configuration Parameters
        cfg_box = ctk.CTkFrame(v, fg_color="#131b2e", corner_radius=10, border_width=1, border_color="#1f293d")
        cfg_box.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(cfg_box, text="🛠 THÔNG SỐ CẤU HÌNH", font=ctk.CTkFont(size=13, weight="bold"), text_color="#cbd5e1").pack(anchor="w", padx=16, pady=(14, 8))

        params = [
            ("Google Sheet ID", self.config.get("spreadsheet_id", "")),
            ("Thương hiệu đầu ra (Chữ ký)", self.config.get("default_signature", "")),
            ("Gemini Model", self.config.get("gemini_model", "auto (gemini-3.6-flash)")),
            ("Chu kỳ lặp (giây)", str(self.config.get("poll_seconds", 30))),
            ("Độ phân giải video", f"{self.config.get('width', 720)} x {self.config.get('height', 1280)} (Chuẩn 9:16)")
        ]
        for p_name, p_val in params:
            row = ctk.CTkFrame(cfg_box, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(row, text=p_name + ":", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94a3b8", width=220, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=p_val, font=ctk.CTkFont(size=12), text_color="#ffffff").pack(side="left")

        # Background Media Management Section
        bg_box = ctk.CTkFrame(v, fg_color="#131b2e", corner_radius=10, border_width=1, border_color="#1f293d")
        bg_box.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(bg_box, text="🎬 KHO VIDEO NỀN 9:16 (12 VIDEO SẴN SÀNG)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#34d399").pack(anchor="w", padx=16, pady=(14, 4))

        bg_desc = (
            "Hệ thống đã nạp sẵn 12 video nền chất lượng cao (Tia nắng rừng, Thác nước, Rừng tre thiền định,\n"
            "Nắng sớm, Sóng biển, Sương mù núi thu, Giọt sương lá, Đồi thông, Tầng mây, Hoàng hôn, Suối đá, Đại dương).\n"
            "Chế độ: Tự động xoay tua đa dạng (mỗi kịch bản có 1 video nền riêng biệt, không bị trùng lặp)."
        )
        ctk.CTkLabel(bg_box, text=bg_desc, font=ctk.CTkFont(size=11), text_color="#94a3b8", justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        bg_btn_row = ctk.CTkFrame(bg_box, fg_color="transparent")
        bg_btn_row.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkButton(
            bg_btn_row,
            text="📁 Mở Thư Mục Video Nền",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#059669",
            hover_color="#10b981",
            command=lambda: os.startfile(str(ROOT / "assets" / "backgrounds"))
        ).pack(side="left", padx=(0, 8))

        # Background Music Management Section
        music_box = ctk.CTkFrame(v, fg_color="#131b2e", corner_radius=10, border_width=1, border_color="#1f293d")
        music_box.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(music_box, text="🎵 KHO NHẠC NỀN 9:16 & CẤU HÌNH ÂM LƯỢNG (10 BẢN NHẠC SẴN SÀNG)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#ec4899").pack(anchor="w", padx=16, pady=(14, 4))

        music_desc = (
            "Hệ thống đã nạp sẵn 10 bản nhạc nền bản quyền mở CC0 (Thiền định, Piano cảm hứng, Nắng mai,\n"
            "Ánh sáng hy vọng, Bay bổng, Guitar mộc mạc, Sáo trúc thanh tao, Piano sâu lắng, Hoàng hôn, Ambient gốc).\n"
            "Chế độ: Tự động đổi nhạc đa dạng theo từng kịch bản (xoay tua ngẫu nhiên, không lo trùng lặp)."
        )
        ctk.CTkLabel(music_box, text=music_desc, font=ctk.CTkFont(size=11), text_color="#94a3b8", justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        # 2-column layout for Default Music & Volume
        m_grid = ctk.CTkFrame(music_box, fg_color="transparent")
        m_grid.pack(fill="x", padx=16, pady=(0, 10))
        m_grid.grid_columnconfigure(0, weight=6)
        m_grid.grid_columnconfigure(1, weight=4)

        # Col 1: Default Music
        mc1 = ctk.CTkFrame(m_grid, fg_color="transparent")
        mc1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(mc1, text="🎵 Nhạc nền mặc định toàn hệ thống:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ec4899").pack(anchor="w", pady=(0, 3))
        self.settings_music_options = [
            "🎲 Tự động đổi nhạc (Xoay tua đa dạng)",
            "01 · Thiền định an yên (Infinite Peace)",
            "02 · Piano truyền cảm hứng (Lovely Piano)",
            "03 · Nắng mai khởi đầu (Adding The Sun)",
            "04 · Ánh sáng hy vọng (See The Light)",
            "05 · Bay bổng khát vọng (Inventing Flight)",
            "06 · Guitar mộc mạc (Mellow Acoustic)",
            "07 · Sáo trúc thanh tao (Chinese Flute)",
            "08 · Piano sâu lắng (Nostalgic Piano)",
            "09 · Buổi chiều êm ả (Sunset Melody)",
            "10 · Nhạc nền gốc mặc định (Original Ambient)"
        ]
        self.settings_combo_music = ctk.CTkOptionMenu(mc1, values=self.settings_music_options, fg_color="#0b0f19", button_color="#1e293b", text_color="#ffffff", dropdown_fg_color="#131b2e")
        cur_def_music = str(self.config.get("default_music", "auto"))
        m_idx = 0
        if cur_def_music != "auto":
            for i_m, m_opt in enumerate(self.settings_music_options):
                if cur_def_music in m_opt or (len(cur_def_music) >= 2 and cur_def_music[:2] == m_opt[:2]):
                    m_idx = i_m
                    break
        self.settings_combo_music.set(self.settings_music_options[m_idx])
        self.settings_combo_music.pack(fill="x")

        # Col 2: Volume
        mc2 = ctk.CTkFrame(m_grid, fg_color="transparent")
        mc2.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(mc2, text="🔊 Âm lượng nhạc nền:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(0, 3))
        self.settings_volume_options = [
            "10% (Rất nhẹ - Ưu tiên rõ giọng)",
            "15% (Nhẹ nhàng êm dịu)",
            "18% (Chuẩn Reels/TikTok - Khuyên dùng)",
            "25% (Rõ nét, sôi động)",
            "30% (Năng lượng cao)"
        ]
        self.settings_combo_volume = ctk.CTkOptionMenu(mc2, values=self.settings_volume_options, fg_color="#0b0f19", button_color="#1e293b", text_color="#ffffff", dropdown_fg_color="#131b2e")
        cur_vol = float(self.config.get("music_volume", 0.18))
        v_idx = 2
        if cur_vol <= 0.11:
            v_idx = 0
        elif cur_vol <= 0.16:
            v_idx = 1
        elif cur_vol <= 0.20:
            v_idx = 2
        elif cur_vol <= 0.27:
            v_idx = 3
        else:
            v_idx = 4
        self.settings_combo_volume.set(self.settings_volume_options[v_idx])
        self.settings_combo_volume.pack(fill="x")

        # Buttons row
        m_btn_row = ctk.CTkFrame(music_box, fg_color="transparent")
        m_btn_row.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkButton(
            m_btn_row,
            text="📁 Mở Thư Mục Nhạc Nền",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#db2777",
            hover_color="#be185d",
            command=lambda: os.startfile(str(ROOT / "assets" / "music"))
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            m_btn_row,
            text="💾 Lưu Cài Đặt Nhạc Nền",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            command=self._save_default_music_settings
        ).pack(side="left")

        # Typography & Color Theme Defaults Section
        style_box = ctk.CTkFrame(v, fg_color="#131b2e", corner_radius=10, border_width=1, border_color="#1f293d")
        style_box.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(style_box, text="🎨 CẤU HÌNH CỠ CHỮ & MÀU SẮC MẶC ĐỊNH (TOÀN HỆ THỐNG)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#f59e0b").pack(anchor="w", padx=16, pady=(14, 4))

        style_desc = (
            "Cấu hình này sẽ được áp dụng tự động cho mọi video dựng mới khi không có tùy chỉnh riêng.\n"
            "Bạn cũng có thể tùy chỉnh riêng cho từng video tại mục 'Duyệt & Sửa Kịch Bản'."
        )
        ctk.CTkLabel(style_box, text=style_desc, font=ctk.CTkFont(size=11), text_color="#94a3b8", justify="left").pack(anchor="w", padx=16, pady=(0, 12))

        # 2-column layout for Size Mode & Theme
        s_grid = ctk.CTkFrame(style_box, fg_color="transparent")
        s_grid.pack(fill="x", padx=16, pady=(0, 10))
        s_grid.grid_columnconfigure(0, weight=1)
        s_grid.grid_columnconfigure(1, weight=1)

        # Col 1: Default Size Mode
        c1 = ctk.CTkFrame(s_grid, fg_color="transparent")
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(c1, text="📐 Cỡ chữ & Bố cục mặc định:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(0, 3))
        self.settings_size_options = [
            "⚡ Tự động (Thích ứng theo số ý - Khuyên dùng)",
            "🔍 Lớn (+20% - Nổi bật, ít ý)",
            "📐 Vừa (Kích cỡ chuẩn cân đối)",
            "🔎 Nhỏ (-15% - Dành cho nội dung dài)"
        ]
        self.settings_combo_size = ctk.CTkOptionMenu(c1, values=self.settings_size_options, fg_color="#0b0f19", button_color="#1e293b", text_color="#ffffff", dropdown_fg_color="#131b2e")
        cur_size = str(self.config.get("font_size_mode", "auto")).lower()
        s_idx = 0
        if "large" in cur_size:
            s_idx = 1
        elif "medium" in cur_size:
            s_idx = 2
        elif "small" in cur_size:
            s_idx = 3
        self.settings_combo_size.set(self.settings_size_options[s_idx])
        self.settings_combo_size.pack(fill="x")

        # Col 2: Default Color Theme
        c2 = ctk.CTkFrame(s_grid, fg_color="transparent")
        c2.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(c2, text="🌈 Bộ màu giao diện mặc định:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#f59e0b").pack(anchor="w", pady=(0, 3))
        self.settings_theme_options = [
            "🌟 Vàng Kim Sang Trọng (Tiêu chuẩn)",
            "🌊 Xanh Biển Hiện Đại (Công nghệ/Mát mẻ)",
            "🌿 Xanh Ngọc Sức Khỏe (Sức khỏe/Thiên nhiên)",
            "🌸 Đỏ Hồng Nổi Bật (Cảnh báo/Thu hút)",
            "⚪ Trắng Tinh Tế (Tối giản thanh lịch)"
        ]
        self.settings_combo_theme = ctk.CTkOptionMenu(c2, values=self.settings_theme_options, fg_color="#0b0f19", button_color="#1e293b", text_color="#ffffff", dropdown_fg_color="#131b2e", command=self._on_settings_theme_changed)
        cur_theme = str(self.config.get("color_theme", "gold")).lower()
        t_idx = 0
        if "cyan" in cur_theme:
            t_idx = 1
        elif "emerald" in cur_theme:
            t_idx = 2
        elif "ruby" in cur_theme:
            t_idx = 3
        elif "white" in cur_theme:
            t_idx = 4
        self.settings_combo_theme.set(self.settings_theme_options[t_idx])
        self.settings_combo_theme.pack(fill="x")

        # Fine-tune hex colors
        fine_box = ctk.CTkFrame(style_box, fg_color="#0b0f19", corner_radius=6, border_width=1, border_color="#1f293d")
        fine_box.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(fine_box, text="🎨 Ghi Đè Mã Màu Chi Tiết (Tùy chọn mã Hex / Bấm nút để chọn):", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(anchor="w", padx=10, pady=(6, 2))

        fine_row = ctk.CTkFrame(fine_box, fg_color="transparent")
        fine_row.pack(fill="x", padx=8, pady=(0, 8))
        fine_row.grid_columnconfigure(0, weight=1)
        fine_row.grid_columnconfigure(1, weight=1)

        # Hook color fine-tune
        h_box = ctk.CTkFrame(fine_row, fg_color="transparent")
        h_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(h_box, text="Màu tiêu đề (Hook):", font=ctk.CTkFont(size=10), text_color="#cbd5e1").pack(anchor="w")
        h_sub = ctk.CTkFrame(h_box, fg_color="transparent")
        h_sub.pack(fill="x", pady=(2, 0))
        self.settings_entry_hook_col = ctk.CTkEntry(h_sub, font=ctk.CTkFont(family="Consolas", size=10), fg_color="#070a13", text_color="#ffffff", height=28)
        self.settings_entry_hook_col.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.settings_entry_hook_col.insert(0, self.config.get("hook_color") or THEMES.get(cur_theme, THEMES["gold"])["hook_color"])
        ctk.CTkButton(h_sub, text="🎨 Chọn", width=54, height=28, font=ctk.CTkFont(size=10, weight="bold"), fg_color="#334155", hover_color="#475569", command=self._pick_settings_hook_color).pack(side="right")

        # Item color fine-tune
        i_box = ctk.CTkFrame(fine_row, fg_color="transparent")
        i_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(i_box, text="Màu chữ nội dung:", font=ctk.CTkFont(size=10), text_color="#cbd5e1").pack(anchor="w")
        i_sub = ctk.CTkFrame(i_box, fg_color="transparent")
        i_sub.pack(fill="x", pady=(2, 0))
        self.settings_entry_item_col = ctk.CTkEntry(i_sub, font=ctk.CTkFont(family="Consolas", size=10), fg_color="#070a13", text_color="#ffffff", height=28)
        self.settings_entry_item_col.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.settings_entry_item_col.insert(0, self.config.get("item_color") or THEMES.get(cur_theme, THEMES["gold"])["item_color"])
        ctk.CTkButton(i_sub, text="🎨 Chọn", width=54, height=28, font=ctk.CTkFont(size=10, weight="bold"), fg_color="#334155", hover_color="#475569", command=self._pick_settings_item_color).pack(side="right")

        # Save Button
        ctk.CTkButton(
            style_box,
            text="💾 Lưu Cấu Hình Giao Diện Mặc Định",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=34,
            command=self._save_default_style_settings
        ).pack(anchor="w", padx=16, pady=(0, 14))

        # Doctor Check Button
        doc_btn = ctk.CTkButton(
            v,
            text="🩺 Chẩn Đoán Toàn Bộ Hệ Thống (Doctor Check)",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=40,
            command=self.run_doctor_check
        )
        doc_btn.pack(fill="x", pady=(0, 14))

    def _pick_settings_hook_color(self):
        curr = self.settings_entry_hook_col.get().strip() or "#facc15"
        res = colorchooser.askcolor(color=curr, title="Chọn màu tiêu đề mặc định")
        if res and res[1]:
            self.settings_entry_hook_col.delete(0, "end")
            self.settings_entry_hook_col.insert(0, res[1].upper())

    def _pick_settings_item_color(self):
        curr = self.settings_entry_item_col.get().strip() or "#ffffff"
        res = colorchooser.askcolor(color=curr, title="Chọn màu chữ nội dung mặc định")
        if res and res[1]:
            self.settings_entry_item_col.delete(0, "end")
            self.settings_entry_item_col.insert(0, res[1].upper())

    def _on_settings_theme_changed(self, choice):
        tkey = "gold"
        if "Xanh Biển" in choice:
            tkey = "cyan"
        elif "Xanh Ngọc" in choice:
            tkey = "emerald"
        elif "Đỏ Hồng" in choice:
            tkey = "ruby"
        elif "Trắng" in choice:
            tkey = "white"
        th = THEMES.get(tkey, THEMES["gold"])
        self.settings_entry_hook_col.delete(0, "end")
        self.settings_entry_hook_col.insert(0, th["hook_color"])
        self.settings_entry_item_col.delete(0, "end")
        self.settings_entry_item_col.insert(0, th["item_color"])

    def _save_default_music_settings(self):
        m_choice = self.settings_combo_music.get()
        chosen_m = "auto"
        for k in ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10"):
            if m_choice.startswith(k):
                chosen_m = k
                break

        v_choice = self.settings_combo_volume.get()
        vol = 0.18
        if "10%" in v_choice:
            vol = 0.10
        elif "15%" in v_choice:
            vol = 0.15
        elif "18%" in v_choice:
            vol = 0.18
        elif "25%" in v_choice:
            vol = 0.25
        elif "30%" in v_choice:
            vol = 0.30

        save_config({
            "default_music": chosen_m,
            "music_volume": vol
        })
        self.config = load_config()
        self.log_queue.put(("SYS", f"✅ Đã lưu cấu hình nhạc nền mặc định: Nhạc={chosen_m}, Âm lượng={int(vol*100)}%"))

    def _save_default_style_settings(self):
        size_str = self.settings_combo_size.get()
        chosen_size = "auto"
        if "Lớn" in size_str:
            chosen_size = "large"
        elif "Vừa" in size_str:
            chosen_size = "medium"
        elif "Nhỏ" in size_str:
            chosen_size = "small"

        theme_str = self.settings_combo_theme.get()
        chosen_theme = "gold"
        if "Xanh Biển" in theme_str:
            chosen_theme = "cyan"
        elif "Xanh Ngọc" in theme_str:
            chosen_theme = "emerald"
        elif "Đỏ Hồng" in theme_str:
            chosen_theme = "ruby"
        elif "Trắng" in theme_str:
            chosen_theme = "white"

        hook_col = self.settings_entry_hook_col.get().strip()
        item_col = self.settings_entry_item_col.get().strip()

        updates = {
            "font_size_mode": chosen_size,
            "color_theme": chosen_theme,
            "hook_color": hook_col,
            "item_color": item_col
        }
        save_config(updates)
        self.config = load_config()
        self.log_queue.put(("SYS", f"✅ Đã lưu cấu hình giao diện mặc định vào config.json: Cỡ chữ={chosen_size}, Chủ đề={chosen_theme}"))

    def run_doctor_check(self):
        def _bg():
            self.log_queue.put(("SYS", "Bắt đầu chẩn đoán hệ thống (python configure.py --doctor)..."))
            res = subprocess.run([sys.executable, "configure.py", "--doctor"], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
            for line in res.stdout.splitlines():
                if line.strip():
                    self.log_queue.put(("SYS", line.strip()))

        threading.Thread(target=_bg, daemon=True).start()

    # ================= LOG PROCESSING & STATS =================
    def _process_logs(self):
        while not self.log_queue.empty():
            tag, msg = self.log_queue.get_nowait()
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            full_line = f"[{now_str}] [{tag}] {msg}\n"

            self.dash_log_text.insert("end", full_line)
            self.dash_log_text.see("end")

        self.after(100, self._process_logs)

    def _refresh_dashboard_stats(self):
        def _bg():
            stats = self.sheet_bridge.fetch_stats()
            try:
                if self.winfo_exists():
                    self.after(0, lambda: self._update_stat_labels(stats))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()
        # Refresh every 30 seconds
        try:
            if self.winfo_exists():
                self.after(30000, self._refresh_dashboard_stats)
        except Exception:
            pass

    def _update_stat_labels(self, stats):
        if "posts" in stats:
            self.stat_cards["posts"].configure(text=str(stats["posts"]))
        if "pending_scripts" in stats:
            self.stat_cards["pending_scripts"].configure(text=str(stats["pending_scripts"]))
        if "renders" in stats:
            self.stat_cards["renders"].configure(text=str(stats["renders"]))

    # ================= TOOL PROCESS CONTROL =================
    def toggle_all_tools(self):
        if self.tool1.running or self.tool2.running:
            self.stop_all_tools()
        else:
            self.start_all_tools()

    def start_all_tools(self):
        self.tool1.start()
        self.tool2.start()
        self.btn_master.configure(text="⏹ DỪNG HỆ THỐNG", fg_color="#ef4444", hover_color="#dc2626")

    def stop_all_tools(self):
        self.tool1.stop()
        self.tool2.stop()
        self.btn_master.configure(text="▶ BẬT TỰ ĐỘNG TOÀN BỘ", fg_color="#10b981", hover_color="#059669")

    # ================= QUICK ACTIONS =================
    def open_google_sheet(self):
        sid = self.config.get("spreadsheet_id", "")
        if sid:
            webbrowser.open(f"https://docs.google.com/spreadsheets/d/{sid}/edit")

    def open_renders_folder(self):
        rdir = ROOT / "data" / "renders"
        rdir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(rdir))

    def trigger_render_once(self):
        if not self.tool2.running:
            def _bg():
                self.log_queue.put(("TOOL2", "Đang kiểm tra và dựng các video đã duyệt..."))
                res = subprocess.run([sys.executable, "-u", "-X", "utf8", "tool2.py", "--once"], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
                for line in res.stdout.splitlines():
                    if line.strip():
                        self.log_queue.put(("TOOL2", line.strip()))
                self._refresh_dashboard_stats()

            threading.Thread(target=_bg, daemon=True).start()
        else:
            self.log_queue.put(("SYS", "ℹ Tool 2 đang chạy tự động dưới nền rồi, hệ thống sẽ tự động dựng ngay khi có kịch bản APPROVED."))

    def copy_logs(self):
        text = self.dash_log_text.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log_queue.put(("SYS", "Đã sao chép nhật ký vào Clipboard."))

    def clear_logs(self):
        self.dash_log_text.delete("1.0", "end")

    def on_closing(self):
        self.tool1.stop()
        self.tool2.stop()
        self.destroy()


def main():
    app = VideoStudioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
