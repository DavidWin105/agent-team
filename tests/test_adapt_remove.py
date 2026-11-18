"""team-adapt --remove takes the agent-team files back out of a project."""
import io
import os
import shutil
import unittest

from fixtures import make_project
from team_adapt import cli
from test_adapt_cli import config_with, mock_ask


class RemoveTest(unittest.TestCase):
    def project(self, cfg, files=None):
        root = make_project(config=cfg, files=files, commit=False)
        self.addCleanup(shutil.rmtree, root)
        return root

    def run_cli(self, argv, replies=()):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(argv, out=out, err=err, ask=mock_ask(replies))
        return code, out.getvalue(), err.getvalue()

    def exists(self, root, *parts):
        return os.path.exists(os.path.join(root, *parts))

    def read(self, root, rel):
        with open(os.path.join(root, rel), encoding="utf-8") as handle:
            return handle.read()

    def adapted(self, files=None):
        root = self.project(config_with("cursor", "gemini"), files=files)
        code, _, err = self.run_cli([root])
        self.assertEqual(code, 0, err)
        return root

    def test_yes_removes_everything_the_team_added(self):
        root = self.adapted(files={".gitignore": "node_modules/\n.claude/team/\n", ".claude/team/events.jsonl": "{}\n"})
        code, out, err = self.run_cli([root, "--remove"], ["y"])
        self.assertEqual(code, 0, err)
        for parts in ((".cursor",), (".gemini",), (".agents",), ("AGENTS.md",), ("GEMINI.md",), (".claude",)):
            self.assertFalse(self.exists(root, *parts), parts)
        self.assertEqual(self.read(root, ".gitignore"), "node_modules/\n")
        self.assertIn("delete .claude/team.json", out)

    def test_owner_text_and_hand_written_files_stay(self):
        root = self.adapted(files={"AGENTS.md": "# Mine\n", ".cursor/agents/mine.md": "hand written\n"})
        code, _, err = self.run_cli([root, "--remove"], ["yes"])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.read(root, "AGENTS.md"), "# Mine\n")
        self.assertEqual(self.read(root, ".cursor/agents/mine.md"), "hand written\n")
        self.assertFalse(self.exists(root, ".cursor", "agents", "builder-standard.md"))

    def test_no_answer_changes_nothing(self):
        root = self.adapted()
        before = sorted(os.listdir(root))
        code, _, err = self.run_cli([root, "--remove"], ["n"])
        self.assertEqual(code, 1)
        self.assertIn("nothing removed", err)
        self.assertEqual(sorted(os.listdir(root)), before)
        self.assertTrue(self.exists(root, ".cursor", "agents", "builder-standard.md"))

    def test_end_of_input_changes_nothing(self):
        root = self.adapted()
        code, _, _ = self.run_cli([root, "--remove"], [EOFError()])
        self.assertEqual(code, 1)
        self.assertTrue(self.exists(root, ".claude", "team.json"))

    def test_invalid_team_json_is_still_removed(self):
        root = self.project("{not json")
        code, _, err = self.run_cli([root, "--remove"], ["y"])
        self.assertEqual(code, 0, err)
        self.assertFalse(self.exists(root, ".claude"))

    def test_claude_only_project_loses_only_its_config(self):
        root = self.project(config_with(), files={"docs/plans/a.md": "plan\n", ".claude/settings.json": "{}\n"})
        code, _, err = self.run_cli([root, "--remove"], ["y"])
        self.assertEqual(code, 0, err)
        self.assertFalse(self.exists(root, ".claude", "team.json"))
        self.assertTrue(self.exists(root, ".claude", "settings.json"))
        self.assertTrue(self.exists(root, "docs", "plans", "a.md"))

    def test_nothing_to_remove_does_not_ask(self):
        root = self.project(config_with())
        os.remove(os.path.join(root, ".claude", "team.json"))
        code, out, _ = self.run_cli([root, "--remove"], [])
        self.assertEqual(code, 0)
        self.assertIn("nothing to remove", out)

    def test_symlinked_config_outside_is_refused(self):
        outside = make_project(commit=False)
        self.addCleanup(shutil.rmtree, outside)
        root = self.project(config_with())
        os.remove(os.path.join(root, ".claude", "team.json"))
        os.symlink(os.path.join(outside, ".claude", "team.json"), os.path.join(root, ".claude", "team.json"))
        code, _, err = self.run_cli([root, "--remove"], [])
        self.assertEqual(code, 1)
        self.assertIn("outside the project", err)
        self.assertTrue(os.path.exists(os.path.join(outside, ".claude", "team.json")))


if __name__ == "__main__":
    unittest.main()
