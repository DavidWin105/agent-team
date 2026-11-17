"""Codex CLI agent files: TOML in .codex/agents/ (spec section 6)."""
import json
import os

from team_adapt import marker

AGENT_DIR = os.path.join(".codex", "agents")
EXTENSION = ".toml"
INSTRUCTIONS = "AGENTS.md"


def toml_string(value):
    # A JSON string is a valid TOML basic string: same quotes and escapes.
    return json.dumps(value, ensure_ascii=False)


def agent_file(role, name, model):
    lines = [
        marker.hash_line("roles/%s.md" % role.name),
        "name = %s" % toml_string(name),
        "description = %s" % toml_string(role.description),
        "model = %s" % toml_string(model),
        "developer_instructions = %s" % toml_string(role.body.strip() + "\n"),
    ]
    return "\n".join(lines) + "\n"
