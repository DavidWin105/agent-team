"""The templates must pass the same checks team-status applies to real projects."""
import json
import os
import unittest

from team_status import config, plans, routing

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")


class TemplatesTest(unittest.TestCase):
    def test_team_json_template_is_valid(self):
        with open(os.path.join(TEMPLATES, "team.json"), encoding="utf-8") as handle:
            self.assertEqual(config.validate(json.load(handle)), [])

    def test_team_json_template_sets_events_path(self):
        with open(os.path.join(TEMPLATES, "team.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["paths"]["events"], config.DEFAULT_EVENTS)

    def test_plan_template_has_front_matter_and_one_open_question(self):
        plan = plans.read_plan(os.path.join(TEMPLATES, "plan.md"))
        self.assertIsNone(plan.problem)
        self.assertEqual(plans.first_word(plan.status), "Draft")
        self.assertEqual(plan.unanswered, 1)

    def test_routing_log_template_reads_as_empty(self):
        summary = routing.summarize(os.path.join(TEMPLATES, "routing-log.md"))
        self.assertEqual((summary.models, summary.unread, summary.problem), ({}, 0, None))


if __name__ == "__main__":
    unittest.main()
