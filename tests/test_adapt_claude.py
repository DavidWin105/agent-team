"""Claude Code output must equal the committed plugin files (multi-tool adapters spec, sections 5 and 11)."""
import os
import shutil
import tempfile
import unittest

from team_adapt import claude, marker, render, source


class RenderTest(unittest.TestCase):
    TEXT = "a\n{{claude}} c {{agent builder}}\n{{other}} o {{agent builder}} {{plugin_root}}/x\n{{other}}\nz {{templates}}\n"

    def test_claude_keeps_claude_lines_and_names_plugin_agents(self):
        self.assertEqual(render.render(self.TEXT, "claude", "R"), "a\nc `agent-team:builder`\nz R/templates\n")

    def test_other_keeps_other_lines_and_names_tier_agents(self):
        self.assertEqual(render.render(self.TEXT, "other", "R"), "a\no `builder-<tier>` R/x\n\nz R/templates\n")

    def test_unknown_family_is_an_error(self):
        with self.assertRaises(ValueError):
            render.render(self.TEXT, "vim", "R")


class SourceTest(unittest.TestCase):
    def make_repo(self, role_text):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        os.makedirs(os.path.join(root, "roles"))
        with open(os.path.join(root, "roles", "builder.md"), "w", encoding="utf-8") as handle:
            handle.write(role_text)
        return root

    def test_reads_a_role(self):
        root = self.make_repo("---\nname: builder\ndescription: d: x\nread-only: false\ntools: read, shell\n---\n\n# B\n")
        role = source.read_role("builder", root)
        self.assertEqual(role, source.Role("builder", "d: x", False, ("read", "shell"), "\n# B\n"))

    def test_unknown_tool_is_an_error(self):
        root = self.make_repo("---\nname: builder\ndescription: d\nread-only: false\ntools: read, fly\n---\nx\n")
        with self.assertRaisesRegex(ValueError, "unknown tools: fly"):
            source.read_role("builder", root)

    def test_missing_front_matter_is_an_error(self):
        root = self.make_repo("# no front matter\n")
        with self.assertRaisesRegex(ValueError, "no front matter"):
            source.read_role("builder", root)


class ClaudeOutputTest(unittest.TestCase):
    def setUp(self):
        self.outputs = claude.plugin_outputs()

    def test_committed_claude_files_match_the_generator(self):
        for rel, text in sorted(self.outputs.items()):
            with self.subTest(rel):
                self.assertEqual(source.read_text(os.path.join(source.REPO_ROOT, rel)), text)

    def test_covers_five_agents_and_the_skill(self):
        expected = {os.path.join("agents", name + ".md") for name in source.AGENT_ROLES}
        expected.add(os.path.join("skills", "agent-team", "SKILL.md"))
        self.assertEqual(set(self.outputs), expected)

    def test_marker_is_second_line_inside_front_matter(self):
        for rel, text in self.outputs.items():
            with self.subTest(rel):
                lines = text.split("\n")
                self.assertEqual(lines[0], "---")
                self.assertTrue(lines[1].startswith("# " + marker.SIGNATURE))
                self.assertTrue(marker.is_generated(text))

    def test_builder_tools_and_model(self):
        text = self.outputs[os.path.join("agents", "builder.md")]
        self.assertIn("\ntools: Read, Edit, Write, Bash, Grep, Glob\nmodel: sonnet\n", text)

    def test_skill_has_no_placeholders(self):
        skill = self.outputs[os.path.join("skills", "agent-team", "SKILL.md")]
        self.assertNotIn("{{", skill)
        self.assertIn("`agent-team:plan-reviewer`", skill)


if __name__ == "__main__":
    unittest.main()
