"""Tests for reading plan files."""
import os
import shutil
import unittest

from fixtures import PLAN_APPROVED, PLAN_DRAFT, PLAN_NO_FRONT, make_project
from team_status import plans

PATHS = {"plans": "plans/", "plan-glob": "*.md", "routing-log": "plans/routing-log.md"}


class ReadPlansTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project(
            files={
                "plans/a-one.md": PLAN_APPROVED,
                "plans/b-two.md": PLAN_DRAFT,
                "plans/c-bad.md": PLAN_NO_FRONT,
                "plans/notes.txt": "not a plan",
                "plans/routing-log.md": "# Agent routing log\n",
            },
            commit=False,
        )
        self.addCleanup(shutil.rmtree, self.root)

    def test_reads_matching_files_in_name_order(self):
        names = [plan.name for plan in plans.read_plans(self.root, PATHS)]
        self.assertEqual(names, ["a-one", "b-two", "c-bad"])

    def test_routing_log_in_the_plans_folder_is_not_a_plan(self):
        names = [plan.name for plan in plans.read_plans(self.root, PATHS)]
        self.assertNotIn("routing-log", names)

    def test_reads_status_and_lead(self):
        plan = plans.read_plan(os.path.join(self.root, "plans/a-one.md"))
        self.assertEqual(plan.status, "Approved 2026-11-17")
        self.assertEqual(plan.lead, "Test lead (local_0000), 2026-11-17")
        self.assertEqual(plan.unanswered, 0)
        self.assertIsNone(plan.problem)

    def test_counts_only_empty_answers_under_the_answers_heading(self):
        plan = plans.read_plan(os.path.join(self.root, "plans/b-two.md"))
        self.assertEqual(plan.unanswered, 2)

    def test_answer_text_containing_bold_colon_is_not_a_question(self):
        text = "---\ntitle: t\nstatus: Draft\nlead: l\n---\n\n## Answers\n\n- **Q3:** see **note:**\n"
        root = make_project(files={"plans/q.md": text}, commit=False)
        self.addCleanup(shutil.rmtree, root)
        self.assertEqual(plans.read_plan(os.path.join(root, "plans/q.md")).unanswered, 0)

    def test_plan_without_front_matter_reports_a_problem(self):
        plan = plans.read_plan(os.path.join(self.root, "plans/c-bad.md"))
        self.assertEqual(plan.problem, "no front matter")
        self.assertIsNone(plan.status)

    def test_unclosed_front_matter_is_a_problem(self):
        path = os.path.join(self.root, "plans/d-open.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("---\nstatus: Draft\n")
        self.assertEqual(plans.read_plan(path).problem, "no front matter")

    def test_unreadable_plan_is_a_problem_not_a_crash(self):
        path = os.path.join(self.root, "plans/e-bytes.md")
        with open(path, "wb") as handle:
            handle.write(b"---\nstatus: \xff\xfe\n---\n")
        plan = plans.read_plan(path)
        self.assertEqual((plan.name, plan.problem, plan.status), ("e-bytes", "cannot be read", None))

    def test_folder_matching_the_glob_is_not_a_plan(self):
        os.makedirs(os.path.join(self.root, "plans/f-folder.md"))
        names = [plan.name for plan in plans.read_plans(self.root, PATHS)]
        self.assertEqual(names, ["a-one", "b-two", "c-bad"])

    def test_no_plan_folder_answers_an_empty_list(self):
        self.assertEqual(plans.read_plans(self.root, {**PATHS, "plans": "missing/"}), [])

    def test_first_word(self):
        self.assertEqual(plans.first_word("Done 2026-11-17 (merged)"), "Done")
        self.assertEqual(plans.first_word(None), "(none)")
        self.assertEqual(plans.first_word("   "), "(none)")


if __name__ == "__main__":
    unittest.main()
