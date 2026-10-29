"""Measured Vietnamese typography with pagination, dynamic adaptive centering, and customizable styling."""
from dataclasses import dataclass
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass
class TextBlock:
    x: int
    y: int
    width: int
    height: int
    lines: list[str]
    font_size: int
    line_height: int


@dataclass
class ItemBlock:
    index: int
    block: TextBlock


@dataclass
class Page:
    hook: TextBlock
    brand: TextBlock
    items: list[ItemBlock]


@dataclass
class Layout:
    width: int
    height: int
    pages: list[Page]
    durations: list[float]
    duration: float
    style: dict = None


THEMES = {
    "gold": {
        "name": "Vàng Kim Sang Trọng",
        "hook_color": "#facc15",
        "hook_stroke": "#78350f",
        "item_color": "#ffffff",
        "item_stroke": "#000000",
        "badge_fill": "#d97706",
        "badge_outline": "#ffffff",
        "badge_text": "#ffffff",
        "brand_color": "#facc15",
        "card_bg": (15, 23, 42, 195),
        "card_border": "#fbbf24",
        "use_cards": True
    },
    "cyan": {
        "name": "Xanh Biển Hiện Đại",
        "hook_color": "#38bdf8",
        "hook_stroke": "#0369a1",
        "item_color": "#ffffff",
        "item_stroke": "#000000",
        "badge_fill": "#0284c7",
        "badge_outline": "#ffffff",
        "badge_text": "#ffffff",
        "brand_color": "#38bdf8",
        "card_bg": (15, 23, 42, 195),
        "card_border": "#38bdf8",
        "use_cards": True
    },
    "emerald": {
        "name": "Xanh Ngọc Sức Khỏe",
        "hook_color": "#34d399",
        "hook_stroke": "#065f46",
        "item_color": "#f0fdf4",
        "item_stroke": "#000000",
        "badge_fill": "#059669",
        "badge_outline": "#ffffff",
        "badge_text": "#ffffff",
        "brand_color": "#34d399",
        "card_bg": (10, 25, 20, 195),
        "card_border": "#10b981",
        "use_cards": True
    },
    "ruby": {
        "name": "Đỏ Hồng Nổi Bật",
        "hook_color": "#fb4164",
        "hook_stroke": "#ffffff",
        "item_color": "#fff2af",
        "item_stroke": "#071525",
        "badge_fill": "#e11d48",
        "badge_outline": "#ffffff",
        "badge_text": "#ffffff",
        "brand_color": "#ffffff",
        "card_bg": (15, 23, 42, 195),
        "card_border": "#e11d48",
        "use_cards": True
    },
    "white": {
        "name": "Trắng Tinh Tế",
        "hook_color": "#ffffff",
        "hook_stroke": "#0f172a",
        "item_color": "#f1f5f9",
        "item_stroke": "#000000",
        "badge_fill": "#475569",
        "badge_outline": "#ffffff",
        "badge_text": "#ffffff",
        "brand_color": "#cbd5e1",
        "card_bg": (15, 23, 42, 195),
        "card_border": "#94a3b8",
        "use_cards": True
    }
}


def resolve_style(script: dict, config: dict = None) -> dict:
    """Resolve styling preferences from script, local preference file, and config."""
    config = config or {}
    sid = str(script.get("script_id") or script.get("post_id") or "")

    # 1. Start with global defaults from config
    theme_key = str(config.get("color_theme", "gold")).lower()
    size_mode = str(config.get("font_size_mode", "auto")).lower()

    # 2. Check local style preference file
    pref_overrides = {}
    root = Path(config.get("root_dir", Path(__file__).resolve().parents[1]))
    pref_file = root / "data" / "script_style_preferences.json"
    if pref_file.is_file():
        try:
            prefs = json.loads(pref_file.read_text(encoding="utf-8"))
            if sid and sid in prefs and isinstance(prefs[sid], dict):
                p = prefs[sid]
                theme_key = p.get("color_theme", theme_key)
                size_mode = p.get("font_size_mode", size_mode)
                pref_overrides = p
        except Exception:
            pass

    # 3. Check direct script overrides
    if script.get("color_theme"):
        theme_key = str(script["color_theme"]).lower()
    if script.get("font_size_mode"):
        size_mode = str(script["font_size_mode"]).lower()

    # Normalize theme key
    clean_theme = "gold"
    for k in THEMES:
        if k in theme_key:
            clean_theme = k
            break

    base_theme = dict(THEMES.get(clean_theme, THEMES["gold"]))

    # Direct color overrides (precedence: script > local per-script preference > config defaults)
    for field in ("hook_color", "item_color", "brand_color", "card_border"):
        val = script.get(field) or pref_overrides.get(field) or config.get(field)
        if val:
            base_theme[field] = val

    # Clean size mode
    clean_size = "auto"
    for m in ("large", "small", "medium", "auto"):
        if m in size_mode:
            clean_size = m
            break
    base_theme["font_size_mode"] = clean_size
    base_theme["theme_key"] = clean_theme

    return base_theme


