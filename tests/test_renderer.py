"""Renderer regression gates: readability, immutable approval, durable retry."""
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock

import pytest


def sample_script():
    return {
        "script_id": "script_fb_test", "post_id": "fb_test", "version": 1,
        "hook": "8 THÓI QUEN GIÚP NGÀY MỚI NHẸ NHÀNG HƠN",
        "items": [
            "Lập kế hoạch — chọn một việc quan trọng nhất cho hôm nay",
            "Dành thời gian — lắng nghe người thân bằng sự chân thành",
            "Giữ góc làm việc — gọn gàng để dễ tập trung hơn",
            "Nghỉ một chút — sau mỗi khoảng làm việc kéo dài",
            "Ghi nhận điều tốt — dù đó chỉ là một việc rất nhỏ",
            "Học điều mới — bắt đầu bằng một trang sách",
            "Sắp xếp việc mai — trước khi kết thúc ngày hôm nay",
            "Trân trọng hiện tại — bớt so sánh bản thân với người khác",
        ],
        "caption": "Một ngày mới, một thay đổi nhỏ.", "brand": "chú Dũng Sức",
        "template": "auto", "duration_seconds": 0,
    }


def test_wrapping_handles_long_word_and_vietnamese():
    from renderer.layout import get_font, wrap_text, text_width
    font = get_font(32)
    lines = wrap_text("Điều quan trọng " + "rất" * 100, font, 280)
    assert len(lines) > 3
    assert all(text_width(line, font) <= 280 for line in lines)
    assert "".join(lines).replace(" ", "") == ("Điều quan trọng " + "rất" * 100).replace(" ", "")


@pytest.mark.parametrize("width,height", [(720, 1280), (1080, 1920)])
def test_long_content_has_no_overflow_and_loses_no_items(width, height):
    from renderer.layout import build_layout
    script = sample_script()
    script["items"] = script["items"] * 3
    layout = build_layout(script, width, height)
    assert len(layout.pages) > 1
    assert [item.index for page in layout.pages for item in page.items] == list(range(1, 25))
    for page in layout.pages:
        for block in [page.hook, page.brand] + [i.block for i in page.items]:
            assert block.x >= 0 and block.y >= 0
            assert block.x + block.width <= width
            assert block.y + block.height <= height
    assert sum(layout.durations) == pytest.approx(layout.duration)


def test_explicit_duration_cannot_force_unreadable_pages():
    from renderer.layout import build_layout
    script = sample_script()
    script.update(template="pages", duration_seconds=2)
    with pytest.raises(ValueError, match="thời lượng|Thời lượng"):
        build_layout(script, 720, 1280)


def test_single_page_template_rejects_excess_instead_of_truncating():
    from renderer.layout import build_layout
    script = sample_script()
    script.update(template="list", items=script["items"] * 5)
    with pytest.raises(ValueError, match="trang|pages"):
        build_layout(script, 720, 1280)


def make_job():
    from shared.models import script_hash
    script = sample_script()
    digest = script_hash(script)
    script.update(approved_hash=digest, status="APPROVED")
    return {"job_id": "job1", "worker_id": "worker1", "render_id": "render_test",
            "content_hash": digest, "script": script}


def fake_store():
    values = {}
    store = Mock()
    store.get_artifact.side_effect = values.get
    store.put_artifact.side_effect = values.__setitem__
    return store


def test_changed_approved_script_is_never_rendered(tmp_path, monkeypatch):
    import renderer.worker as worker
    job = make_job()
    job["script"]["hook"] = "NỘI DUNG ĐÃ BỊ SỬA SAU DUYỆT"
    engine = Mock()
    monkeypatch.setattr(worker, "render_script", engine)
    with pytest.raises(ValueError, match="duyệt|hash|phiên bản"):
        worker.process_job({"data_dir": tmp_path}, Mock(), fake_store(), job)
    engine.assert_not_called()


