"""Cursor agent files: markdown with front matter in .cursor/agents/ (spec section 6)."""
import json
import os

from team_adapt import marker

AGENT_DIR = os.path.join(".cursor", "agents")
EXTENSION = ".md"
INSTRUCTIONS = "AGENTS.md"


def agent_file(role, name, model):
    head = [
        "---",
        marker.hash_line("roles/%s.md" % role.name),
        "name: %s" % name,
        "description: %s" % json.dumps(role.description, ensure_ascii=False),
        "model: %s" % json.dumps(model, ensure_ascii=False),
    ]
    if role.read_only:
        head.append("readonly: true")
    return "\n".join(head + ["---"]) + "\n" + role.body
