"""Tests for log_parser: opencode stdout/stderr line → LogEntry rendering."""

import json

from folio.log_parser import parse_opencode_line, strip_ansi, system_log


def test_strip_ansi_removes_color_codes():
    assert strip_ansi("\x1b[31mred\x1b[0m text") == "red text"


def test_strip_ansi_passes_through_plain_text():
    assert strip_ansi("plain") == "plain"


def test_system_log_marks_stream_and_type():
    entry = system_log("starting up")
    assert entry.stream == "system"
    assert entry.type == "system"
    assert entry.title == "system"
    assert entry.body == "starting up"


def test_parse_non_json_stderr_falls_back_to_stderr_type():
    entry = parse_opencode_line({"stream": "stderr", "text": "boom: opencode crashed"})
    assert entry.type == "stderr"
    assert entry.stream == "stderr"
    assert entry.body == "boom: opencode crashed"


def test_parse_non_json_stdout_falls_back_to_raw_type():
    entry = parse_opencode_line({"stream": "stdout", "text": "hello"})
    assert entry.type == "raw"
    assert entry.title == "raw"
    assert entry.body == "hello"


def test_parse_strips_ansi_from_raw_body():
    entry = parse_opencode_line({"stream": "stdout", "text": "\x1b[31mhi\x1b[0m"})
    assert entry.body == "hi"


def test_parse_text_event_uses_text_field_as_body():
    payload = json.dumps({"type": "text", "part": {"text": "extracted invoice"}})
    entry = parse_opencode_line({"stream": "stdout", "text": payload})
    assert entry.type == "text"
    assert entry.body == "extracted invoice"
    assert entry.technical is False


def test_parse_step_start_marks_technical_and_uses_message_id():
    payload = json.dumps({"type": "step_start", "messageID": "msg-123", "id": "step-1"})
    entry = parse_opencode_line({"stream": "stdout", "text": payload})
    assert entry.type == "step_start"
    assert entry.technical is True
    assert entry.body == "messageID: msg-123"
    assert entry.meta == "step-1"


def test_parse_step_finish_renders_cost_tokens_and_duration():
    payload = json.dumps({
        "type": "step_finish",
        "reason": "stop",
        "cost": 0.0042,
        "tokens": {"total": 100, "input": 60, "output": 40},
        "time": {"start": 1000, "end": 1500},
    })
    entry = parse_opencode_line({"stream": "stdout", "text": payload})
    assert entry.type == "step_finish"
    assert entry.technical is True
    assert "Reason: stop" in entry.body
    assert "Cost: $0.0042" in entry.body
    assert "Tokens: 100 total, 60 in, 40 out" in entry.body
    assert "Duration: 500ms" in entry.body
    assert entry.meta == "stop"


def test_parse_tool_use_uses_tool_name_as_meta_and_renders_input():
    payload = json.dumps({
        "type": "tool_use",
        "part": {
            "tool": "pdf_read",
            "description": "Reading PDF",
            "input": {"path": "/tmp/invoice.pdf"},
        },
    })
    entry = parse_opencode_line({"stream": "stdout", "text": payload})
    assert entry.type == "tool_use"
    assert entry.meta == "pdf_read"
    assert "Reading PDF" in entry.body
    assert "/tmp/invoice.pdf" in entry.body


def test_parse_tool_use_pulls_nested_state_output_and_error():
    payload = json.dumps({
        "type": "tool_use",
        "part": {
            "tool": "shell",
            "state": {"output": "ok", "error": "permission denied"},
        },
    })
    entry = parse_opencode_line({"stream": "stdout", "text": payload})
    assert "Output:" in entry.body
    assert "ok" in entry.body
    assert "Error: permission denied" in entry.body


def test_parse_unknown_json_type_falls_back_to_readable_object():
    payload = json.dumps({"type": "mystery", "part": {"foo": "bar", "baz": 1}})
    entry = parse_opencode_line({"stream": "stdout", "text": payload})
    assert entry.type == "mystery"
    assert "foo: bar" in entry.body
    assert "baz: 1" in entry.body


def test_parse_readable_object_skips_sessionid_and_messageid_noise():
    payload = json.dumps({
        "type": "other",
        "part": {"sessionID": "s1", "messageID": "m1", "label": "keep me"},
    })
    entry = parse_opencode_line({"stream": "stdout", "text": payload})
    assert "sessionID" not in entry.body
    assert "messageID" not in entry.body
    assert "label: keep me" in entry.body
