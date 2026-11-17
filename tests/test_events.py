import os
import shutil
import unittest
from datetime import datetime, timedelta, timezone

from team_status.events import EventLog, Row
from fixtures import make_project, write_events

NOW = datetime(2026, 11, 17, 14, 5, 23, tzinfo=timezone.utc)


def ev(ts, event, **fields):
    return {"ts": ts, "event": event, "agent_id": "a1", "agent": "builder", "item": "subtract", **fields}


START = ev("2026-11-17T14:02:11Z", "start")
PRE = ev("2026-11-17T14:02:20Z", "tool", tool="Edit", target="test_calc.py", phase="pre")
POST = ev("2026-11-17T14:02:30Z", "tool", tool="Edit", target="test_calc.py", phase="post", ok=True)


class EventsTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project(commit=False)
        self.addCleanup(shutil.rmtree, self.root, True)

    def rows(self, lines, now=NOW):
        log = EventLog(write_events(self.root, lines))
        log.refresh()
        self.log = log
        return log.rows(now)

    def test_running_builder(self):
        self.assertEqual(self.rows([START, PRE]), [Row("builder", "subtract", "running", "Edit test_calc.py", 1, 192, 1)])

    def test_done_and_failed(self):
        self.assertEqual(self.rows([START, ev("2026-11-17T14:03:00Z", "stop", ok=True)])[0].state, "done")
        self.assertEqual(self.rows([START, ev("2026-11-17T14:03:00Z", "stop", ok=False)])[0].state, "failed")

    def test_done_row_stops_the_clock(self):
        row = self.rows([START, ev("2026-11-17T14:03:00Z", "stop", ok=True)])[0]
        self.assertEqual(row.seconds, 49)

    def test_calls_counted_on_pre_only(self):
        row = self.rows([START, PRE, POST])[0]
        self.assertEqual((row.calls, row.doing), (1, ""))

    def test_silent_after_300_seconds(self):
        self.assertEqual(self.rows([START, POST], now=NOW + timedelta(seconds=300))[0].state, "silent")
        self.assertEqual(self.rows([START, POST], now=NOW)[0].state, "running")

    def test_long_open_tool_call_is_not_silent(self):
        row = self.rows([START, ev("2026-11-17T13:55:00Z", "tool", tool="Bash", target="make", phase="pre")])[0]
        self.assertEqual(row.state, "running")

    def test_only_events_since_last_plan_marker(self):
        old = ev("2026-11-17T13:00:00Z", "start", agent_id="old", agent="reviewer")
        plan = {"ts": "2026-11-17T14:00:00Z", "event": "plan", "target": "plan-two.md"}
        rows = self.rows([old, plan, START])
        self.assertEqual([r.agent for r in rows], ["builder"])
        self.assertEqual(self.log.plan, "plan-two.md")

    def test_no_plan_marker_shows_everything(self):
        self.rows([START])
        self.assertIsNone(self.log.plan)

    def test_agents_without_id_share_row(self):
        a = ev("2026-11-17T14:02:11Z", "start", agent_id="")
        b = ev("2026-11-17T14:02:12Z", "start", agent_id="")
        rows = self.rows([a, b])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].shared, 2)

    def test_broken_line_counted_not_guessed(self):
        self.rows([START, "{not json", "[1, 2]"])
        self.assertEqual((self.log.seen, self.log.unread), (1, 2))

    def test_partial_last_line_waits(self):
        path = write_events(self.root, [START])
        with open(path, "a", encoding="utf-8") as handle:
            handle.write('{"ts": "2026-11-17T14:02:20Z", "event": "sto')
        log = EventLog(path)
        log.refresh()
        self.assertEqual((log.seen, log.unread), (1, 0))
        with open(path, "a", encoding="utf-8") as handle:
            handle.write('p", "agent_id": "a1", "ok": true}\n')
        log.refresh()
        self.assertEqual((log.seen, log.unread), (2, 0))
        self.assertEqual(log.rows(NOW)[0].state, "done")

    def test_truncated_log_starts_over(self):
        path = write_events(self.root, [START, PRE, POST])
        log = EventLog(path)
        log.refresh()
        write_events(self.root, [ev("2026-11-17T14:04:00Z", "start", agent_id="b2", agent="code-reviewer")])
        log.refresh()
        self.assertEqual(log.seen, 1)
        self.assertEqual([r.agent for r in log.rows(NOW)], ["code-reviewer"])

    def test_replaced_log_of_same_size_or_more_starts_over(self):
        path = write_events(self.root, [START])
        log = EventLog(path)
        log.refresh()
        os.remove(path)
        write_events(self.root, [ev("2026-11-17T14:04:00Z", "start", agent_id="b2", agent="code-reviewer"), PRE])
        log.refresh()
        self.assertEqual([r.agent for r in log.rows(NOW)], ["code-reviewer", "builder"])
        self.assertEqual(log.seen, 2)

    def test_missing_log_is_empty(self):
        log = EventLog(os.path.join(self.root, "nope.jsonl"))
        log.refresh()
        self.assertEqual((log.seen, log.rows(NOW)), (0, []))

    def test_vanished_log_resets(self):
        path = write_events(self.root, [START])
        log = EventLog(path)
        log.refresh()
        os.remove(path)
        log.refresh()
        self.assertEqual((log.seen, log.rows(NOW)), (0, []))

    def test_future_timestamp_gives_zero_seconds(self):
        row = self.rows([ev("2026-11-17T15:00:00Z", "start")])[0]
        self.assertEqual(row.seconds, 0)


if __name__ == "__main__":
    unittest.main()


class RecentTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project(commit=False)
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_recent_returns_newest_first(self):
        log = EventLog(write_events(self.root, [START, PRE, POST]))
        log.refresh()
        events = log.recent(2)
        self.assertEqual([e.phase for e in events], ["post", "pre"])
        self.assertEqual(events[0].ts, "2026-11-17T14:02:30Z")
        self.assertEqual(len(log.recent(10)), 3)

    def test_recent_keeps_only_the_last_fifty(self):
        lines = [ev("2026-11-17T14:%02d:%02dZ" % divmod(i, 60), "tool", tool="Read", target="f%d" % i, phase="pre") for i in range(80)]
        log = EventLog(write_events(self.root, lines))
        log.refresh()
        events = log.recent(100)
        self.assertEqual(len(events), 50)
        self.assertEqual(events[0].target, "f79")

    def test_recent_resets_with_the_log(self):
        path = write_events(self.root, [START, PRE, POST])
        log = EventLog(path)
        log.refresh()
        write_events(self.root, [ev("2026-11-17T15:00:00Z", "start", item="other")])
        log.refresh()
        self.assertEqual([e.item for e in log.recent(5)], ["other"])
