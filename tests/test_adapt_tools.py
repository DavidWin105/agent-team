"""Codex, Cursor and Gemini output (multi-tool adapters spec, sections 6 and 7)."""
import os
import unittest

from fixtures import valid_config
from team_adapt import marker, project, source
from team_status.config import TIER_NAMES


def config_with(*tools):
    cfg = valid_config()
    for tool in tools:
        cfg["tiers"][tool] = {tier: "%s-%s" % (tool, tier) for tier in TIER_NAMES}
    return cfg


class ProjectOutputsTest(unittest.TestCase):
    def setUp(self):
        self.files, self.blocks = project.project_outputs(config_with("codex", "cursor", "gemini"))

    def agent(self, folder, name):
        return self.files[os.path.join(folder, name)]

    def test_claude_only_config_writes_nothing(self):
        self.assertEqual(project.project_outputs(valid_config()), ({}, {}))

    def test_every_role_gets_all_four_tiers_per_tool(self):
        for module in project.MODULES.values():
            names = sorted(rel for rel in self.files if rel.startswith(module.AGENT_DIR + os.sep))
            expected = sorted(
                os.path.join(module.AGENT_DIR, "%s-%s%s" % (role, tier, module.EXTENSION))
                for role in source.AGENT_ROLES
                for tier in TIER_NAMES
            )
            self.assertEqual(names, expected)

    def test_every_file_carries_the_marker(self):
        for rel, text in self.files.items():
            with self.subTest(rel):
                self.assertTrue(marker.is_generated(text))

    def test_instruction_blocks(self):
        self.assertEqual(set(self.blocks), {"AGENTS.md", "GEMINI.md"})
        self.assertIn(".agents/skills/agent-team/", self.blocks["AGENTS.md"])

    def test_codex_head(self):
        text = self.agent(os.path.join(".codex", "agents"), "code-reviewer-strong.toml")
        self.assertEqual(
            text.split("\n")[1:4],
            ['name = "code-reviewer-strong"', 'description = "%s"' % source.read_role("code-reviewer").description, 'model = "codex-strong"'],
        )
        self.assertTrue(text.split("\n")[4].startswith('developer_instructions = "# Code reviewer\\n'))

    def test_codex_parses_as_toml_when_tomllib_exists(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest("tomllib needs Python 3.11")
        data = tomllib.loads(self.agent(os.path.join(".codex", "agents"), "builder-fast.toml"))
        self.assertEqual((data["name"], data["model"]), ("builder-fast", "codex-fast"))
        self.assertIn("You build one item", data["developer_instructions"])

    def test_cursor_reviewer_is_readonly_and_builder_is_not(self):
        reviewer = self.agent(os.path.join(".cursor", "agents"), "code-reviewer-strong.md")
        builder = self.agent(os.path.join(".cursor", "agents"), "builder-standard.md")
        self.assertIn("\nname: code-reviewer-strong\n", reviewer)
        self.assertIn('\nmodel: "cursor-strong"\nreadonly: true\n---\n', reviewer)
        self.assertNotIn("readonly", builder.split("\n---\n")[0])

    def test_gemini_reviewer_has_no_edit_or_write_tools(self):
        reviewer = self.agent(os.path.join(".gemini", "agents"), "security-reviewer-strongest.md")
        builder = self.agent(os.path.join(".gemini", "agents"), "builder-standard.md")
        self.assertIn('\ntools: ["read_file", "read_many_files", "list_directory", "glob", "grep_search", "run_shell_command"]\n', reviewer)
        self.assertIn('"replace"', builder)
        self.assertIn('"write_file"', builder)

    def test_shared_skill_is_filled_for_other_tools(self):
        skill = self.files[os.path.join(project.SKILL_DIR, "SKILL.md")]
        self.assertTrue(skill.startswith("---\n# " + marker.SIGNATURE))
        for absent in ("{{", "${CLAUDE_PLUGIN_ROOT}", "agent-team:", "`/team-status`", "`/team-init`", "Flightdeck"):
            self.assertNotIn(absent, skill)
        self.assertIn("`builder-<tier>`", skill)
        self.assertIn(source.REPO_ROOT + "/scripts/team-status", skill)
        self.assertIn(source.REPO_ROOT + "/templates/plan.md", skill)

    def test_roles_name_no_claude_tool(self):
        for role in source.read_roles(source.REPO_ROOT):
            with self.subTest(role=role.name):
                self.assertNotIn("Bash", role.body)

    def test_rules_copy_has_html_marker(self):
        rules = self.files[os.path.join(project.SKILL_DIR, "rules.md")]
        self.assertTrue(rules.startswith("<!-- " + marker.SIGNATURE))
        self.assertIn("## Model choice", rules)

    def test_only_cursor_configured_writes_only_agents_md_block(self):
        files, blocks = project.project_outputs(config_with("cursor"))
        self.assertEqual(set(blocks), {"AGENTS.md"})
        self.assertFalse(any(rel.startswith(".codex") for rel in files))


if __name__ == "__main__":
    unittest.main()
