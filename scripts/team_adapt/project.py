"""Everything team-adapt writes into a project for Codex, Cursor and Gemini (spec sections 6 and 7)."""
import os

from team_adapt import codex, cursor, gemini, marker, render, source
from team_status.config import TIER_NAMES

MODULES = {"codex": codex, "cursor": cursor, "gemini": gemini}
SKILL_DIR = os.path.join(".agents", "skills", "agent-team")
GENERATED_DIRS = tuple(module.AGENT_DIR for module in MODULES.values()) + (SKILL_DIR,)
INSTRUCTION_BLOCK = (
    "## agent-team\n\n"
    "This project uses the agent-team workflow. To plan a task for the team, run an approved plan or check "
    "the team's status, use the `agent-team` skill in `.agents/skills/agent-team/`. Its agents are named "
    "`<role>-<tier>`, one per core role and tier.\n"
)


def project_outputs(cfg, repo_root=source.REPO_ROOT):
    """Answer (files, blocks): whole files and marked instruction blocks, keyed by path relative to the project."""
    tools = [tool for tool in sorted(cfg["tiers"]) if tool in MODULES]
    files, blocks = {}, {}
    roles = source.read_roles(repo_root) if tools else []
    for tool in tools:
        module = MODULES[tool]
        for role in roles:
            for tier in TIER_NAMES:
                name = "%s-%s" % (role.name, tier)
                path = os.path.join(module.AGENT_DIR, name + module.EXTENSION)
                files[path] = module.agent_file(role, name, cfg["tiers"][tool][tier])
        blocks[module.INSTRUCTIONS] = INSTRUCTION_BLOCK
    if tools:
        files.update(skill_files(repo_root))
    return files, blocks


def skill_files(repo_root):
    skill = render.render(source.read_lead(repo_root), "other", repo_root)
    rules = source.read_text(os.path.join(repo_root, "skills", "agent-team", "rules.md"))
    return {
        os.path.join(SKILL_DIR, "SKILL.md"): marker.after_first_line(skill, marker.hash_line("roles/lead.md")),
        os.path.join(SKILL_DIR, "rules.md"): marker.html_line("skills/agent-team/rules.md") + "\n" + rules,
    }
