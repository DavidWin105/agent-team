"""team-adapt --init questions (multi-tool adapters spec, section 9)."""
import json
import os
import shutil
import tempfile
import unittest

from team_adapt import init, source
from team_status import config


def answers(*replies):
    queue = list(replies)
    return lambda prompt: queue.pop(0)


def template():
    with open(os.path.join(source.REPO_ROOT, "templates", "team.json"), encoding="utf-8") as handle:
        return json.load(handle)


CURSOR_RUN = ["cursor", "m1", "m2", "m3", "m4", "Test Owner", "tests", "npm test", "", "", ""]


class BuildConfigTest(unittest.TestCase):
    def test_cursor_answers_make_a_valid_config(self):
        cfg = init.build_config(answers(*CURSOR_RUN), template())
        self.assertEqual(config.validate(cfg), [])
        self.assertEqual(cfg["tiers"], {"cursor": {"strongest": "m1", "strong": "m2", "standard": "m3", "fast": "m4"}})
        self.assertEqual(cfg["checks"], [{"name": "tests", "run": "npm test"}])
        self.assertEqual(cfg["paths"]["plans"], "docs/plans/")

    def test_unknown_tool_and_empty_answers_are_asked_again(self):
        replies = ["vim", "", "gemini", "", "a", "b", "c", "d", "O", "", "t", "", "make", "", "p/", ""]
        cfg = init.build_config(answers(*replies), template())
        self.assertEqual(list(cfg["tiers"]), ["gemini"])
        self.assertEqual(cfg["tiers"]["gemini"]["strongest"], "a")
        self.assertEqual(cfg["checks"], [{"name": "t", "run": "make"}])
        self.assertEqual(cfg["paths"]["plans"], "p/")

    def test_template_is_not_changed(self):
        original = template()
        init.build_config(answers(*CURSOR_RUN), original)
        self.assertEqual(original, template())


class RunInitTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.lines = []

    def test_writes_team_json(self):
        self.assertTrue(init.run_init(self.root, answers(*CURSOR_RUN), self.lines.append))
        cfg, problems = config.load_config(self.root)
        self.assertEqual(problems, [])
        self.assertIn("wrote .claude/team.json", self.lines)

    def test_existing_file_is_kept_without_yes(self):
        path = os.path.join(self.root, ".claude", "team.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as handle:
            handle.write("{}")
        self.assertFalse(init.run_init(self.root, answers(""), self.lines.append))
        with open(path) as handle:
            self.assertEqual(handle.read(), "{}")


if __name__ == "__main__":
    unittest.main()
