"""Marked blocks, refusals and stale files (multi-tool adapters spec, sections 6 and 10)."""
import os
import shutil
import tempfile
import unittest

from team_adapt import marker, write

BLOCK = "## agent-team\n\ntext\n"
FULL = write.START + "\n" + BLOCK + write.END


class WithBlockTest(unittest.TestCase):
    def test_empty_file_gets_only_the_block(self):
        self.assertEqual(write.with_block("", BLOCK), FULL + "\n")

    def test_block_is_appended_after_a_blank_line(self):
        self.assertEqual(write.with_block("# Mine\n", BLOCK), "# Mine\n\n" + FULL + "\n")
        self.assertEqual(write.with_block("# Mine", BLOCK), "# Mine\n\n" + FULL + "\n")

    def test_existing_block_is_replaced_and_outside_text_kept(self):
        old = "top\n" + write.START + "\nold\n" + write.END + "\nbottom\n"
        self.assertEqual(write.with_block(old, BLOCK), "top\n" + FULL + "\nbottom\n")

    def test_half_block_is_an_error(self):
        with self.assertRaises(ValueError):
            write.with_block("top\n" + write.START + "\n", BLOCK)

    def test_no_block_removes_it_and_keeps_outside_text(self):
        old = "top\n" + write.START + "\nold\n" + write.END + "\nbottom\n"
        self.assertEqual(write.with_block(old, None), "top\nbottom\n")


class PlanChangesTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

    def put(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_unmarked_target_is_a_problem(self):
        self.put("d/a.md", "mine\n")
        writes, deletes, problems = write.plan_changes(self.root, {"d/a.md": "new"}, {}, ("d",))
        self.assertEqual(problems, ["d/a.md exists and was not written by team-adapt"])

    def test_marked_target_is_overwritten(self):
        self.put("d/a.md", marker.hash_line("x") + "\nold\n")
        writes, deletes, problems = write.plan_changes(self.root, {"d/a.md": "new"}, {}, ("d",))
        self.assertEqual((writes, deletes, problems), ({"d/a.md": "new"}, [], []))

    def test_only_marked_stale_files_are_deleted(self):
        self.put("d/stale.md", marker.hash_line("x") + "\n")
        self.put("d/mine.md", "my own agent\n")
        writes, deletes, problems = write.plan_changes(self.root, {}, {}, ("d",))
        self.assertEqual(deletes, [os.path.join("d", "stale.md")])

    def test_block_of_an_unconfigured_instruction_file_is_removed(self):
        self.put("AGENTS.md", "# Mine\n\n" + FULL + "\n")
        writes, deletes, problems = write.plan_changes(self.root, {}, {}, (), ("AGENTS.md", "GEMINI.md"))
        self.assertEqual((writes, deletes, problems), ({"AGENTS.md": "# Mine\n\n"}, [], []))

    def test_unconfigured_instruction_file_without_a_block_is_left_alone(self):
        self.put("AGENTS.md", "# Mine\n")
        writes, deletes, problems = write.plan_changes(self.root, {}, {}, (), ("AGENTS.md", "GEMINI.md"))
        self.assertEqual((writes, deletes, problems), ({}, [], []))

    def test_half_block_is_a_problem(self):
        self.put("AGENTS.md", write.END + "\n")
        writes, deletes, problems = write.plan_changes(self.root, {}, {"AGENTS.md": BLOCK}, ())
        self.assertEqual(problems, ["AGENTS.md has only one of the agent-team markers"])

    def test_out_of_order_markers_are_a_problem(self):
        self.put("AGENTS.md", write.END + "\n" + write.START + "\n")
        writes, deletes, problems = write.plan_changes(self.root, {}, {"AGENTS.md": BLOCK}, ())
        self.assertEqual(problems, ["AGENTS.md has the agent-team markers out of order"])

    def outside(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        return folder

    def test_symlinked_file_outside_the_project_is_a_problem(self):
        target = os.path.join(self.outside(), "target.txt")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("outside\n")
        os.symlink(target, os.path.join(self.root, "AGENTS.md"))
        writes, deletes, problems = write.plan_changes(self.root, {}, {"AGENTS.md": BLOCK}, ())
        self.assertEqual(problems, ["AGENTS.md is outside the project"])

    def test_unconfigured_symlinked_instruction_file_outside_the_project_is_skipped(self):
        target = os.path.join(self.outside(), "AGENTS.md")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(FULL + "\n")
        os.symlink(target, os.path.join(self.root, "AGENTS.md"))
        writes, deletes, problems = write.plan_changes(self.root, {}, {}, (), ("AGENTS.md",))
        self.assertEqual((writes, deletes, problems), ({}, [], []))

    def test_symlinked_folder_outside_the_project_is_a_problem(self):
        os.symlink(self.outside(), os.path.join(self.root, "d"))
        writes, deletes, problems = write.plan_changes(self.root, {"d/a.md": "new"}, {}, ())
        self.assertEqual(problems, ["d/a.md is outside the project"])

    def test_unreadable_target_is_a_problem(self):
        os.makedirs(os.path.join(self.root, "d"))
        with open(os.path.join(self.root, "d", "a.md"), "wb") as handle:
            handle.write(b"\xff\xfe")
        writes, deletes, problems = write.plan_changes(self.root, {"d/a.md": "new"}, {}, ())
        self.assertEqual(problems, ["d/a.md cannot be read"])

    def test_apply_writes_and_deletes(self):
        self.put("d/stale.md", marker.hash_line("x") + "\n")
        write.apply(self.root, {"e/new.md": "hi"}, [os.path.join("d", "stale.md")])
        self.assertTrue(os.path.isfile(os.path.join(self.root, "e", "new.md")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "d", "stale.md")))


if __name__ == "__main__":
    unittest.main()
