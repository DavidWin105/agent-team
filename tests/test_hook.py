import io
import json
import os
import shutil
import subprocess
import sys
import unittest

from team_status import hook
from fixtures import MISSING, make_project

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "team-event")


class FakeStdin:
    def __init__(self, data):
        self.buffer = io.BytesIO(data if isinstance(data, bytes) else data.encode("utf-8"))

    def read(self, size=-1):
        return self.buffer.read(size).decode("utf-8", "replace")


class HookTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project(commit=False)
        self.addCleanup(shutil.rmtree, self.root, True)
        self.log = os.path.join(self.root, ".claude/team/events.jsonl")

    def lines(self):
        try:
            with open(self.log, encoding="utf-8") as handle:
                return [json.loads(line) for line in handle.read().splitlines()]
        except FileNotFoundError:
            return []

    def payload(self, **fields):
        base = {"hook_event_name": "SubagentStart", "cwd": self.root,
                "agent_id": "a1", "agent_type": "agent-team:builder"}
        base.update(fields)
        return base

    def test_no_config_writes_nothing(self):
        other = make_project(MISSING, commit=False)
        self.addCleanup(shutil.rmtree, other, True)
        hook.handle(self.payload(cwd=other))
        self.assertFalse(os.path.exists(os.path.join(other, ".claude/team/events.jsonl")))

    def test_invalid_config_writes_nothing(self):
        other = make_project("{not json", commit=False)
        self.addCleanup(shutil.rmtree, other, True)
        hook.handle(self.payload(cwd=other))
        self.assertFalse(os.path.exists(os.path.join(other, ".claude/team/events.jsonl")))

    def test_non_team_agent_writes_nothing(self):
        hook.handle(self.payload(agent_type="other-plugin:thing"))
        hook.handle(self.payload(agent_type="Explore"))
        hook.handle({"hook_event_name": "PreToolUse", "cwd": self.root, "tool_name": "Edit"})
        self.assertEqual(self.lines(), [])

    def test_unknown_event_writes_nothing(self):
        hook.handle(self.payload(hook_event_name="Notification"))
        self.assertEqual(self.lines(), [])

    def test_specialist_is_recorded(self):
        hook.handle(self.payload(agent_type="devops-sre"))
        self.assertEqual(self.lines()[0]["agent"], "devops-sre")

    def test_start_tool_stop_lines(self):
        wt = os.path.join(self.root, ".claude/worktrees/subtract")
        hook.handle(self.payload(cwd=wt))
        hook.handle(self.payload(cwd=wt, hook_event_name="PreToolUse", tool_name="Edit",
                                 tool_input={"file_path": os.path.join(wt, "calc.py")}))
        hook.handle(self.payload(cwd=wt, hook_event_name="PostToolUse", tool_name="Edit"))
        hook.handle(self.payload(cwd=wt, hook_event_name="PostToolUseFailure", tool_name="Bash"))
        hook.handle(self.payload(cwd=wt, hook_event_name="SubagentStop"))
        hook.handle(self.payload())
        got = self.lines()
        self.assertEqual([x["event"] for x in got], ["start", "tool", "tool", "tool", "stop", "start"])
        self.assertEqual(got[0]["agent"], "builder")
        self.assertEqual(got[0]["agent_id"], "a1")
        self.assertEqual(got[0]["item"], "subtract")
        self.assertEqual(got[5]["item"], "")
        self.assertEqual((got[1]["phase"], got[1]["tool"]), ("pre", "Edit"))
        self.assertEqual(got[1]["target"], os.path.join(".claude/worktrees/subtract", "calc.py"))
        self.assertEqual((got[2]["phase"], got[2]["ok"]), ("post", True))
        self.assertEqual((got[3]["phase"], got[3]["ok"]), ("post", False))
        self.assertNotIn("ok", got[4])
        self.assertRegex(got[0]["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertFalse(os.path.exists(os.path.join(wt, ".claude/team/events.jsonl")))

    def test_bash_keeps_first_word_only(self):
        hook.handle(self.payload(hook_event_name="PreToolUse", tool_name="Bash",
                                 tool_input={"command": "npm test --token=abc123"}))
        self.assertEqual(self.lines()[0]["target"], "npm")
        with open(self.log, encoding="utf-8") as handle:
            self.assertNotIn("abc123", handle.read())

    def test_edit_target_relative_to_project(self):
        hook.handle(self.payload(hook_event_name="PreToolUse", tool_name="Read",
                                 tool_input={"file_path": os.path.join(self.root, "src", "a.py")}))
        self.assertEqual(self.lines()[0]["target"], os.path.join("src", "a.py"))

    def test_path_outside_project_keeps_file_name_only(self):
        hook.handle(self.payload(hook_event_name="PreToolUse", tool_name="Write",
                                 tool_input={"file_path": "/etc/secret/key.pem"}))
        self.assertEqual(self.lines()[0]["target"], "key.pem")

    def test_other_tool_has_empty_target(self):
        hook.handle(self.payload(hook_event_name="PreToolUse", tool_name="Grep",
                                 tool_input={"pattern": "password"}))
        self.assertEqual(self.lines()[0]["target"], "")

    def test_newline_in_path_stays_one_line(self):
        hook.handle(self.payload(hook_event_name="PreToolUse", tool_name="Edit",
                                 tool_input={"file_path": os.path.join(self.root, "a\nb.py")}))
        with open(self.log, "rb") as handle:
            data = handle.read()
        self.assertEqual(data.count(b"\n"), 1)
        self.assertEqual(self.lines()[0]["target"], "a\nb.py")

    def run_main(self, data, argv=()):
        out = io.StringIO()
        real, sys.stdout = sys.stdout, out
        try:
            code = hook.main(list(argv), FakeStdin(data))
        finally:
            sys.stdout = real
        self.assertEqual(out.getvalue(), "")
        return code

    def test_main_writes_from_stdin(self):
        self.assertEqual(self.run_main(json.dumps(self.payload())), 0)
        self.assertEqual(len(self.lines()), 1)

    def test_not_json_exit_0(self):
        self.assertEqual(self.run_main("nope{"), 0)

    def test_not_an_object_exit_0(self):
        self.assertEqual(self.run_main("[1, 2]"), 0)
        self.assertEqual(self.lines(), [])

    def test_huge_input_exit_0(self):
        big = json.dumps(self.payload(filler="x" * (1024 * 1024 + 10)))
        self.assertEqual(self.run_main(big), 0)
        self.assertEqual(self.lines(), [])

    def test_unwritable_log_exit_0(self):
        os.makedirs(self.log)  # a folder where the log file should be
        self.assertEqual(self.run_main(json.dumps(self.payload())), 0)

    def test_plan_flag_appends_plan_event(self):
        old = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, old)
        self.assertEqual(self.run_main("", ["--plan", "docs/plans/x.md"]), 0)
        got = self.lines()
        self.assertEqual((got[0]["event"], got[0]["target"]), ("plan", "x.md"))
        self.assertIn("ts", got[0])

    def test_project_root(self):
        self.assertEqual(hook.project_root(os.path.join(self.root, ".claude/worktrees/s1/sub")), self.root)
        self.assertEqual(hook.project_root(os.path.join(self.root, "a", "b")), self.root)
        self.assertIsNone(hook.project_root("/nonexistent-zzz/a"))

    def test_script_prints_nothing_and_exits_0(self):
        done = subprocess.run([sys.executable, "-I", SCRIPT], input=json.dumps(self.payload()).encode(),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, b"")
        self.assertEqual(len(self.lines()), 1)


if __name__ == "__main__":
    unittest.main()
