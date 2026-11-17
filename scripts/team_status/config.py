"""Load and check a project's .claude/team.json (spec section 5)."""
import json
import os
import re

CONFIG_PATH = os.path.join(".claude", "team.json")
TOOL = "claude-code"
CORE_ROLES = ("lead", "builder", "code-reviewer", "security-reviewer", "plan-reviewer", "doc-recorder")
REQUIRED_KEYS = ("version", "owner", "tiers", "roles", "checks", "owner-only", "paths")
OPTIONAL_KEYS = ("specialists", "rules")
PATH_KEYS = ("plans", "plan-glob", "routing-log")
DEFAULT_EVENTS = ".claude/team/events.jsonl"
RULE_DEFAULTS = {"reviewer-differs-from-writer": True, "rerun-up-after-failures": 2, "one-lead-per-plan": True}
BOOLEAN_RULES = ("reviewer-differs-from-writer", "one-lead-per-plan")


def load_config(project_dir):
    """Answer (config, problems); config is None whenever there is a problem."""
    path = os.path.join(project_dir, CONFIG_PATH)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None, ["no %s" % CONFIG_PATH]
    except json.JSONDecodeError as error:
        return None, ["%s is not valid JSON: line %d" % (CONFIG_PATH, error.lineno)]
    except (OSError, UnicodeDecodeError, RecursionError):
        return None, ["%s cannot be read" % CONFIG_PATH]
    problems = validate(data)
    return (None if problems else data), problems


def validate(data):
    """Answer every problem found in a parsed config; an empty list means valid."""
    if not isinstance(data, dict):
        return ["team.json must be a JSON object"]
    allowed = set(REQUIRED_KEYS) | set(OPTIONAL_KEYS)
    shape = ["missing key: %s" % key for key in REQUIRED_KEYS if key not in data]
    shape += ["unknown key: %s" % key for key in sorted(data) if key not in allowed]
    if shape:
        return shape
    tiers, tier_problems = _tool_tiers(data["tiers"])
    problems = [] if type(data["version"]) is int and data["version"] == 1 else ["version must be 1"]
    problems += [] if _is_text(data["owner"]) else ["owner must be a non-empty string"]
    return (
        problems
        + tier_problems
        + _check_roles(data["roles"], tiers)
        + _check_specialists(data.get("specialists", []), tiers)
        + _check_checks(data["checks"])
        + _check_owner_only(data["owner-only"])
        + _check_paths(data["paths"])
        + _check_rules(data.get("rules", {}))
    )


def _is_text(value):
    return isinstance(value, str) and value.strip() != ""


def _tool_tiers(tiers):
    block = tiers.get(TOOL) if isinstance(tiers, dict) else None
    if not isinstance(block, dict) or not block:
        return {}, ["tiers.%s must map tier names to models" % TOOL]
    bad = ["tiers.%s.%s must be a model name" % (TOOL, name) for name, model in block.items() if not _is_text(model)]
    return block, bad


def _check_roles(roles, tiers):
    if not isinstance(roles, dict):
        return ["roles must be an object"]
    problems = ["missing role: %s" % role for role in CORE_ROLES if role not in roles]
    problems += ["unknown role: %s" % role for role in sorted(roles) if role not in CORE_ROLES]
    problems += [
        "role %s uses unknown tier: %s" % (role, tier)
        for role, tier in sorted(roles.items())
        if role in CORE_ROLES and (not isinstance(tier, str) or tier not in tiers)
    ]
    return problems


def _check_specialists(specialists, tiers):
    if not isinstance(specialists, list):
        return ["specialists must be a list"]
    problems = []
    for index, item in enumerate(specialists):
        if not isinstance(item, dict) or not all(_is_text(item.get(key)) for key in ("agent", "tier", "when")):
            problems.append("specialists[%d] needs agent, tier and when" % index)
        elif item["tier"] not in tiers:
            problems.append("specialist %s uses unknown tier: %s" % (item["agent"], item["tier"]))
    return problems


def _check_checks(checks):
    if not isinstance(checks, list) or not checks:
        return ["checks must be a non-empty list"]
    return [
        "checks[%d] needs name and run" % index
        for index, check in enumerate(checks)
        if not isinstance(check, dict) or not (_is_text(check.get("name")) and _is_text(check.get("run")))
    ]


def _check_owner_only(steps):
    if not isinstance(steps, list) or not steps or not all(_is_text(step) for step in steps):
        return ["owner-only must be a non-empty list of step names"]
    return []


def _check_paths(paths):
    if not isinstance(paths, dict):
        return ["paths must be an object"]
    problems = ["paths.%s must be a non-empty string" % key for key in PATH_KEYS if not _is_text(paths.get(key))]
    if "events" in paths and not _is_text(paths["events"]):
        problems.append("paths.events must be a non-empty string")
    elif "events" in paths and not _inside_project(paths["events"]):
        problems.append("paths.events must be a relative path inside the project")
    return problems


def _inside_project(path):
    """Answer whether a relative path stays inside the project: not absolute, no ".." part."""
    if os.path.isabs(path) or path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", path):
        return False
    return ".." not in re.split(r"[\\/]", path)


def events_path(cfg):
    """Answer the events log path, relative to the project."""
    return cfg["paths"].get("events", DEFAULT_EVENTS)


def _check_rules(rules):
    if not isinstance(rules, dict):
        return ["rules must be an object"]
    problems = ["unknown rule: %s" % key for key in sorted(rules) if key not in RULE_DEFAULTS]
    problems += [
        "rules.%s must be true or false" % key
        for key in BOOLEAN_RULES
        if key in rules and not isinstance(rules[key], bool)
    ]
    rerun = rules.get("rerun-up-after-failures", RULE_DEFAULTS["rerun-up-after-failures"])
    if isinstance(rerun, bool) or not isinstance(rerun, int) or rerun < 1:
        problems.append("rules.rerun-up-after-failures must be a whole number of 1 or more")
    return problems


def model_for(cfg, agent):
    """Answer the model name for a core role or a specialist agent, else None."""
    try:
        models = cfg["tiers"][TOOL]
        tier = cfg["roles"].get(agent)
        if tier is None:
            tier = next((item["tier"] for item in cfg.get("specialists", []) if item["agent"] == agent), None)
        model = models.get(tier) if tier is not None else None
    except (KeyError, TypeError, AttributeError, StopIteration):
        return None
    return model if isinstance(model, str) else None
