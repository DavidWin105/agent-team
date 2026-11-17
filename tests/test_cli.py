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


CLEAR = "\x1b[H\x1b[2J"


class WatchTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project()
        self.addCleanup(shutil.rmtree, self.root)
        bindir = fake_gh(GH_ONE_PR)
        self.addCleanup(shutil.rmtree, bindir)
        self.env = env_with(bindir)

    def watch(self, argv, sleep, max_frames=2):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(argv, env=self.env, out=out, err=err, sleep=sleep, max_frames=max_frames)
        return code, out.getvalue(), err.getvalue()

    def ignore_log(self):
        with open(os.path.join(self.root, ".gitignore"), "w", encoding="utf-8") as handle:
            handle.write(".claude/team/events.jsonl\n")

    def test_watch_draws_two_frames_and_sees_new_event(self):
        write_events(self.root, [{"ts": "2026-11-17T10:00:00Z", "event": "start", "agent_id": "a1",
                                  "agent": "builder", "item": "first-item"}])
        slept = []

        def sleep(seconds):
            slept.append(seconds)
            with open(os.path.join(self.root, ".claude/team/events.jsonl"), "a", encoding="utf-8") as handle:
                handle.write('{"ts": "2026-11-17T10:01:00Z", "event": "start", "agent_id": "a2", '
                             '"agent": "builder", "item": "second-item"}\n')

        code, out, _ = self.watch(["--watch", self.root], sleep)
        frames = out.split(CLEAR)
        self.assertEqual(code, 0)
        self.assertEqual(frames[0], "")
        self.assertEqual(len(frames), 3)
        self.assertNotIn("second-item", frames[1])
        self.assertIn("first-item", frames[1])
        self.assertIn("second-item", frames[2])
        self.assertEqual(slept, [1])

    def test_watch_flag_may_follow_the_folder(self):
        code, out, _ = self.watch([self.root, "--watch"], lambda s: None, max_frames=1)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith(CLEAR))

    def test_watch_exit_0_on_ctrl_c(self):
        def sleep(seconds):
            raise KeyboardInterrupt

        code, out, err = self.watch(["--watch", self.root], sleep, max_frames=None)
        self.assertEqual(code, 0)
        self.assertEqual(out.count(CLEAR), 1)
        self.assertNotIn("Traceback", err)

    def test_watch_warns_once_when_log_not_ignored(self):
        code, _, err = self.watch(["--watch", self.root], lambda s: None)
        self.assertEqual(err, "team-status: .claude/team/events.jsonl is not ignored by git\n")

    def test_watch_no_warning_when_ignored(self):
        self.ignore_log()
        code, _, err = self.watch(["--watch", self.root], lambda s: None)
        self.assertEqual(err, "")

    def test_snapshot_never_warns(self):
        out, err = io.StringIO(), io.StringIO()
        cli.main([self.root], env=self.env, out=out, err=err)
        self.assertEqual(err.getvalue(), "")
        self.assertNotIn(CLEAR, out.getvalue())

    def test_git_and_gh_gathered_every_tenth_frame(self):
        calls = []
        real = cli.repo.open_prs
        cli.repo.open_prs = lambda *a, **k: calls.append(1) or real(*a, **k)
        self.addCleanup(setattr, cli.repo, "open_prs", real)
        self.ignore_log()
        self.watch(["--watch", self.root], lambda s: None, max_frames=11)
        self.assertEqual(len(calls), 2)


class WatchHeadTest(WatchTest):
    def test_head_reread_at_frame_10_and_not_before(self):
        heads = []
        real = cli.repo.git_head

        def counting(*args, **kwargs):
            result = real(*args, **kwargs)
            heads.append(result)
            return result

        cli.repo.git_head = counting
        self.addCleanup(setattr, cli.repo, "git_head", real)
        self.ignore_log()
        self.watch(["--watch", self.root], lambda s: None, max_frames=10)
        self.assertEqual(len(heads), 1)  # startup only
        heads.clear()
        self.watch(["--watch", self.root], lambda s: None, max_frames=11)
        self.assertEqual(len(heads), 2)  # startup + frame 10

    def test_head_shown_follows_new_commit_at_frame_10(self):
        self.ignore_log()
        count = []

        def sleep(seconds):
            count.append(1)
            if len(count) == 5:
                subprocess.run(["git", "checkout", "-q", "-b", "later"], cwd=self.root, check=True)

        _, out, _ = self.watch(["--watch", self.root], sleep, max_frames=11)
        frames = out.split(CLEAR)
        self.assertNotIn("later", frames[10])
        self.assertIn("later", frames[11])

    def test_head_kept_when_git_fails_on_refresh(self):
        self.ignore_log()
        real = cli.repo.git_head
        calls = []

        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) > 1:
                raise cli.repo.NotARepo("x")
            return real(*args, **kwargs)

        cli.repo.git_head = flaky
        self.addCleanup(setattr, cli.repo, "git_head", real)
        code, out, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=11)
        self.assertEqual(code, 0)
        self.assertIn("main", out.split(CLEAR)[11])


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
