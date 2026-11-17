"""Gemini CLI agent files: markdown with front matter in .gemini/agents/ (spec section 6)."""
import json
import os

from team_adapt import marker

AGENT_DIR = os.path.join(".gemini", "agents")
EXTENSION = ".md"
INSTRUCTIONS = "GEMINI.md"
TOOL_NAMES = {
    "read": ["read_file", "read_many_files", "list_directory"],
    "edit": ["replace"],
    "write": ["write_file"],
    "shell": ["run_shell_command"],
    "search": ["glob", "grep_search"],
}


def agent_file(role, name, model):
    tools = [gemini_name for tool in role.tools for gemini_name in TOOL_NAMES[tool]]
    head = [
        "---",
        marker.hash_line("roles/%s.md" % role.name),
        "name: %s" % name,
        "description: %s" % json.dumps(role.description, ensure_ascii=False),
        "kind: local",
        "tools: %s" % json.dumps(tools),
        "model: %s" % json.dumps(model, ensure_ascii=False),
    ]
    return "\n".join(head + ["---"]) + "\n" + role.body
