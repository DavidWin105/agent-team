"""team-adapt --init: ask for tools, models and project values, then write .claude/team.json (spec section 9)."""
import copy
import json
import os

from team_adapt import source
from team_status import config


def _ask_text(ask, prompt):
    while True:
        answer = ask(prompt).strip()
        if answer:
            return answer


def _ask_tools(ask):
    prompt = "Tools you use (%s), comma separated: " % ", ".join(config.TOOLS)
    while True:
        tools = [tool.strip() for tool in ask(prompt).split(",") if tool.strip()]
        if tools and all(tool in config.TOOLS for tool in tools):
            return list(dict.fromkeys(tools))


def _ask_checks(ask):
    checks = []
    while True:
        name = ask("Check name, for example tests (blank to finish): ").strip()
        if name:
            checks.append({"name": name, "run": _ask_text(ask, "Command for %s: " % name)})
        elif checks:
            return checks


def build_config(ask, template):
    """Answer a new config: the template with the owner's tools, models, owner, checks and paths."""
    cfg = copy.deepcopy(template)
    cfg["tiers"] = {
        tool: {tier: _ask_text(ask, "%s model for the %s tier: " % (tool, tier)) for tier in config.TIER_NAMES}
        for tool in _ask_tools(ask)
    }
    cfg["owner"] = _ask_text(ask, "Owner name: ")
    cfg["checks"] = _ask_checks(ask)
    for key in ("plans", "routing-log"):
        answer = ask("paths.%s [%s]: " % (key, cfg["paths"][key])).strip()
        if answer:
            cfg["paths"][key] = answer
    return cfg


def run_init(project_dir, ask=input, out=print):
    """Ask the questions and write .claude/team.json; answer whether a new file was written."""
    path = os.path.join(project_dir, config.CONFIG_PATH)
    if os.path.exists(path) and ask("%s exists. Replace it? [y/N] " % config.CONFIG_PATH).strip().lower() != "y":
        out("kept %s" % config.CONFIG_PATH)
        return False
    with open(os.path.join(source.REPO_ROOT, "templates", "team.json"), encoding="utf-8") as handle:
        template = json.load(handle)
    cfg = build_config(ask, template)
    problems = config.validate(cfg)
    if problems:
        for problem in problems:
            out("team.json: %s" % problem)
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(cfg, handle, indent=2)
        handle.write("\n")
    out("wrote %s" % config.CONFIG_PATH)
    return True
