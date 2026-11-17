"""The skill, command and README must describe the live agent view."""
import os
import re
import unittest

WATCH = 'python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/team-status" --watch <project folder>'
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def step(text, number):
    match = re.search(r"^## %d\. .*?(?=^## \d+\. |\Z)" % number, text, re.S | re.M)
    return match.group(0)


class SkillTextTest(unittest.TestCase):
    def setUp(self):
        self.skill = read("skills", "agent-team", "SKILL.md")

    def test_step_5_records_the_plan_and_points_at_watch(self):
        build = step(self.skill, 5)
        self.assertIn("team-event", build)
        self.assertIn("--plan", build)
        self.assertIn(WATCH, build)
        self.assertIn("resolved", build)
        self.assertNotIn("`team-status --watch`", build)
        self.assertNotIn("so every agent gets a card", build)

    def test_paths_row_mentions_events(self):
        row = [l for l in self.skill.splitlines() if l.startswith("| `paths`")][0]
        self.assertIn("events", row)

    def test_summary_suggests_watch(self):
        summary = step(self.skill, 11)
        self.assertIn(WATCH, summary)
        self.assertNotIn("`team-status --watch`", summary)

    def test_team_init_gitignores_team_folder(self):
        self.assertIn(".claude/team/", read("commands", "team-init.md"))

    def test_readme_mentions_watch(self):
        readme = read("README.md")
        self.assertIn("`python3 -I agent-team/scripts/team-status --watch <project-dir>`", readme)
        self.assertNotIn("`team-status --watch`", readme)

    def test_team_watch_command_prints_the_resolved_watch_command(self):
        text = read("commands", "team-watch.md")
        self.assertIn("--watch", text)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", text)
        self.assertIn("$PWD", text)
        self.assertIn("second terminal", text)
        self.assertIn("Do not run", text)
        self.assertNotIn("`team-status --watch`", text)

    def test_readme_has_a_watch_it_live_section_with_team_watch(self):
        readme = read("README.md")
        self.assertIn("### Watch it live", readme)
        section = readme.split("### Watch it live", 1)[1].split("\n### ", 1)[0]
        self.assertIn("`/team-watch`", section)
        self.assertIn("second terminal", section)
        self.assertIn("python3 -I", section)

    def test_first_design_doc_points_to_live_view(self):
        text = read("docs", "specs", "2026-11-17-agent-team-plugin-design.md")
        self.assertIn("live-agent-view-design.md", text)
        self.assertNotIn("No monitor of our own", text)


if __name__ == "__main__":
    unittest.main()
