"""The team-adapt command against made-up projects (multi-tool adapters spec, sections 9 and 10)."""
import io
import json
import os
import shutil
import unittest

from fixtures import make_project, valid_config
from team_adapt import cli
from team_status.config import TIER_NAMES


def config_with(*tools):
    cfg = valid_config()
    for tool in tools:
        cfg["tiers"][tool] = {tier: "%s-%s" % (tool, tier) for tier in TIER_NAMES}
    return cfg


class AdaptTest(unittest.TestCase):
    def project(self, cfg):
        root = make_project(config=cfg, commit=False)
        self.addCleanup(shutil.rmtree, root)
        return root

    def run_adapt(self, root):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main([root], out=out, err=err)
        return code, out.getvalue(), err.getvalue()

    def exists(self, root, *parts):
        return os.path.exists(os.path.join(root, *parts))

    def test_writes_cursor_files_and_agents_md(self):
        root = self.project(config_with("cursor"))
        code, out, err = self.run_adapt(root)
        self.assertEqual(code, 0, err)
        self.assertTrue(self.exists(root, ".cursor", "agents", "builder-standard.md"))
        self.assertTrue(self.exists(root, ".agents", "skills", "agent-team", "SKILL.md"))
        self.assertIn("<!-- agent-team:start -->", open(os.path.join(root, "AGENTS.md")).read())
        self.assertIn("wrote .cursor/agents/builder-standard.md", out)

    def test_second_run_is_allowed_and_keeps_owner_text(self):
        root = self.project(config_with("gemini"))
        with open(os.path.join(root, "GEMINI.md"), "w") as handle:
            handle.write("# Owner notes\n")
        self.assertEqual(self.run_adapt(root)[0], 0)
        self.assertEqual(self.run_adapt(root)[0], 0)
        text = open(os.path.join(root, "GEMINI.md")).read()
        self.assertTrue(text.startswith("# Owner notes\n\n<!-- agent-team:start -->"))
        self.assertEqual(text.count("<!-- agent-team:start -->"), 1)

    def test_unmarked_file_stops_everything(self):
        root = self.project(config_with("cursor"))
        os.makedirs(os.path.join(root, ".cursor", "agents"))
        with open(os.path.join(root, ".cursor", "agents", "builder-fast.md"), "w") as handle:
            handle.write("my own builder\n")
        code, out, err = self.run_adapt(root)
        self.assertEqual(code, 1)
        self.assertIn(".cursor/agents/builder-fast.md exists and was not written by team-adapt", err)
        self.assertIn("nothing written", err)
        self.assertFalse(self.exists(root, ".agents"))
        self.assertFalse(self.exists(root, "AGENTS.md"))

    def test_invalid_config_names_the_field(self):
        cfg = config_with("cursor")
        del cfg["tiers"]["cursor"]["fast"]
        code, out, err = self.run_adapt(self.project(cfg))
        self.assertEqual(code, 1)
        self.assertIn("team.json: tiers.cursor is missing tier: fast", err)

    def test_removed_tool_files_are_deleted(self):
        root = self.project(config_with("cursor", "gemini"))
        self.run_adapt(root)
        with open(os.path.join(root, ".claude", "team.json"), "w") as handle:
            json.dump(config_with("gemini"), handle)
        code, out, err = self.run_adapt(root)
        self.assertEqual(code, 0, err)
        self.assertFalse(self.exists(root, ".cursor", "agents", "builder-standard.md"))
        self.assertIn("deleted .cursor/agents/builder-standard.md", out)
        self.assertTrue(self.exists(root, ".gemini", "agents", "builder-standard.md"))

    def test_codex_and_cursor_together_warn(self):
        code, out, err = self.run_adapt(self.project(config_with("codex", "cursor")))
        self.assertEqual(code, 0)
        self.assertIn("Cursor also reads .codex/agents/", err)

    def test_claude_only_project_has_nothing_to_write(self):
        code, out, err = self.run_adapt(self.project(valid_config()))
        self.assertEqual(code, 0)
        self.assertIn("nothing to write", out)


if __name__ == "__main__":
    unittest.main()
