"""Claude Code output: the plugin's own agents/ and skills/agent-team/SKILL.md (spec section 6)."""
import json
import os

from team_adapt import marker, render, source

PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"
SKILL = os.path.join("skills", "agent-team", "SKILL.md")
TOOL_NAMES = {"read": ["Read"], "edit": ["Edit"], "write": ["Write"], "shell": ["Bash"], "search": ["Grep", "Glob"]}


def agent_file(role, model):
    tools = ", ".join(name for tool in role.tools for name in TOOL_NAMES[tool])
    head = "---\n%s\nname: %s\ndescription: %s\ntools: %s\nmodel: %s\n---\n" % (
        marker.hash_line("roles/%s.md" % role.name), role.name, role.description, tools, model)
    return head + role.body


def skill_file(lead_text):
    return marker.after_first_line(render.render(lead_text, "claude", PLUGIN_ROOT), marker.hash_line("roles/lead.md"))


def template_models(repo_root=source.REPO_ROOT):
    """Answer role -> model from templates/team.json; it fills each agent file's fallback model line."""
    with open(os.path.join(repo_root, "templates", "team.json"), encoding="utf-8") as handle:
        cfg = json.load(handle)
    models = cfg["tiers"]["claude-code"]
    return {role: models[tier] for role, tier in cfg["roles"].items()}


def plugin_outputs(repo_root=source.REPO_ROOT):
    """Answer {path relative to the repo: text} for every Claude Code file the plugin ships."""
    models = template_models(repo_root)
    outputs = {
        os.path.join("agents", role.name + ".md"): agent_file(role, models[role.name])
        for role in source.read_roles(repo_root)
    }
    outputs[SKILL] = skill_file(source.read_lead(repo_root))
    return outputs


def write_plugin_files(repo_root=source.REPO_ROOT):
    outputs = plugin_outputs(repo_root)
    for rel, text in outputs.items():
        with open(os.path.join(repo_root, rel), "w", encoding="utf-8") as handle:
            handle.write(text)
    return sorted(outputs)