def get_font(size: int):
    bundled = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "arialbd.ttf"
    candidates = (
        str(bundled),
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "Arial.ttf",
        "arial.ttf"
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    raise RuntimeError("Không tìm thấy font Unicode. Cài Arial/DejaVu Sans để hiển thị tiếng Việt.")


def text_width(text, font):
    box = font.getbbox(text or " ", stroke_width=2)
    return box[2] - box[0]


def wrap_text(text: str, font, max_width: int) -> list[str]:
    """Wrap all text, including unbroken URLs/tokens, without dropping characters."""
    if max_width < 30:
        raise ValueError("Khung chữ quá hẹp.")
    result = []
    for paragraph in str(text).splitlines() or [""]:
        current = ""
        for word in paragraph.split():
            if text_width(word, font) > max_width:
                if current:
                    result.append(current)
                    current = ""
                chunk = ""
                for char in word:
                    if chunk and text_width(chunk + char, font) > max_width:
                        result.append(chunk)
                        chunk = char
                    else:
                        chunk += char
                current = chunk
                continue
            candidate = (current + " " + word).strip()
            if current and text_width(candidate, font) > max_width:
                result.append(current)
                current = word
            else:
                current = candidate
        if current:
            result.append(current)
    return result or [""]


def _block(text, x, y, width, size):
    font = get_font(size)
    lines = wrap_text(text, font, width)
    ascent, descent = font.getmetrics()
    line_height = ascent + descent + 6
    return TextBlock(x, y, max(text_width(line, font) for line in lines),
                     len(lines) * line_height, lines, size, line_height)


def _fit_heading(text, x, y, width, maximum_size, minimum_size, max_height):
    for size in range(maximum_size, minimum_size - 1, -2):
        block = _block(text, x, y, width, size)
        if block.height <= max_height:
            return block
    raise ValueError("Tiêu đề/chữ ký quá dài. Hãy rút gọn trước khi duyệt lại kịch bản.")


def _center_page_items(items: list[ItemBlock], top: int, bottom: int, gap: int):
    """Dynamically center page items vertically so fewer items never sit unbalanced at the top."""
    if not items:
        return
    total_h = sum(item.block.height for item in items) + gap * (len(items) - 1)
    available_h = bottom - top
    if available_h > total_h:
        offset_y = (available_h - total_h) // 2
        for item in items:
            item.block.y += offset_y


def build_layout(script: dict, width=720, height=1280, config=None) -> Layout:
    if (width, height) not in ((720, 1280), (1080, 1920)):
        raise ValueError("Chỉ hỗ trợ đầu ra 720×1280 hoặc 1080×1920.")
    items = script.get("items", [])
    if not items or not all(isinstance(item, str) and item.strip() for item in items):
        raise ValueError("Kịch bản cần danh sách ý không rỗng.")
    if len(items) > 50:
        raise ValueError("Mỗi video tối đa 50 ý; hãy chia thành nhiều kịch bản.")

    style = resolve_style(script, config)

    scale = width / 720
    s = lambda value: round(value * scale)
    margin = s(44)
    text_x = s(122)
    text_available = width - text_x - margin - s(12)

    # Dynamic Typography Scaling according to configured size mode and item count
    size_mode = style.get("font_size_mode", "auto")
    item_count = len(items)

    if size_mode == "large":
        hook_max_size, hook_min_size = s(52), s(38)
        base_item_sizes = (s(40), s(38), s(36), s(34))
        gap = s(28)
    elif size_mode == "small":
        hook_max_size, hook_min_size = s(42), s(30)
        base_item_sizes = (s(28), s(26), s(24))
        gap = s(16)
    elif size_mode == "medium":
        hook_max_size, hook_min_size = s(46), s(32)
        base_item_sizes = (s(34), s(32), s(30))
        gap = s(20)
    else:  # auto: adaptive based on item count
        if item_count <= 3:
            hook_max_size, hook_min_size = s(50), s(36)
            base_item_sizes = (s(40), s(38), s(36), s(34))
            gap = s(36)
        elif item_count <= 5:
            hook_max_size, hook_min_size = s(48), s(34)
            base_item_sizes = (s(34), s(32), s(30))
            gap = s(26)
        else:
            hook_max_size, hook_min_size = s(44), s(32)
            base_item_sizes = (s(30), s(28), s(26))
            gap = s(18)

    hook = _fit_heading(str(script.get("hook", "")).strip(), margin, s(76),
                        width - margin * 2, hook_max_size, hook_min_size, s(220))
    if not str(script.get("hook", "")).strip():
        raise ValueError("Thiếu hook.")
    brand = _fit_heading(str(script.get("brand", "")).strip(), margin, height - s(170),
                         width - margin * 2, s(32), s(24), s(85))
    top = hook.y + hook.height + s(38)
    bottom = height - s(230)
    template = script.get("template", "auto")
    if template not in ("auto", "list", "pages"):
        raise ValueError("Mẫu video phải là auto, list hoặc pages.")

    def blocks_for_size(size):
        return [_block(item.strip(), text_x, 0, text_available, size) for item in items]

    blocks = blocks_for_size(base_item_sizes[0])
    if template != "pages":
        for size in base_item_sizes:
            blocks = blocks_for_size(size)
            if sum(b.height for b in blocks) + gap * (len(blocks) - 1) <= bottom - top:
                break
        else:
            if template == "list":
                raise ValueError("Nội dung không vừa một trang. Chọn mẫu auto hoặc pages rồi duyệt lại.")
            blocks = blocks_for_size(base_item_sizes[-1])

    pages, page_items, y = [], [], top
    for index, block in enumerate(blocks, 1):
        if block.height > bottom - top:
            raise ValueError(f"Ý {index} quá dài cho một trang; hãy chia ngắn nội dung.")
        if page_items and (y + block.height > bottom or (template == "pages" and len(page_items) >= 4)):
            _center_page_items(page_items, top, bottom, gap)
            pages.append(Page(hook, brand, page_items))
            page_items, y = [], top
        block.y = y
        page_items.append(ItemBlock(index, block))
        y += block.height + gap
    if page_items:
        _center_page_items(page_items, top, bottom, gap)
        pages.append(Page(hook, brand, page_items))

    # ~3 Vietnamese space-delimited units/sec plus settling time.
    minimums = []
    for page in pages:
        word_count = len(" ".join(hook.lines).split())
        word_count += sum(len(" ".join(item.block.lines).split()) for item in page.items)
        minimums.append(max(5.0, math.ceil(word_count / 3 + 1.5)))
    required = sum(minimums)
    requested = float(script.get("duration_seconds", 0) or 0)
    if not math.isfinite(requested) or requested < 0:
        raise ValueError("Thời lượng không hợp lệ.")
    if requested and requested + 0.01 < required:
        raise ValueError(f"Thời lượng {requested:g}s quá ngắn; nội dung cần ít nhất {required:g}s để đọc.")
    total = requested or required
    durations = [round(total * t / required, 3) for t in minimums]
    durations[-1] = round(total - sum(durations[:-1]), 3)
    return Layout(width, height, pages, durations, total, style=style)


def _paint_block(draw, block, color, center_width=None, stroke_color="#071525"):
    font = get_font(block.font_size)
    for index, line in enumerate(block.lines):
        x = block.x + 2
        if center_width is not None:
            x = (center_width - text_width(line, font)) / 2 + 2
        draw.text((x, block.y + index * block.line_height + 2), line,
                  font=font, fill=color, anchor="lt", stroke_width=2, stroke_fill=stroke_color)


def write_overlays(layout: Layout, output_dir: Path) -> list[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    scale = layout.width / 720
    s = lambda v: round(v * scale)
    margin = s(44)
    style = layout.style or THEMES["gold"]

    for page_index, page in enumerate(layout.pages):
        image = Image.new("RGBA", (layout.width, layout.height), (3, 12, 26, 125))
        draw = ImageDraw.Draw(image)

        # 1. Paint Hook Title
        _paint_block(draw, page.hook, style["hook_color"], layout.width, stroke_color=style["hook_stroke"])

        # 2. Paint Items (with Glassmorphism Rounded Cards)
        for item in page.items:
            card_pad_v = s(10)
            card_top = item.block.y - card_pad_v
            card_bottom = item.block.y + item.block.height + card_pad_v

            # Draw card rounded background
            if style.get("use_cards", True):
                draw.rounded_rectangle(
                    [margin, card_top, layout.width - margin, card_bottom],
                    radius=s(14),
                    fill=style["card_bg"],
                    outline=style["card_border"],
                    width=max(1, round(1.5 * scale))
                )

            # Draw Badge
            radius = round(21 * scale)
            cx = margin + s(38)
            cy = card_top + (card_bottom - card_top) // 2
            draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius),
                         fill=style["badge_fill"], outline=style["badge_outline"], width=max(2, round(2 * scale)))
            font_badge = get_font(round(20 * scale))
            draw.text((cx, cy), str(item.index), font=font_badge, fill=style["badge_text"], anchor="mm")

            # Draw Item Text
            _paint_block(draw, item.block, style["item_color"], stroke_color=style["item_stroke"])

        # 3. Paint Brand / Watermark
        _paint_block(draw, page.brand, style["brand_color"], layout.width, stroke_color="#000000")

        # 4. Page Indicator (if multi-page)
        footer = f"{page_index + 1} / {len(layout.pages)}" if len(layout.pages) > 1 else ""
        if footer:
            draw.text((layout.width / 2, layout.height - s(65)), footer,
                      font=get_font(s(20)), fill="#dce9f4", anchor="mm")

        path = output_dir / f"overlay_{page_index + 1:03d}.png"
        image.save(path)
        paths.append(path)
    return paths
