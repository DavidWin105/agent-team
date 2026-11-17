"""Fold the live event log into one row per agent. Lines that do not read are counted, never guessed."""
import json
from collections import deque, namedtuple
from datetime import datetime, timezone

Event = namedtuple("Event", "ts event agent_id agent item tool target phase ok")
Row = namedtuple("Row", "agent item state doing calls seconds shared")
SILENT_SECONDS = 300
HEAD_BYTES = 64
RECENT_KEPT = 50
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
FIELDS = ("event", "agent_id", "agent", "item", "tool", "target", "phase")


class EventLog:
    """Read a JSON-lines event log in steps and answer the agent rows folded from it."""

    def __init__(self, path):
        self.path = path
        self._reset()

    def _reset(self):
        self.seen = 0
        self.unread = 0
        self.plan = None
        self._offset = 0
        self._head = b""
        self._events = []
        self._recent = deque(maxlen=RECENT_KEPT)

    def refresh(self):
        """Read the complete lines added since the last call; start over if the file shrank or changed."""
        try:
            with open(self.path, "rb") as handle:
                handle.seek(0, 2)
                if handle.tell() < self._offset or self._head_changed(handle):
                    self._reset()
                handle.seek(self._offset)
                chunk = handle.read()
                if self._offset == 0:
                    handle.seek(0)
                    self._head = handle.read(HEAD_BYTES)
        except OSError:
            self._reset()
            return
        end = chunk.rfind(b"\n") + 1
        self._offset += end
        for raw in chunk[:end].splitlines():
            self._take(raw)

    def _head_changed(self, handle):
        handle.seek(0)
        return self._offset > 0 and handle.read(len(self._head)) != self._head

    def _take(self, raw):
        if not raw.strip():
            return
        parsed = _parse(raw)
        if parsed is None:
            self.unread += 1
            return
        self.seen += 1
        self._events.append(parsed)
        self._recent.append(parsed[0])
        if parsed[0].event == "plan":
            self.plan = parsed[0].target

    def rows(self, now):
        """Answer one Row per agent for the events after the last plan marker."""
        groups = {}
        for event, when in self._since_last_plan():
            if event.event in ("start", "tool", "stop"):
                groups.setdefault(_key(event), []).append((event, when))
        return [_fold(group, now) for group in groups.values()]

    def recent(self, n):
        """Answer the newest n parsed Events, newest first (from the last 50 kept)."""
        return list(self._recent)[::-1][:n]

    def _since_last_plan(self):
        last = max((i for i, (event, _) in enumerate(self._events) if event.event == "plan"), default=-1)
        return self._events[last + 1:]


def _parse(raw):
    """Answer (Event, datetime) for a good line, else None."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    ts = data.get("ts")
    try:
        when = datetime.strptime(ts, TIME_FORMAT).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    texts = {name: _text(data.get(name)) for name in FIELDS}
    ok = data.get("ok")
    return Event(ts=ts, ok=ok if isinstance(ok, bool) else None, **texts), when


def _text(value):
    return value if isinstance(value, str) else ""


def _key(event):
    return event.agent_id or (event.agent, event.item)


def _fold(group, now):
    """Answer the Row for one agent's events, oldest first."""
    first, last = group[0], group[-1]
    starts = sum(1 for event, _ in group if event.event == "start")
    stops = [event for event, _ in group if event.event == "stop"]
    tools = [event for event, _ in group if event.event == "tool"]
    calls = sum(1 for event in tools if event.phase == "pre")
    open_call = tools[-1] if tools and tools[-1].phase == "pre" else None
    if stops and len(stops) >= max(starts, 1):
        state = "failed" if any(event.ok is False for event in stops) else "done"
        end, open_call = last[1], None
    else:
        quiet = (now - last[1]).total_seconds() >= SILENT_SECONDS
        state = "silent" if quiet and open_call is None else "running"
        end = now
    doing = ("%s %s" % (open_call.tool, open_call.target)).strip() if open_call else ""
    shared = 1 if first[0].agent_id else max(starts, 1)
    return Row(first[0].agent, first[0].item, state, doing, calls, max(0, int((end - first[1]).total_seconds())), shared)
