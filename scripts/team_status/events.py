"""Fold the live event log into one row per agent. Lines that do not read are counted, never guessed."""
import json
import unicodedata
from collections import deque, namedtuple
from datetime import datetime, timezone

Event = namedtuple("Event", "ts event agent_id agent item tool target phase ok")
Row = namedtuple("Row", "agent item state doing calls seconds shared")
SILENT_SECONDS = 300
OPEN_CALL_LIMIT = 1800
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
        if parsed[0].event == "plan":
            # A new run: everything before the marker is dropped from memory.
            self.plan = parsed[0].target
            self._events = []
            self._recent.clear()
        self._events.append(parsed)
        self._recent.append(parsed[0])

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
    return printable(value) if isinstance(value, str) else ""


def printable(text):
    """Answer text with every control, format, unassigned or line-breaking character replaced by "?".

    Log text reaches the owner's terminal, so no escape sequence or line break may pass."""
    return "".join("?" if _unsafe(char) else char for char in text)


def _unsafe(char):
    return char in "\u2028\u2029" or unicodedata.category(char).startswith("C")


def _key(event):
    return event.agent_id or (event.agent, event.item)


def _fold(group, now):
    """Answer the Row for one agent's events, oldest first."""
    first, last = group[0], group[-1]
    events = [event for event, _ in group]
    starts = sum(1 for event in events if event.event == "start")
    stops = [event for event in events if event.event == "stop"]
    if first[0].agent_id:
        # The last event decides: a start or tool event after the last stop means it runs again.
        last_stop = max((i for i, event in enumerate(events) if event.event == "stop"), default=-1)
        finished = bool(stops) and last_stop == len(events) - 1
        current = group[last_stop + 1:]
    else:
        finished = bool(stops) and len(stops) >= max(starts, 1)
        current = group
    calls = sum(1 for event in events if event.event == "tool" and event.phase == "pre")
    if finished:
        state = "failed" if any(event.ok is False for event in stops) else "done"
        end, doing = last[1], ""
    else:
        tools = [event for event, _ in current if event.event == "tool"]
        open_call = _open_call(current, now)
        quiet = (now - last[1]).total_seconds() >= SILENT_SECONDS
        state = "silent" if quiet and open_call is None else "running"
        end, doing = (last[1] if state == "silent" else now), _doing(open_call, tools)
    item = next((event.item for event in events if event.item), "")
    shared = 1 if first[0].agent_id else max(starts, 1)
    return Row(first[0].agent, item, state, doing, calls, max(0, int((end - first[1]).total_seconds())), shared)


def _open_call(group, now):
    """Answer the most recent pre event no post has closed and not older than OPEN_CALL_LIMIT, else None.

    Posts close the oldest open call of their tool. A call open longer than the limit is taken as lost."""
    open_calls = []
    for event, when in group:
        if event.event != "tool":
            continue
        if event.phase == "pre":
            open_calls.append((event, when))
        elif event.phase == "post":
            match = next((i for i, (call, _) in enumerate(open_calls) if call.tool == event.tool), None)
            if match is not None:
                del open_calls[match]
    fresh = [call for call, when in open_calls if (now - when).total_seconds() <= OPEN_CALL_LIMIT]
    return fresh[-1] if fresh else None


def _doing(open_call, tools):
    if open_call is not None:
        return ("%s %s" % (open_call.tool, open_call.target)).strip()
    if tools and tools[-1].phase == "post" and tools[-1].ok is False:
        return ("%s (failed)" % tools[-1].tool).strip()
    return ""
