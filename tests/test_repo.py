"""Tests for reading git and gh state."""
import os
import shutil
import subprocess
import tempfile
import unittest

from fixtures import env_with, fake_gh, make_project
from team_status import repo


class GitTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project()
        self.addCleanup(shutil.rmtree, self.root)

    def test_head_answers_branch_and_short_commit(self):
        head = repo.git_head(self.root)
        self.assertEqual(head.branch, "main")
        self.assertGreaterEqual(len(head.commit), 7)

    def test_not_a_repository_raises(self):
        plain = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, plain)
        with self.assertRaises(repo.NotARepo):
            repo.git_head(plain)

    def test_git_missing_is_not_a_repo_and_no_worktrees(self):
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty)
        with self.assertRaises(repo.NotARepo):
            repo.git_head(self.root, {"PATH": empty})
        self.assertEqual(repo.worktrees(self.root, {"PATH": empty}), [])

    def test_worktrees_leave_out_the_main_checkout(self):
        self.assertEqual(repo.worktrees(self.root), [])
        parent = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, parent)
        extra = os.path.join(parent, "wt")
        subprocess.run(["git", "worktree", "add", "-q", "-b", "feat/item-a", extra], cwd=self.root, check=True)
        self.assertEqual(repo.worktrees(self.root), ["feat/item-a"])


class GhTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project()
        self.addCleanup(shutil.rmtree, self.root)

    def gh(self, script):
        bindir = fake_gh(script)
        self.addCleanup(shutil.rmtree, bindir)
        return env_with(bindir)

    def test_open_prs_from_gh(self):
        env = self.gh("echo '[{\"number\": 7, \"title\": \"feat: made-up item\"}]'")
        self.assertEqual(repo.open_prs(self.root, env), [repo.PullRequest(7, "feat: made-up item")])

    def test_open_prs_asks_for_up_to_1000(self):
        env = self.gh("case \"$*\" in *'--limit 1000'*) echo '[{\"number\": 7, \"title\": \"t\"}]';; *) exit 1;; esac")
        self.assertEqual(repo.open_prs(self.root, env), [repo.PullRequest(7, "t")])

    def test_gh_wrong_shape_is_none(self):
        self.assertIsNone(repo.open_prs(self.root, self.gh("echo '[1, 2]'")))
        self.assertIsNone(repo.open_prs(self.root, self.gh("echo '[{\"number\": \"7\", \"title\": null}]'")))

    def test_gh_missing_is_none_not_empty(self):
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty)
        self.assertIsNone(repo.open_prs(self.root, {"PATH": empty}))

    def test_gh_signed_out_is_none(self):
        self.assertIsNone(repo.open_prs(self.root, self.gh("echo 'not logged in' >&2; exit 4")))

    def test_gh_garbage_output_is_none(self):
        self.assertIsNone(repo.open_prs(self.root, self.gh("echo 'not json'")))


if __name__ == "__main__":
    unittest.main()
