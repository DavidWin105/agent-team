"""Tests for summing the routing log."""
import os
import shutil
import unittest

from fixtures import ROUTING_LOG, make_project
from team_status import routing

HEADER = ROUTING_LOG.split("| 2026-11-17 | Plan one | Plan review")[0]


class SummarizeTest(unittest.TestCase):
    def write_log(self, text):
        root = make_project(files={"log.md": text}, commit=False)
        self.addCleanup(shutil.rmtree, root)
        return os.path.join(root, "log.md")

    def test_sums_per_model(self):
        summary = routing.summarize(self.write_log(ROUTING_LOG))
        fable = summary.models["fable"]
        self.assertEqual((fable.runs, fable.tokens, fable.minutes, fable.findings, fable.kept), (1, 110638, 3.6, (1, 6, 9), 5))
        self.assertEqual(summary.models["opus"].kept, 0)

    def test_blank_tokens_are_counted_as_not_seen_never_guessed(self):
        sonnet = routing.summarize(self.write_log(ROUTING_LOG)).models["sonnet"]
        self.assertEqual((sonnet.runs, sonnet.tokens, sonnet.not_seen, sonnet.minutes), (1, 0, 1, 12.5))

    def test_broken_and_short_rows_are_not_read(self):
        self.assertEqual(routing.summarize(self.write_log(ROUTING_LOG)).unread, 2)

    def test_rows_stop_at_the_end_of_the_table(self):
        summary = routing.summarize(self.write_log(ROUTING_LOG))
        self.assertEqual(sorted(summary.models), ["fable", "opus", "sonnet"])

    def test_log_without_a_table_is_empty(self):
        summary = routing.summarize(self.write_log("# Agent routing log\n\nNo rows yet.\n"))
        self.assertEqual((summary.models, summary.unread), ({}, 0))

    def test_unreadable_log_is_a_problem_not_a_crash(self):
        path = self.write_log("")
        with open(path, "wb") as handle:
            handle.write(b"| Date \xff\xfe |\n")
        summary = routing.summarize(path)
        self.assertEqual((summary.models, summary.unread, summary.problem), ({}, 0, "cannot be read"))

    def test_bad_findings_cell_is_not_read(self):
        row = "| 2026-11-17 | P | R | `a` | Opus | 10 | 1 | 1.0 | 1/2 | 0 | - | n |\n"
        summary = routing.summarize(self.write_log(HEADER + row))
        self.assertEqual((summary.models, summary.unread), ({}, 1))

    def test_values_that_are_not_counts_are_not_read(self):
        rows = [
            "| d | P | R | `a` | Opus | 10 | 1 | nan | - | - | - | n |\n",
            "| d | P | R | `a` | Opus | 10 | 1 | inf | - | - | - | n |\n",
            "| d | P | R | `a` | Opus | -5 | 1 | 1.0 | - | - | - | n |\n",
            "| d | P | R | `a` | Opus | 1_000 | 1 | 1.0 | - | - | - | n |\n",
            "| d | P | R | `a` | Opus | 10 | 1 | 1e3 | - | - | - | n |\n",
            "| d | P | R | `a` | Opus | 10 | 1 | 1.0 | -1/2/3 | - | - | n |\n",
            "| d | P | R | `a` | Opus | 10 | 1 | 1.0 | - | -2 | - | n |\n",
            "| d | P | R | `a` | - | 10 | 1 | 1.0 | - | - | - | n |\n",
        ]
        summary = routing.summarize(self.write_log(HEADER + "".join(rows)))
        self.assertEqual((summary.models, summary.unread), ({}, 8))

    def test_blank_findings_or_kept_count_as_not_seen_but_dash_does_not(self):
        rows = [
            "| d | P | R | `a` | Opus | 10 | 1 | 1.0 |  | 1 | - | n |\n",
            "| d | P | R | `a` | Opus | 10 | 1 | 1.0 | 0/0/1 |  | - | n |\n",
            "| d | P | R | `a` | Opus | 10 | 1 | 1.0 | - | - | - | n |\n",
        ]
        opus = routing.summarize(self.write_log(HEADER + "".join(rows))).models["opus"]
        self.assertEqual((opus.runs, opus.not_seen, opus.findings, opus.kept), (3, 2, (0, 0, 1), 1))

    def test_two_rows_of_one_model_add_up(self):
        row = "| 2026-11-17 | P | R | `a` | Opus | 1,000 | 1 | 1.5 | 0/1/2 | 1 | - | n |\n"
        opus = routing.summarize(self.write_log(HEADER + row + row)).models["opus"]
        self.assertEqual((opus.runs, opus.tokens, opus.minutes, opus.findings, opus.kept), (2, 2000, 3.0, (0, 2, 4), 2))

    def test_minutes_sum_without_rounding_drift(self):
        row = "| d | P | R | `a` | Opus | 10 | 1 | 2.25 | - | - | - | n |\n"
        opus = routing.summarize(self.write_log(HEADER + row * 4)).models["opus"]
        self.assertAlmostEqual(opus.minutes, 9.0)

    def test_commas_only_as_thousands_groups_in_tokens_and_never_in_minutes(self):
        rows = [
            "| d | P | R | `a` | Opus | 1,5 | 1 | 1.0 | - | - | - | n |\n",
            "| d | P | R | `a` | Opus | 10 | 1 | 1,5 | - | - | - | n |\n",
        ]
        summary = routing.summarize(self.write_log(HEADER + "".join(rows)))
        self.assertEqual((summary.models, summary.unread), ({}, 2))
        good = "| d | P | R | `a` | Opus | 110,638 | 1 | 1.0 | - | - | - | n |\n"
        self.assertEqual(routing.summarize(self.write_log(HEADER + good)).models["opus"].tokens, 110638)


if __name__ == "__main__":
    unittest.main()
