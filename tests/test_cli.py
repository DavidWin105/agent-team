"""End-to-end tests for team-status, including the entry script."""
import io
import os
import shutil
import subprocess
import sys
import unittest

from datetime import datetime, timezone

from fixtures import MISSING, PLAN_DRAFT, ROUTING_LOG, env_with, fake_gh, make_project, write_events
from team_status import cli

ENTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "team-status")
GH_ONE_PR = "echo '[{\"number\": 7, \"title\": \"feat: made-up item\"}]'"


class MainTest(unittest.TestCase):
    def run_main(self, root, env=None, now=None):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main([root], env=env, out=out, err=err, now=now)
        return code, out.getvalue(), err.getvalue()

    def project(self, **kwargs):
        root = make_project(**kwargs)
        self.addCleanup(shutil.rmtree, root)
        return root

    def gh_env(self):
        bindir = fake_gh(GH_ONE_PR)
        self.addCleanup(shutil.rmtree, bindir)
        return env_with(bindir)

    def test_full_report_exit_0(self):
        root = self.project(files={"plans/b-two.md": PLAN_DRAFT, "plans/routing-log.md": ROUTING_LOG})
        code, out, err = self.run_main(root, self.gh_env())
        self.assertEqual((code, err), (0, ""))
        self.assertIn("merge #7", out)
        self.assertIn("plan b-two: 2 unanswered questions", out)
        self.assertIn("fable", out)

    def test_snapshot_shows_agents_before_plans(self):
        root = self.project(files={"plans/b-two.md": PLAN_DRAFT})
        write_events(root, [
            {"ts": "2026-11-17T10:00:00Z", "event": "plan", "target": "p"},
            {"ts": "2026-11-17T10:06:48Z", "event": "start", "agent_id": "a1", "agent": "builder", "item": "subtract"},
            {"ts": "2026-11-17T10:09:50Z", "event": "tool", "agent_id": "a1", "agent": "builder",
             "item": "subtract", "tool": "Edit", "target": "test_calc.py", "phase": "pre"},
        ])
        now = datetime(2026, 11, 17, 10, 10, 0, tzinfo=timezone.utc)
        code, out, _ = self.run_main(root, self.gh_env(), now=now)
        self.assertEqual(code, 0)
        self.assertLess(out.index("AGENTS"), out.index("PLANS"))
        self.assertIn("subtract  builder        \u25b6 Edit test_calc.py  3m12s  1 calls", out)

    def test_snapshot_without_events_says_so(self):
        code, out, _ = self.run_main(self.project(), self.gh_env())
        self.assertIn("no agent events recorded yet (.claude/team/events.jsonl)", out)

    def test_missing_config_exit_1_with_hint(self):
        code, out, err = self.run_main(self.project(config=MISSING))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("team-status: no .claude/team.json", err)
        self.assertIn("run /team-init", err)

    def test_invalid_config_lists_every_problem(self):
        code, _, err = self.run_main(self.project(config='{"version": 1}'))
        self.assertEqual(code, 1)
        self.assertIn("missing key: owner", err)
        self.assertIn("missing key: paths", err)

    def test_not_a_repository_exit_1(self):
        code, _, err = self.run_main(self.project(commit=False))
        self.assertEqual(code, 1)
        self.assertIn("is not a git repository with a commit", err)

    def test_gh_missing_still_prints_report(self):
        git_dir = os.path.dirname(shutil.which("git"))
        if shutil.which("gh", path=git_dir):
            self.skipTest("gh lives next to git on this machine, so it cannot be hidden")
        code, out, _ = self.run_main(self.project(), {**os.environ, "PATH": git_dir})
        self.assertEqual(code, 0)
        self.assertIn("not checked: gh unavailable", out)

    def test_entry_script_runs_isolated(self):
        root = self.project()
        result = subprocess.run(
            [sys.executable, "-I", ENTRY, root], env=self.gh_env(), capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agent-team · ", result.stdout)


if __name__ == "__main__":
    unittest.main()
