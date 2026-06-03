import pytest
from app.notifier import build_context, _render_template, _render_json_body


def test_build_context():
    ctx = build_context(
        monitor_name="Web Server",
        target="https://example.com",
        status="down",
        failure_count=3,
        error="Connection refused",
        latency=150.5,
    )
    assert ctx["monitor_name"] == "Web Server"
    assert ctx["failure_count"] == "3"
    assert ctx["latency"] == "150.5"
    assert ctx["status"] == "down"


def test_render_template():
    result = _render_template("$monitor_name is $status", {"monitor_name": "API", "status": "down"})
    assert result == "API is down"


def test_render_json_body_dict():
    tpl = {"text": "[$status] $monitor_name failed $failure_count times"}
    ctx = {"status": "down", "monitor_name": "DB", "failure_count": "5"}
    result = _render_json_body(tpl, ctx)
    assert "down" in result
    assert "DB" in result
    assert "5" in result


def test_render_json_body_string():
    tpl = '{"msg": "$monitor_name is $status"}'
    ctx = {"monitor_name": "API", "status": "up"}
    result = _render_json_body(tpl, ctx)
    assert "API" in result
    assert "up" in result
