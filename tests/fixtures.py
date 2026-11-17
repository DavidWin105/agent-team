"""Build made-up projects for the team-status tests. No real people or data."""
import copy
import json
import os
import stat
import subprocess
import tempfile

MISSING = object()

VALID = {
    "version": 1,
    "owner": "Test Owner",
    "tiers": {"claude-code": {"strongest": "fable", "strong": "opus", "standard": "sonnet", "fast": "haiku"}},
    "roles": {
        "lead": "strong",
        "builder": "standard",
        "code-reviewer": "strong",
        "security-reviewer": "strongest",
        "plan-reviewer": "strongest",
        "doc-recorder": "standard",
    },
    "specialists": [{"agent": "devops-sre", "tier": "strong", "when": "deploy changes"}],
    "rules": {"reviewer-differs-from-writer": True, "rerun-up-after-failures": 2, "one-lead-per-plan": True},
    "checks": [{"name": "tests", "run": "npm test"}],
    "owner-only": ["merge", "deploy"],
    "paths": {"plans": "plans/", "plan-glob": "*.md", "routing-log": "plans/routing-log.md"},
}

PLAN_APPROVED = """---
title: Made-up plan one
status: Approved 2026-11-17
lead: Test lead (local_0000), 2026-11-17
---

# Plan one

## Answers

- **A1:** count only
"""

PLAN_DRAFT = """---
title: Made-up plan two
status: Draft
lead: scheduled batch run, 2026-11-17
---

# Plan two

## Answers

- **A1:**
- **A2:**\x20\x20\x20
- **A3:** answered

## Change log
- **not a question:**
"""

PLAN_NO_FRONT = "# A plan with no front matter\n"

ROUTING_LOG = """# Agent routing log

## Rows

| Date | Plan, item | Role | Agent | Model | Tokens | Tool calls | Minutes | Findings H/M/L | Kept | Rework | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-17 | Plan one | Plan review | `plan-reviewer` | Fable | 110,638 | 16 | 3.6 | 1/6/9 | 5 | - | made up |
| 2026-11-17 | Plan one | Plan review | `plan-reviewer` | Opus | 135,278 | 43 | 8.0 | 1/4/7 |  | - | made up |
| 2026-11-17 | Plan one | Build | `builder` | Sonnet |  | 30 | 12.5 | - | - | 0 | tokens not seen |
| 2026-11-17 | Plan one | Build | `builder` | Sonnet | lots | 30 | 1.0 | - | - | 0 | broken number |
| 2026-11-17 | short row |

Text after the table.
"""


def valid_config():
    """Answer a fresh copy of a valid config, so a test can change it safely."""
    return copy.deepcopy(VALID)


def _write(root, relative, text):
    path = os.path.join(root, relative)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def make_project(config=None, files=None, commit=True):
    """Create a made-up project folder and answer its path; the caller removes it.

    config: None writes a valid config, MISSING writes none, a str is written as is,
    anything else is written as JSON.
    """
    root = tempfile.mkdtemp(prefix="team-status-")
    if config is not MISSING:
        text = config if isinstance(config, str) else json.dumps(valid_config() if config is None else config)
        _write(root, ".claude/team.json", text)
    for relative, text in (files or {}).items():
        _write(root, relative, text)
    if commit:
        git = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid"]
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        subprocess.run(git + ["add", "-A"], cwd=root, check=True)
        subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "init"], cwd=root, check=True)
    return root


def fake_gh(script):
    """Answer a folder holding a fake `gh` that runs the given shell lines."""
    bindir = tempfile.mkdtemp(prefix="fake-gh-")
    path = os.path.join(bindir, "gh")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n" + script + "\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return bindir


def env_with(bindir):
    """Answer an environment whose PATH finds the given folder first."""
    return {**os.environ, "PATH": bindir + os.pathsep + os.environ.get("PATH", "")}


def write_events(root, lines):
    """Write the given lines (dicts become JSON, str as is) to the events log and answer its path."""
    path = os.path.join(root, ".claude/team/events.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for line in lines:
            handle.write((line if isinstance(line, str) else json.dumps(line)) + "\n")
    return path
