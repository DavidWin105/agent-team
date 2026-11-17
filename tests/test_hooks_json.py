"""hooks/hooks.json must register exactly the five events, in exec form."""
import json
import os
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
EVENTS = {"SubagentStart", "SubagentStop", "PreToolUse", "PostToolUse", "PostToolUseFailure"}


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return json.load(handle)


class HooksJsonTest(unittest.TestCase):
    def test_registers_exactly_the_five_events(self):
        self.assertEqual(set(load("hooks", "hooks.json")["hooks"]), EVENTS)

    def test_every_handler_is_exec_form_with_timeout(self):
        for event, groups in load("hooks", "hooks.json")["hooks"].items():
            self.assertEqual(len(groups), 1, event)
            self.assertEqual(groups[0]["matcher"], "", event)
            self.assertEqual(len(groups[0]["hooks"]), 1, event)
            for handler in groups[0]["hooks"]:
                self.assertEqual(handler["type"], "command")
                self.assertEqual(handler["command"], "python3")
                self.assertEqual(handler["args"][0], "-I")
                self.assertTrue(handler["args"][1].endswith("scripts/team-event"))
                self.assertEqual(handler["timeout"], 5)

    def test_script_exists_relative_to_plugin_root(self):
        handler = load("hooks", "hooks.json")["hooks"]["SubagentStart"][0]["hooks"][0]
        rel = handler["args"][1].replace("${CLAUDE_PLUGIN_ROOT}/", "")
        self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)))

    def test_plugin_version(self):
        self.assertEqual(load(".claude-plugin", "plugin.json")["version"], "0.2.0")


if __name__ == "__main__":
    unittest.main()
