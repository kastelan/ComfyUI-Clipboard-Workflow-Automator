"""
Unit tests for clipboard.py.

These test the pure logic (JSON patching, retry/backoff, retention, dead-letter
queue) with everything that touches the real OS clipboard, network, or GTK/win32
mocked or monkeypatched out. They run on whichever platform CI is currently on
(Linux job imports the GTK branch, Windows job imports the win32 branch) since
clipboard.py picks its clipboard implementation at import time based on
sys.platform — there's no way to test both branches in one process.
"""

import json
import time

import pytest
import requests

import clipboard

# ---------------------------------------------------------------------------
# get_image_hash
# ---------------------------------------------------------------------------

class _FakeImage:
    """Minimal stand-in for a PIL.Image — get_image_hash only calls .tobytes()."""
    def __init__(self, data: bytes):
        self._data = data

    def tobytes(self) -> bytes:
        return self._data


def test_get_image_hash_deterministic():
    img = _FakeImage(b"same pixels")
    assert clipboard.get_image_hash(img) == clipboard.get_image_hash(_FakeImage(b"same pixels"))


def test_get_image_hash_differs_for_different_content():
    a = clipboard.get_image_hash(_FakeImage(b"pixels A"))
    b = clipboard.get_image_hash(_FakeImage(b"pixels B"))
    assert a != b


# ---------------------------------------------------------------------------
# create_api_prompt
# ---------------------------------------------------------------------------

