"""The translated READMEs must keep the same commands as the English one."""
import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TRANSLATIONS = ("README.zh-CN.md", "README.my.md")


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
        return handle.read()


def code_blocks(text):
    return re.findall(r"```[a-z]*\n(.*?)```", text, re.S)


class ReadmeTranslationsTest(unittest.TestCase):
    def test_english_readme_links_to_both_translations(self):
        first_line = read("README.md").splitlines()[0]
        for name in TRANSLATIONS:
            self.assertIn("(%s)" % name, first_line)

    def test_each_translation_links_back_and_to_the_other(self):
        for name in TRANSLATIONS:
            first_line = read(name).splitlines()[0]
            self.assertIn("(README.md)", first_line)
            other = [n for n in TRANSLATIONS if n != name][0]
            self.assertIn("(%s)" % other, first_line)

    def test_code_blocks_match_the_english_readme(self):
        english = code_blocks(read("README.md"))
        for name in TRANSLATIONS:
            self.assertEqual(code_blocks(read(name)), english, name)

    def test_translations_keep_the_key_commands_and_paths(self):
        for name in TRANSLATIONS:
            text = read(name)
            for token in ("/team-init", "/team-status", "/team-watch", "docs/media/live-view-preview-cards.png",
                          "docs/specs/2026-11-17-agent-team-plugin-design.md", "LICENSE"):
                self.assertIn(token, text, "%s is missing %s" % (name, token))


if __name__ == "__main__":
    unittest.main()
