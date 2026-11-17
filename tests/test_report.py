"""Tests for the printed report."""
import shutil
import unittest
from datetime import datetime, timezone

from fixtures import make_project, write_events
from team_status.events import EventLog
from team_status.plans import Plan
from team_status.repo import Head, PullRequest
from team_status.report import render
from team_status.routing import ModelTotals, Summary

HEAD = Head("main", "abc1234")
PLANS = [
    Plan("a-one", "Approved 2026-11-17", "Test lead (local_0000)", 0, None),
    Plan("b-two", "Draft", "scheduled batch run", 2, None),
    Plan("c-bad", None, None, 0, "no front matter"),
]
SUMMARY = Summary({"fable": ModelTotals(1, 110638, 0, 3.6, (1, 6, 9), 5)}, 1)
ONE_PR = [PullRequest(7, "feat: made-up item")]


def full(prs=ONE_PR, summary=SUMMARY):
    return render("demo", HEAD, PLANS, ["feat/item-a"], prs, summary, "plans/log.md")


NOW = datetime(2026, 11, 17, 10, 10, 0, tzinfo=timezone.utc)
EVENTS_PATH = ".claude/team/events.jsonl"


def ev(ts, event, agent="builder", item="subtract", agent_id="a1", **extra):
    return dict(ts="2026-11-17T" + ts + "Z", event=event, agent=agent, item=item, agent_id=agent_id, **extra)


class AgentsSectionTest(unittest.TestCase):
    def log(self, lines):
        root = make_project(commit=False)
        self.addCleanup(shutil.rmtree, root)
        log = EventLog(write_events(root, lines))
        log.refresh()
        return log

    def agents(self, lines):
        return render("demo", HEAD, PLANS, [], [], SUMMARY, "plans/log.md", agents=self.log(lines), now=NOW)

    def running(self):
        return [
            ev("10:00:00", "plan", target="p", agent_id=""),
            ev("10:06:48", "start"),
            ev("10:06:50", "tool", tool="Edit", target="test_calc.py", phase="pre"),
        ]

    def test_agents_section_rows(self):
        lines = [ev("10:00:00", "plan", target="p", agent_id=""), ev("10:06:48", "start")]
        for n in range(11):
            lines.append(ev("10:07:%02d" % n, "tool", tool="Read", target="a.py", phase="pre"))
        lines.append(ev("10:09:50", "tool", tool="Edit", target="test_calc.py", phase="pre"))
        text = self.agents(lines)
        self.assertIn("AGENTS\n", text)
        self.assertIn("  subtract  builder        \u25b6 Edit test_calc.py  3m12s  12 calls\n", text)

    def test_done_failed_silent(self):
        base = [ev("10:00:00", "plan", target="p", agent_id="")]
        done = self.agents(base + [ev("10:08:00", "start"), ev("10:09:00", "stop", ok=True)])
        self.assertIn("\u2713 done", done)
        failed = self.agents(base + [ev("10:08:00", "start"), ev("10:09:00", "stop", ok=False)])
        self.assertIn("\u2717 failed", failed)
        silent = self.agents(base + [ev("10:01:00", "start")])
        self.assertIn("? silent", silent)

    def test_running_without_doing(self):
        text = self.agents([ev("10:00:00", "plan", target="p", agent_id=""), ev("10:09:50", "start")])
        self.assertIn("\u25b6 running", text)

    def test_no_events_message(self):
        message = "  no agent events recorded yet (.claude/team/events.jsonl)\n"
        self.assertIn("AGENTS\n" + message, full())
        self.assertIn("AGENTS\n" + message, self.agents([]))

    def test_shared_row_note(self):
        lines = [
            ev("10:00:00", "plan", target="p", agent_id=""),
            ev("10:08:00", "start", agent_id=""),
            ev("10:08:01", "start", agent_id=""),
        ]
        self.assertIn("  2 agents share this row\n", self.agents(lines))

    def test_unread_line_note(self):
        lines = [ev("10:00:00", "plan", target="p", agent_id=""), ev("10:08:00", "start"), "junk", "{"]
        self.assertIn("  2 lines not read\n", self.agents(lines))

    def test_no_plan_marker_note(self):
        text = self.agents([ev("10:08:00", "start")])
        self.assertIn("  no plan marker: showing every event\n", text)
        self.assertNotIn("no plan marker", self.agents(self.running()))

    def test_agents_between_header_and_plans(self):
        text = self.agents(self.running())
        self.assertLess(text.index("agent-team \u00b7"), text.index("AGENTS"))
        self.assertLess(text.index("AGENTS"), text.index("PLANS"))


class RenderTest(unittest.TestCase):
    def test_sections_in_order(self):
        text = full()
        order = [text.index(title) for title in ("PLANS", "WORKTREES", "OPEN PRs", "WAITING ON OWNER", "ROUTING LOG")]
        self.assertEqual(order, sorted(order))
        self.assertTrue(text.startswith("agent-team · demo · main abc1234\n"))

    def test_plan_rows(self):
        text = full()
        self.assertRegex(text, r"a-one\s+Approved\s+lead: Test lead \(local_0000\)")
        self.assertRegex(text, r"c-bad\s+no front matter")

    def test_worktrees_line(self):
        self.assertIn("WORKTREES   1   feat/item-a", full())

    def test_waiting_lists_merges_questions_and_drafts(self):
        text = full()
        self.assertIn("  merge #7", text)
        self.assertIn("  plan b-two: 2 unanswered questions", text)
        self.assertIn("  plan b-two: still Draft", text)

    def test_gh_unavailable_is_never_shown_as_zero(self):
        text = full(prs=None)
        self.assertIn("OPEN PRs    not checked: gh unavailable", text)
        self.assertNotIn("OPEN PRs    0", text)
        self.assertIn("  pull requests: not checked", text)

    def test_nothing_waiting(self):
        text = render("demo", HEAD, [], [], [], SUMMARY, "plans/log.md")
        self.assertIn("WAITING ON OWNER\n  nothing", text)
        self.assertIn("PLANS\n  none found", text)

    def test_routing_totals_and_unread_rows(self):
        text = full()
        self.assertRegex(text, r"fable\s+1\s+110,638\s+3\.6\s+1/6/9\s+5\s+0")
        self.assertIn("rows not read: 1", text)

    def test_missing_routing_log(self):
        self.assertIn("no routing log at plans/log.md", full(summary=None))

    def test_unreadable_routing_log(self):
        text = full(summary=Summary({}, 0, "cannot be read"))
        self.assertIn("ROUTING LOG\n  routing log at plans/log.md cannot be read", text)


if __name__ == "__main__":
    unittest.main()
