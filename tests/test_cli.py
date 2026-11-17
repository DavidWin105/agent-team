"""End-to-end tests for team-status, including the entry script."""
import io
import os
import shutil
import re
import subprocess
import sys
import threading
import unittest

from datetime import datetime, timezone

from fixtures import MISSING, PLAN_DRAFT, ROUTING_LOG, env_with, fake_gh, make_project, write_events
from team_status import cards, cli
from team_status.repo import PullRequest

ENTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "team-status")
GH_ONE_PR = "echo '[{\"number\": 7, \"title\": \"feat: made-up item\"}]'"


CLEAR = "\x1b[H\x1b[2J"
NOW = datetime(2026, 11, 17, 10, 10, 0, tzinfo=timezone.utc)
CLOCK = NOW.astimezone().strftime("%H:%M:%S")
PLAN_EVENTS = [
    {"ts": "2026-11-17T10:00:00Z", "event": "plan", "target": "plans/2026-11-17-calc.md"},
    {"ts": "2026-11-17T10:06:48Z", "event": "start", "agent_id": "a1", "agent": "builder", "item": "subtract"},
]


def join_gh_threads():
    """Wait (bounded) for the background gh threads, so no test leaves one running."""
    for thread in threading.enumerate():
        if thread.name == cli.GH_THREAD:
            thread.join(10)
WARNING = "WARNING: .claude/team/events.jsonl is not ignored by git; add .claude/team/ to .gitignore"


class WatchTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project()
        self.addCleanup(shutil.rmtree, self.root)
        bindir = fake_gh(GH_ONE_PR)
        self.addCleanup(shutil.rmtree, bindir)
        self.env = env_with(bindir)

    def watch(self, argv, sleep, max_frames=2, width=80, now=None, height=0):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(argv, env=self.env, out=out, err=err, sleep=sleep, max_frames=max_frames, width=width, color=False,
                        now=now, height=height)
        join_gh_threads()
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

    def test_watch_uses_cards_when_wide_and_table_when_narrow(self):
        write_events(self.root, [{"ts": "2026-11-17T10:00:00Z", "event": "start", "agent_id": "a1",
                                  "agent": "builder", "item": "first-item"}])
        _, wide, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=1, width=120)
        _, narrow, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=1, width=99)
        self.assertIn("┌", wide)
        self.assertIn("WAITING ON YOU", wide)
        self.assertIn("builder · sonnet", wide)
        self.assertNotIn("┌", narrow)
        self.assertIn("WAITING ON OWNER", narrow)
        self.assertIn("1 silent", wide)

    def test_snapshot_stays_a_table_even_when_wide(self):
        out = io.StringIO()
        cli.main([self.root], env=self.env, out=out, err=io.StringIO(), width=200, color=True)
        self.assertNotIn("┌", out.getvalue())
        self.assertNotIn("\x1b", out.getvalue())
        self.assertIn("WAITING ON OWNER", out.getvalue())

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

    def start_event(self, **fields):
        line = {"ts": "2026-11-17T10:00:00Z", "event": "start", "agent_id": "a1", "agent": "builder", "item": "first-item"}
        line.update(fields)
        return line

    def test_watch_warns_in_every_frame_when_log_not_ignored(self):
        write_events(self.root, [self.start_event()])
        for width in (80, 120):
            code, out, err = self.watch(["--watch", self.root], lambda s: None, width=width)
            frames = out.split(CLEAR)[1:]
            self.assertEqual((code, err, len(frames)), (0, "", 2))
            for frame in frames:
                self.assertIn(WARNING + "\n", frame, width)

    def test_watch_no_warning_when_ignored(self):
        self.ignore_log()
        write_events(self.root, [self.start_event()])
        for width in (80, 120):
            code, out, err = self.watch(["--watch", self.root], lambda s: None, width=width)
            self.assertEqual(err, "")
            self.assertNotIn("WARNING", out)

    def test_no_warning_while_the_log_does_not_exist(self):
        for width in (80, 120):
            _, out, _ = self.watch(["--watch", self.root], lambda s: None, width=width)
            self.assertNotIn("WARNING", out)

    def test_snapshot_warns_when_log_not_ignored(self):
        write_events(self.root, [self.start_event()])
        out, err = io.StringIO(), io.StringIO()
        cli.main([self.root], env=self.env, out=out, err=err)
        self.assertEqual(err.getvalue(), "")
        self.assertNotIn(CLEAR, out.getvalue())
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[1], WARNING)
        self.assertLess(lines.index(WARNING), lines.index("AGENTS"))
        self.ignore_log()
        out = io.StringIO()
        cli.main([self.root], env=self.env, out=out, err=io.StringIO())
        self.assertNotIn("WARNING", out.getvalue())

    def test_cards_show_every_log_note(self):
        self.ignore_log()
        _, out, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=1, width=120)
        self.assertIn("\nno agent events recorded yet (.claude/team/events.jsonl)\n", out)
        write_events(self.root, [self.start_event(agent_id=""), self.start_event(agent_id=""), "{broken"])
        _, out, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=1, width=120)
        self.assertIn("\nfirst-item · builder: 2 agents share this row\n", out)
        self.assertIn("\n1 line not read\n", out)
        self.assertIn("\nno plan marker: showing every event\n", out)
        write_events(self.root, [self.start_event(), {"ts": "2026-11-17T10:01:00Z", "event": "plan", "target": "p.md"}])
        _, out, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=1, width=120)
        self.assertIn("\nno agent activity since the last plan marker\n", out)
        self.assertNotIn("no plan marker", out)

    def test_watch_reads_the_terminal_width_every_frame(self):
        sizes = [os.terminal_size((120, 40)), os.terminal_size((80, 40))]
        real = cli.shutil.get_terminal_size
        cli.shutil.get_terminal_size = lambda *a, **k: sizes.pop(0)
        self.addCleanup(setattr, cli.shutil, "get_terminal_size", real)
        self.ignore_log()
        out = io.StringIO()
        cli.main(["--watch", self.root], env=self.env, out=out, err=io.StringIO(), sleep=lambda s: None,
                 max_frames=2, color=False)
        frames = out.getvalue().split(CLEAR)
        self.assertIn("WAITING ON YOU", frames[1])
        self.assertIn("WAITING ON OWNER", frames[2])
        self.assertEqual(sizes, [])

    def test_git_and_gh_gathered_every_tenth_frame(self):
        calls = []
        real = cli.repo.open_prs
        cli.repo.open_prs = lambda *a, **k: calls.append(1) or []
        self.addCleanup(setattr, cli.repo, "open_prs", real)
        self.ignore_log()
        self.watch(["--watch", self.root], lambda s: join_gh_threads(), max_frames=11)
        self.assertEqual(len(calls), 2)

    def test_header_shows_plan_name_and_clock(self):
        self.ignore_log()
        write_events(self.root, PLAN_EVENTS)
        _, wide, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=1, width=120, now=NOW)
        first = wide.split(CLEAR)[1].splitlines()[0]
        self.assertTrue(first.startswith("AGENT TEAM · plan: plans/2026-11-17-calc.md"), first)
        self.assertTrue(first.endswith(CLOCK), first)
        self.assertEqual(cards.display_width(first), 120)
        _, narrow, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=1, width=80, now=NOW)
        lines = narrow.split(CLEAR)[1].splitlines()
        self.assertRegex(lines[0], r"^agent-team · .* · main [0-9a-f]+ · %s$" % CLOCK)
        self.assertIn("AGENTS   plan: plans/2026-11-17-calc.md", lines)

    def test_watch_reads_the_terminal_height_every_frame(self):
        sizes = [os.terminal_size((120, 12)), os.terminal_size((120, 0))]
        real = cli.shutil.get_terminal_size
        cli.shutil.get_terminal_size = lambda *a, **k: sizes.pop(0)
        self.addCleanup(setattr, cli.shutil, "get_terminal_size", real)
        self.ignore_log()
        write_events(self.root, PLAN_EVENTS[:1] + [dict(PLAN_EVENTS[1], agent_id="a%d" % n, item="item%d" % n)
                                                   for n in range(8)])
        out = io.StringIO()
        cli.main(["--watch", self.root], env=self.env, out=out, err=io.StringIO(), sleep=lambda s: None,
                 max_frames=2, color=False, now=NOW)
        join_gh_threads()
        frames = out.getvalue().split(CLEAR)
        self.assertIn("\nAGENTS   plan: plans/2026-11-17-calc.md\n", frames[1])  # 12 lines: no card row fits
        self.assertFalse(set("┌│└") & set(frames[1]))
        self.assertIn("┌", frames[2])
        self.assertNotIn("more agents", frames[2])
        self.assertIn("item7", frames[2])
        self.assertEqual(sizes, [])

    def test_short_terminal_falls_back_to_table(self):
        self.ignore_log()
        write_events(self.root, PLAN_EVENTS[:1] + [dict(PLAN_EVENTS[1], agent_id="a%d" % n, item="item%d" % n)
                                                   for n in range(5)])
        _, out, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=1, width=120, now=NOW, height=24)
        frame = out.split(CLEAR)[1]
        self.assertFalse(set("┌│└") & set(frame))
        self.assertIn("\nAGENTS   plan: plans/2026-11-17-calc.md\n", frame)
        self.assertTrue(frame.splitlines()[0].endswith(" · " + CLOCK))
        self.assertTrue(frame.endswith("\n"))
        _, out, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=1, width=120, now=NOW, height=25)
        frame = out.split(CLEAR)[1]
        self.assertEqual(len(frame.splitlines()), 25)
        self.assertIn("+1 more agents (use a taller terminal)", frame)
        os.remove(os.path.join(self.root, ".claude/team/events.jsonl"))
        _, out, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=1, width=120, now=NOW, height=5)
        self.assertIn("WAITING ON OWNER", out)
        self.assertNotIn("┌", out)


    def test_card_frame_as_tall_as_the_screen_does_not_scroll(self):
        self.ignore_log()
        write_events(self.root, PLAN_EVENTS)
        _, out, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=2, width=120, now=NOW)
        tall = len(out.split(CLEAR)[1].splitlines())
        _, out, _ = self.watch(["--watch", self.root], lambda s: None, max_frames=2, width=120, now=NOW, height=tall)
        frames = out.split(CLEAR)
        self.assertEqual(len(frames[1].splitlines()), tall)
        self.assertEqual(frames[1].count("\n"), tall - 1)  # no newline after the last line
        self.assertTrue(frames[2].endswith("┘\n"))  # the last frame ends the line before the shell prompt


class GhThreadTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project()
        self.addCleanup(shutil.rmtree, self.root)
        with open(os.path.join(self.root, ".gitignore"), "w", encoding="utf-8") as handle:
            handle.write(".claude/team/events.jsonl\n")
        self.real = cli.repo.open_prs
        self.addCleanup(setattr, cli.repo, "open_prs", self.real)
        self.addCleanup(join_gh_threads)

    def watch(self, sleep, max_frames):
        out = io.StringIO()
        code = cli.main(["--watch", self.root], out=out, err=io.StringIO(), sleep=sleep, max_frames=max_frames,
                        width=120, height=0, color=False, now=NOW)
        return code, out.getvalue().split(CLEAR)

    def test_slow_gh_does_not_delay_frames(self):
        started, release = threading.Event(), threading.Event()

        def slow(*args, **kwargs):
            started.set()
            release.wait(10)
            return [PullRequest(7, "feat: slow")]

        cli.repo.open_prs = slow
        slept = []

        def sleep(seconds):
            slept.append(seconds)
            if len(slept) == 2:  # frames 0 and 1 are drawn while gh still hangs
                self.assertTrue(started.wait(10))
                release.set()
                join_gh_threads()

        code, frames = self.watch(sleep, max_frames=3)
        self.assertEqual(code, 0)
        for frame in frames[1:3]:
            self.assertIn("pull requests: not checked", frame)
            self.assertNotIn("merge #7", frame)
        self.assertIn("merge #7", frames[3])
        self.assertNotIn("not checked", frames[3])

    def test_only_one_gh_thread_at_a_time(self):
        lock = threading.Lock()
        calls, active, peak = [], [0], [0]
        release = threading.Event()

        def blocking(*args, **kwargs):
            with lock:
                calls.append(1)
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            release.wait(10)
            with lock:
                active[0] -= 1
            return []

        cli.repo.open_prs = blocking
        code, frames = self.watch(lambda s: None, max_frames=21)  # frames 0, 10 and 20 would start one
        self.assertEqual((code, len(frames)), (0, 22))
        self.assertEqual(len([t for t in threading.enumerate() if t.name == cli.GH_THREAD]), 1)
        release.set()
        join_gh_threads()
        self.assertEqual((len(calls), peak[0]), (1, 1))

        calls.clear()
        release.clear()
        count = []

        def sleep(seconds):
            count.append(1)
            if len(count) == 5:  # let the first gh call finish before frame 10
                release.set()
                join_gh_threads()
                release.clear()

        self.watch(sleep, max_frames=11)
        release.set()
        join_gh_threads()
        self.assertEqual((len(calls), peak[0]), (2, 1))

    def test_gh_thread_is_a_daemon(self):
        seen = []
        cli.repo.open_prs = lambda *a, **k: seen.append(threading.current_thread()) or []
        self.watch(lambda s: join_gh_threads(), max_frames=1)
        join_gh_threads()
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0].daemon)
        self.assertEqual(seen[0].name, cli.GH_THREAD)


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
        self.assertIn("subtract  builder        \u25b6 Edit test_calc.py  3m12s  1 call", out)

    def test_snapshot_shows_plan_name_without_clock(self):
        root = self.project()
        write_events(root, PLAN_EVENTS)
        code, out, _ = self.run_main(root, self.gh_env(), now=NOW)
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertIn("AGENTS   plan: plans/2026-11-17-calc.md", lines)
        self.assertNotRegex(lines[0], r"\d\d:\d\d:\d\d")
        self.assertNotIn(CLEAR, out)
        self.assertEqual(self.run_main(root, self.gh_env(), now=NOW)[1], out)

    def test_snapshot_calls_gh_directly(self):
        root = self.project()
        real = cli.repo.open_prs
        self.addCleanup(setattr, cli.repo, "open_prs", real)
        seen = []
        cli.repo.open_prs = lambda *a, **k: seen.append(threading.current_thread()) or [PullRequest(9, "x")]
        _, out, _ = self.run_main(root)
        self.assertEqual(seen, [threading.main_thread()])
        self.assertIn("merge #9", out)

    def test_command_doc_mentions_agents_and_watch(self):
        with open(os.path.join(os.path.dirname(ENTRY), "..", "commands", "team-status.md"), encoding="utf-8") as handle:
            text = handle.read()
        front, body = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S).groups()
        description = next(line for line in front.splitlines() if line.startswith("description:"))
        for part in (description, body):
            self.assertIn("AGENTS", part)
            self.assertIn("--watch", part)

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
