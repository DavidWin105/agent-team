"""Tests for the printed report."""
import unittest

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