def test_durable_completion_reused_after_delivery_failure(tmp_path, monkeypatch):
    import renderer.worker as worker
    job = make_job()
    store = fake_store()
    client = Mock()
    movie = tmp_path / "movie.mp4"
    movie.write_bytes(b"fixture")
    preview = tmp_path / "preview.png"
    preview.write_bytes(b"fixture")
    engine = Mock(return_value={"output_path": str(movie), "preview_path": str(preview),
                               "duration_seconds": 12.0, "width": 720, "height": 1280})
    monkeypatch.setattr(worker, "render_script", engine)
    monkeypatch.setattr(worker, "validate_video", lambda *a, **kw: {"has_audio": True})
    monkeypatch.setattr(worker, "LeaseHeartbeat", lambda *a, **kw: nullcontext())
    config = {"data_dir": tmp_path}
    first = worker.process_job(config, client, store, job)
    # Outbox delivery is a separate operation; failure must not erase the artifact.
    store.flush.side_effect = RuntimeError("offline")
    with pytest.raises(RuntimeError):
        store.flush(client)
    second = worker.process_job(config, client, store, job)
    assert first == second
    assert engine.call_count == 1
    assert store.enqueue.call_count == 2
    snapshot = next((tmp_path / "renders").glob("*/snapshot.json"))
    assert "NỘI DUNG ĐÃ BỊ SỬA" not in snapshot.read_text(encoding="utf-8")


def test_invalid_cached_movie_never_completes(tmp_path, monkeypatch):
    import renderer.worker as worker
    job = make_job()
    store = fake_store()
    monkeypatch.setattr(worker, "LeaseHeartbeat", lambda *a, **kw: nullcontext())
    monkeypatch.setattr(worker, "render_script", Mock(side_effect=RuntimeError("invalid media")))
    with pytest.raises(RuntimeError, match="invalid media"):
        worker.process_job({"data_dir": tmp_path}, Mock(), store, job)
    store.enqueue.assert_not_called()


def test_saved_manifest_reused_after_process_restart(tmp_path, monkeypatch):
    import renderer.worker as worker
    job = make_job()
    movie = tmp_path / "movie.mp4"
    preview = tmp_path / "preview.png"
    movie.write_bytes(b"fixture")
    preview.write_bytes(b"fixture")
    engine = Mock(return_value={"output_path": str(movie), "preview_path": str(preview),
                               "duration_seconds": 12.0, "width": 720, "height": 1280})
    monkeypatch.setattr(worker, "render_script", engine)
    monkeypatch.setattr(worker, "validate_video", lambda *a, **kw: {"has_audio": True})
    monkeypatch.setattr(worker, "LeaseHeartbeat", lambda *a, **kw: nullcontext())
    first = worker.process_job({"data_dir": tmp_path}, Mock(), fake_store(), job)
    # Fresh store simulates a crash after manifest write but before database persistence.
    second = worker.process_job({"data_dir": tmp_path}, Mock(), fake_store(), job)
    assert first == second
    assert engine.call_count == 1


def test_lease_loss_never_queues_completion(tmp_path, monkeypatch):
    from contextlib import contextmanager
    import renderer.worker as worker
    @contextmanager
    def lease_lost(*args, **kwargs):
        yield
        raise RuntimeError("lease lost")
    engine = Mock(return_value={"output_path": "movie.mp4", "preview_path": "preview.png",
                               "duration_seconds": 12.0, "width": 720, "height": 1280})
    monkeypatch.setattr(worker, "render_script", engine)
    monkeypatch.setattr(worker, "LeaseHeartbeat", lease_lost)
    store = fake_store()
    with pytest.raises(RuntimeError, match="lease lost"):
        worker.process_job({"data_dir": tmp_path}, Mock(), store, make_job())
    store.enqueue.assert_not_called()


def test_pending_completion_does_not_claim_new_render():
    from tool2 import run_once
    store, client = Mock(), Mock()
    store.pending.return_value = [{"action": "complete_render"}]
    assert run_once({}, client, store, "worker") is None
    client.call.assert_not_called()
