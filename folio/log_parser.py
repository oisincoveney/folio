"""Parse opencode stdout/stderr lines into LogEntry objects. Ported from store.js."""

import json
import re

from folio.models import LogEntry


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _readable_value(value: object) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return str(value)
    return json.dumps(value, indent=2)


def _readable_object(obj: dict, skip: list[str] | None = None) -> str:
    skip = skip or []
    lines = []
    for key, value in (obj or {}).items():
        if key in skip or value is None or value == "":
            continue
        readable = _readable_value(value)
        if "\n" in readable:
            lines.append(f"{key}:\n{readable}")
        else:
            lines.append(f"{key}: {readable}")
    return "\n".join(lines)


def _event_content(parsed: dict) -> str:
    part = parsed.get("part") or {}
    for src in (part, parsed):
        for field in ("text", "content", "reasoning", "thought"):
            v = src.get(field)
            if isinstance(v, str):
                return v
    return ""


def _render_tool_use(part: dict) -> tuple[str, str]:
    tool = part.get("tool") or part.get("name") or part.get("id") or "tool"
    lines: list[str] = []
    if part.get("description"):
        lines.append(part["description"])
    for key in ("input", "output"):
        direct = part.get(key)
        nested = (part.get("state") or {}).get(key)
        label = key.capitalize()
        if direct:
            lines.append(f"{label}:\n{_readable_value(direct)}")
        elif nested:
            lines.append(f"{label}:\n{_readable_value(nested)}")
    direct_err = part.get("error")
    nested_err = (part.get("state") or {}).get("error")
    if direct_err:
        lines.append(f"Error: {direct_err}")
    elif nested_err:
        lines.append(f"Error: {nested_err}")
    if not lines:
        lines.append(_readable_object(part, ["id", "sessionID", "messageID"]))
    return tool, "\n\n".join(filter(None, lines))


def _render_step_finish(parsed: dict) -> str:
    lines: list[str] = []
    if parsed.get("reason"):
        lines.append(f"Reason: {parsed['reason']}")
    if parsed.get("cost") is not None:
        lines.append(f"Cost: ${float(parsed['cost']):.4f}")
    if tokens := parsed.get("tokens"):
        lines.append(
            f"Tokens: {tokens.get('total', 0)} total, "
            f"{tokens.get('input', 0)} in, {tokens.get('output', 0)} out",
        )
    t = parsed.get("time") or {}
    if t.get("start") and t.get("end"):
        lines.append(f"Duration: {max(0, t['end'] - t['start'])}ms")
    return "\n".join(lines)


def parse_opencode_line(ev: dict) -> LogEntry:
    """Parse an opencode raw_log event dict into a LogEntry."""
    entry = LogEntry(
        stream=ev.get("stream", "stdout"),
        raw=ev.get("text", ""),
        type="raw",
        title=ev.get("stream", "stdout"),
        body=strip_ansi(ev.get("text", "")),
    )
    try:
        parsed = json.loads(entry.raw)
        part = parsed.get("part") or {}
        entry.type = parsed.get("type", "json")
        entry.title = entry.type
        entry.meta = (
            part.get("type", "")
            or part.get("tool", "")
            or parsed.get("reason", "")
            or ""
        )
        entry.technical = entry.type in ("step_start", "step_finish")
        emitted = _event_content(parsed)
        if entry.type == "step_start":
            msg_id = parsed.get("messageID")
            entry.body = f"messageID: {msg_id}" if msg_id else "step started"
            entry.meta = parsed.get("id", "")
        elif entry.type == "step_finish":
            entry.body = _render_step_finish(parsed) or "step finished"
            entry.meta = parsed.get("reason", "")
        elif entry.type == "tool_use":
            meta, body = _render_tool_use(part or parsed)
            entry.body = body
            entry.meta = meta
        elif emitted:
            entry.body = emitted
        elif part and isinstance(part, dict):
            entry.body = _readable_object(
                part, ["id", "sessionID", "messageID"],
            ) or _readable_object(parsed, ["id", "sessionID", "messageID", "snapshot"])
        else:
            entry.body = _readable_object(
                parsed, ["id", "sessionID", "messageID", "snapshot"],
            ) or entry.raw
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        entry.type = "stderr" if entry.stream == "stderr" else "raw"
        entry.title = entry.type
    return entry


def system_log(text: str) -> LogEntry:
    """Create a system-type LogEntry with the given text."""
    return LogEntry(stream="system", raw=text, type="system", title="system", body=text)
