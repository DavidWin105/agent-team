"""Tests for loading and checking .claude/team.json."""
import os
import shutil
import unittest

from fixtures import MISSING, make_project, valid_config
from team_status import config


def project(test, cfg=None):
    root = make_project(config=cfg, commit=False)
    test.addCleanup(shutil.rmtree, root)
    return root


class LoadConfigTest(unittest.TestCase):
    def test_valid_config_loads_with_no_problems(self):
        cfg, problems = config.load_config(project(self))
        self.assertEqual(problems, [])
        self.assertEqual(cfg["owner"], "Test Owner")

    def test_missing_file_is_one_problem_and_no_config(self):
        cfg, problems = config.load_config(project(self, MISSING))
        self.assertIsNone(cfg)
        self.assertEqual(problems, ["no .claude/team.json"])

    def test_broken_json_names_the_line(self):
        cfg, problems = config.load_config(project(self, '{\n  "version": 1,\n}'))
        self.assertIsNone(cfg)
        self.assertIn("is not valid JSON: line 3", problems[0])

    def test_unreadable_file_is_a_problem_not_a_crash(self):
        root = project(self, MISSING)
        os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
        with open(os.path.join(root, ".claude", "team.json"), "wb") as handle:
            handle.write(b"\xff\xfe\x00 not utf-8")
        cfg, problems = config.load_config(root)
        self.assertIsNone(cfg)
        self.assertEqual(problems, [".claude/team.json cannot be read"])

    def test_team_json_that_is_a_folder_is_a_problem_not_a_crash(self):
        root = project(self, MISSING)
        os.makedirs(os.path.join(root, ".claude", "team.json"))
        cfg, problems = config.load_config(root)
        self.assertIsNone(cfg)
        self.assertEqual(problems, [".claude/team.json cannot be read"])

    def test_invalid_config_is_not_returned(self):
        cfg, problems = config.load_config(project(self, {**valid_config(), "version": 2}))
        self.assertIsNone(cfg)
        self.assertEqual(problems, ["version must be 1"])


class ValidateTest(unittest.TestCase):
    def test_missing_required_key(self):
        data = valid_config()
        del data["checks"]
        self.assertEqual(config.validate(data), ["missing key: checks"])

    def test_unknown_top_level_key(self):
        self.assertEqual(config.validate({**valid_config(), "chekcs": []}), ["unknown key: chekcs"])

    def test_not_an_object(self):
        self.assertEqual(config.validate([]), ["team.json must be a JSON object"])

    def test_role_with_unknown_tier(self):
        data = valid_config()
        data["roles"]["builder"] = "turbo"
        self.assertEqual(config.validate(data), ["role builder uses unknown tier: turbo"])

    def test_role_tier_that_is_not_text_is_a_problem_not_a_crash(self):
        data = valid_config()
        data["roles"]["builder"] = ["standard"]
        self.assertEqual(config.validate(data), ["role builder uses unknown tier: ['standard']"])

    def test_version_true_is_not_version_1(self):
        self.assertEqual(config.validate({**valid_config(), "version": True}), ["version must be 1"])

    def test_missing_and_unknown_roles(self):
        data = valid_config()
        del data["roles"]["doc-recorder"]
        data["roles"]["tester"] = "standard"
        self.assertEqual(config.validate(data), ["missing role: doc-recorder", "unknown role: tester"])

    def test_missing_tool_block(self):
        data = valid_config()
        data["tiers"] = {"cursor": {"strong": "x"}}
        self.assertIn("tiers.claude-code must map tier names to models", config.validate(data))

    def test_specialist_needs_known_tier_and_fields(self):
        data = valid_config()
        data["specialists"] = [{"agent": "a", "tier": "turbo", "when": "w"}, {"agent": "b"}]
        self.assertEqual(
            config.validate(data),
            ["specialist a uses unknown tier: turbo", "specialists[1] needs agent, tier and when"],
        )

    def test_checks_must_not_be_empty(self):
        self.assertEqual(config.validate({**valid_config(), "checks": []}), ["checks must be a non-empty list"])

    def test_check_needs_name_and_run(self):
        self.assertEqual(config.validate({**valid_config(), "checks": [{"name": "x"}]}), ["checks[0] needs name and run"])

    def test_owner_only_must_list_steps(self):
        self.assertEqual(
            config.validate({**valid_config(), "owner-only": []}),
            ["owner-only must be a non-empty list of step names"],
        )

    def test_paths_need_all_three(self):
        self.assertEqual(
            config.validate({**valid_config(), "paths": {"plans": "p/"}}),
            ["paths.plan-glob must be a non-empty string", "paths.routing-log must be a non-empty string"],
        )

    def test_rules_and_specialists_are_optional(self):
        data = valid_config()
        del data["rules"]
        del data["specialists"]
        self.assertEqual(config.validate(data), [])

    def test_bad_rules(self):
        data = {**valid_config(), "rules": {"one-lead-per-plan": "yes", "rerun-up-after-failures": 0, "speed": 1}}
        self.assertEqual(
            config.validate(data),
            [
                "unknown rule: speed",
                "rules.one-lead-per-plan must be true or false",
                "rules.rerun-up-after-failures must be a whole number of 1 or more",
            ],
        )


if __name__ == "__main__":
    unittest.main()
