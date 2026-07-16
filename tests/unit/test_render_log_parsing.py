"""Unit tests for Render log parsing (scripts/render_logs.py) — no network."""
from scripts.render_logs import LogRecord, format_record, is_error, parse_entry


def entry(message, level=None, timestamp="2026-07-15T12:00:00Z"):
    e = {"timestamp": timestamp, "message": message}
    if level is not None:
        e["labels"] = [{"name": "level", "value": level}]
    return e


def test_parses_uvicorn_access_line():
    rec = parse_entry(entry('10.204.108.201:0 - "GET /api/plants?garden_id=1 HTTP/1.1" 200', "info"))
    assert rec.method == "GET"
    assert rec.path == "/api/plants?garden_id=1"
    assert rec.status == 200
    assert rec.level == "info"
    assert rec.timestamp == "2026-07-15T12:00:00Z"


def test_non_access_line_has_no_http_fields():
    rec = parse_entry(entry("Application startup complete.", "info"))
    assert rec.method is None
    assert rec.path is None
    assert rec.status is None


def test_missing_labels_gives_empty_level():
    rec = parse_entry({"timestamp": "t", "message": "hello"})
    assert rec.level == ""
    assert rec.message == "hello"


def test_is_error_on_error_level():
    assert is_error(parse_entry(entry("something broke", "error")))


def test_is_error_on_4xx_5xx_status():
    assert is_error(parse_entry(entry('1.2.3.4:0 - "POST /api/auth/login HTTP/1.1" 401')))
    assert is_error(parse_entry(entry('1.2.3.4:0 - "GET /api/plants HTTP/1.1" 500')))
    assert not is_error(parse_entry(entry('1.2.3.4:0 - "GET /api/health HTTP/1.1" 200')))


def test_is_error_on_traceback():
    assert is_error(parse_entry(entry("Traceback (most recent call last):", "info")))


def test_info_line_is_not_error():
    assert not is_error(parse_entry(entry("Application startup complete.", "info")))


def test_format_record_includes_http_fields():
    rec = LogRecord(timestamp="t", level="info", message="m", method="GET", path="/api/health", status=200)
    line = format_record(rec)
    assert "200 GET /api/health" in line
    assert "[info]" in line