def _write_workflow(tmp_path, data: dict, name: str = "wf.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_create_api_prompt_happy_path_text(tmp_path):
    wf = _write_workflow(tmp_path, {
        "5": {"_meta": {"title": "load_clipboard_text"}, "inputs": {"text": "old"}}
    })
    result = clipboard.create_api_prompt("hello", "text", workflow_path=wf)
    assert result == {
        "prompt": {"5": {"_meta": {"title": "load_clipboard_text"}, "inputs": {"text": "hello"}}},
        "client_id": "clipboard_script",
    }


def test_create_api_prompt_happy_path_image(tmp_path, monkeypatch):
    monkeypatch.setattr(clipboard, "INPUT_DIR", tmp_path / "clipboard_images")
    wf = _write_workflow(tmp_path, {
        "5": {"_meta": {"title": "load_clipboard_image"}, "inputs": {"image": "old.png"}}
    })
    fake_image_path = tmp_path / "clipboard_images" / "clipboard_123.png"
    result = clipboard.create_api_prompt(fake_image_path, "image", workflow_path=wf)
    assert result["prompt"]["5"]["inputs"]["image"] == "clipboard_images/clipboard_123.png"


def test_create_api_prompt_missing_file(tmp_path):
    result = clipboard.create_api_prompt("x", "text", workflow_path=tmp_path / "does_not_exist.json")
    assert result is None


def test_create_api_prompt_empty_file(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("", encoding="utf-8")
    result = clipboard.create_api_prompt("x", "text", workflow_path=path)
    assert result is None


def test_create_api_prompt_corrupt_json(tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text('{"5": {"_meta":', encoding="utf-8")
    result = clipboard.create_api_prompt("x", "text", workflow_path=path)
    assert result is None


def test_create_api_prompt_missing_inputs_block(tmp_path):
    wf = _write_workflow(tmp_path, {"5": {"_meta": {"title": "load_clipboard_text"}}})
    result = clipboard.create_api_prompt("x", "text", workflow_path=wf)
    assert result is None


def test_create_api_prompt_missing_target_key(tmp_path):
    wf = _write_workflow(tmp_path, {
        "5": {"_meta": {"title": "load_clipboard_text"}, "inputs": {"other": 1}}
    })
    result = clipboard.create_api_prompt("x", "text", workflow_path=wf)
    assert result is None


def test_create_api_prompt_node_not_found(tmp_path):
    wf = _write_workflow(tmp_path, {
        "5": {"_meta": {"title": "something_else"}, "inputs": {}}
    })
    result = clipboard.create_api_prompt("x", "text", workflow_path=wf)
    assert result is None


def test_create_api_prompt_unknown_content_type(tmp_path):
    wf = _write_workflow(tmp_path, {"5": {"_meta": {"title": "x"}, "inputs": {}}})
    result = clipboard.create_api_prompt("x", "audio", workflow_path=wf)
    assert result is None


# ---------------------------------------------------------------------------
# cleanup_old_images
# ---------------------------------------------------------------------------

def _touch(path, age_seconds: float = 0):
    path.write_bytes(b"x")
    if age_seconds:
        t = time.time() - age_seconds
        import os
        os.utime(path, (t, t))


def test_cleanup_nonexistent_directory_is_a_noop(tmp_path):
    clipboard.cleanup_old_images(tmp_path / "does_not_exist", max_age_days=7, max_files=10)
    # no exception raised is the whole test


def test_cleanup_enforces_max_files(tmp_path):
    d = tmp_path / "images"
    d.mkdir()
    for i in range(5):
        _touch(d / f"clipboard_{i}.png", age_seconds=i)  # i=0 is newest
    clipboard.cleanup_old_images(d, max_age_days=0, max_files=3)
    remaining = sorted(p.name for p in d.glob("*.png"))
    assert remaining == ["clipboard_0.png", "clipboard_1.png", "clipboard_2.png"]


def test_cleanup_enforces_max_age(tmp_path):
    d = tmp_path / "images"
    d.mkdir()
    _touch(d / "clipboard_old.png", age_seconds=8 * 86400)
    _touch(d / "clipboard_new.png", age_seconds=0)
    clipboard.cleanup_old_images(d, max_age_days=7, max_files=0)
    remaining = sorted(p.name for p in d.glob("*.png"))
    assert remaining == ["clipboard_new.png"]


def test_cleanup_zero_disables_both_checks(tmp_path):
    d = tmp_path / "images"
    d.mkdir()
    _touch(d / "clipboard_ancient.png", age_seconds=999 * 86400)
    clipboard.cleanup_old_images(d, max_age_days=0, max_files=0)
    assert (d / "clipboard_ancient.png").exists()


def test_cleanup_ignores_non_matching_filenames(tmp_path):
    d = tmp_path / "images"
    d.mkdir()
    (d / "not_a_clipboard_file.png").write_bytes(b"x")
    clipboard.cleanup_old_images(d, max_age_days=0, max_files=0)
    assert (d / "not_a_clipboard_file.png").exists()


# ---------------------------------------------------------------------------
# send_to_api — retry/backoff + dead-letter queue
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Every retry test would otherwise burn real wall-clock time (2s, 4s, 8s...)."""
    monkeypatch.setattr(clipboard.time, "sleep", lambda seconds: None)


@pytest.fixture
def _dead_letter_dir(tmp_path, monkeypatch):
    d = tmp_path / "failed_prompts"
    monkeypatch.setattr(clipboard, "DEAD_LETTER_DIR", d)
    return d


def test_send_to_api_empty_prompt_does_not_call_requests(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(requests, "post", lambda *a, **kw: called.__setitem__("n", called["n"] + 1))
    clipboard.send_to_api(None)
    assert called["n"] == 0


def test_send_to_api_succeeds_first_try(monkeypatch, _dead_letter_dir):
    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"prompt_id": "abc"}

    calls = {"n": 0}

    def fake_post(*a, **kw):
        calls["n"] += 1
        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    clipboard.send_to_api({"prompt": {}})
    assert calls["n"] == 1
    assert not list(_dead_letter_dir.glob("*")) if _dead_letter_dir.exists() else True


def test_send_to_api_recovers_after_retries(monkeypatch, _dead_letter_dir):
    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"prompt_id": "abc"}

    calls = {"n": 0}

    def flaky_post(*a, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.exceptions.ConnectionError("refused")
        return _Resp()

    monkeypatch.setattr(requests, "post", flaky_post)
    clipboard.send_to_api({"prompt": {"marker": "A"}})
    assert calls["n"] == 3
    assert not _dead_letter_dir.exists() or not list(_dead_letter_dir.glob("*"))


def test_send_to_api_dead_letters_after_exhausting_retries(monkeypatch, _dead_letter_dir):
    monkeypatch.setattr(
        requests, "post",
        lambda *a, **kw: (_ for _ in ()).throw(requests.exceptions.ConnectionError("refused")),
    )
    clipboard.send_to_api({"prompt": {"marker": "B"}})
    files = list(_dead_letter_dir.glob("failed_*.json"))
    assert len(files) == 1
    saved = json.loads(files[0].read_text())
    assert saved == {"prompt": {"marker": "B"}}


def test_send_to_api_respects_configured_retry_count(monkeypatch, _dead_letter_dir):
    monkeypatch.setitem(clipboard.CONFIG, "retry_count", 1)
    calls = {"n": 0}

    def always_fails(*a, **kw):
        calls["n"] += 1
        raise requests.exceptions.Timeout("slow")

    monkeypatch.setattr(requests, "post", always_fails)
    clipboard.send_to_api({"prompt": {}})
    # retry_count=1 means: 1 initial attempt + 1 retry = 2 calls total
    assert calls["n"] == 2


# ---------------------------------------------------------------------------
# replay_dead_letter_queue
# ---------------------------------------------------------------------------

def test_replay_dead_letter_queue_no_directory_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(clipboard, "DEAD_LETTER_DIR", tmp_path / "does_not_exist")
    clipboard.replay_dead_letter_queue()  # should not raise


def test_replay_dead_letter_queue_success_removes_file(monkeypatch, _dead_letter_dir):
    _dead_letter_dir.mkdir(parents=True)
    f = _dead_letter_dir / "failed_1.json"
    f.write_text(json.dumps({"prompt": "one"}))

    class _Resp:
        def raise_for_status(self): pass

    monkeypatch.setattr(requests, "post", lambda *a, **kw: _Resp())
    clipboard.replay_dead_letter_queue()
    assert not f.exists()


def test_replay_dead_letter_queue_failure_keeps_file(monkeypatch, _dead_letter_dir):
    _dead_letter_dir.mkdir(parents=True)
    f = _dead_letter_dir / "failed_1.json"
    f.write_text(json.dumps({"prompt": "one"}))

    monkeypatch.setattr(
        requests, "post",
        lambda *a, **kw: (_ for _ in ()).throw(requests.exceptions.ConnectionError("still down")),
    )
    clipboard.replay_dead_letter_queue()
    assert f.exists()


def test_replay_dead_letter_queue_skips_unreadable_file(monkeypatch, _dead_letter_dir):
    _dead_letter_dir.mkdir(parents=True)
    bad = _dead_letter_dir / "failed_bad.json"
    bad.write_text("not valid json {{{")

    calls = {"n": 0}
    monkeypatch.setattr(requests, "post", lambda *a, **kw: calls.__setitem__("n", calls["n"] + 1))
    clipboard.replay_dead_letter_queue()
    # Corrupt file is left in place and never sent — not silently deleted or crashed on.
    assert bad.exists()
    assert calls["n"] == 0
