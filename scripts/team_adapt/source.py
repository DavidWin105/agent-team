"""Read the tool-neutral role sources in roles/ (spec section 5.1)."""
import os
from collections import namedtuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
AGENT_ROLES = ("builder", "code-reviewer", "security-reviewer", "plan-reviewer", "doc-recorder")
NEUTRAL_TOOLS = ("read", "edit", "write", "shell", "search")
FIELDS = ("name", "description", "read-only", "tools")

Role = namedtuple("Role", "name description read_only tools body")


def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def split_front_matter(text, path):
    """Answer (fields, body) for text that starts with '---' front matter of 'key: value' lines."""
    if not text.startswith("---\n") or "\n---\n" not in text[3:]:
        raise ValueError("%s: no front matter" % path)
    head, body = text[4:].split("\n---\n", 1)
    fields = {}
    for line in head.split("\n"):
        key, sep, value = line.partition(": ")
        if not sep:
            raise ValueError("%s: bad front matter line: %s" % (path, line))
        fields[key] = value
    return fields, body


def read_role(name, repo_root=REPO_ROOT):
    path = os.path.join(repo_root, "roles", name + ".md")
    fields, body = split_front_matter(read_text(path), path)
    if any(key not in fields for key in FIELDS) or fields["name"] != name or fields["read-only"] not in ("true", "false"):
        raise ValueError("%s: needs name %s, description, read-only true or false, and tools" % (path, name))
    tools = tuple(tool.strip() for tool in fields["tools"].split(","))
    unknown = [tool for tool in tools if tool not in NEUTRAL_TOOLS]
    if unknown:
        raise ValueError("%s: unknown tools: %s" % (path, ", ".join(unknown)))
    return Role(name, fields["description"], fields["read-only"] == "true", tools, body)


def read_roles(repo_root=REPO_ROOT):
    return [read_role(name, repo_root) for name in AGENT_ROLES]


def read_lead(repo_root=REPO_ROOT):
    return read_text(os.path.join(repo_root, "roles", "lead.md"))
