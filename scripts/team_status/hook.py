"""Record agent-team hook events in the live event log. Never raises, never prints, never writes secrets."""
import json
import os
import re
import time

from team_status import config
from team_status.events import printable

MAX_INPUT = 1024 * 1024
PREFIX = "agent-team:"
WORKTREES = os.path.join(".claude", "worktrees")
FILE_TOOLS = ("Edit", "Write", "Read", "NotebookEdit")
PATH_FIELD = {"NotebookEdit": "notebook_path"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SAFE_HEAD = re.compile(r"^[A-Za-z0-9._+-]*")
MAX_COMMAND = 64
EVENTS = {
    "SubagentStart": ("start", None, None),
    "SubagentStop": ("stop", None, None),
    "PreToolUse": ("tool", "pre", None),
    "PostToolUse": ("tool", "post", True),
    "PostToolUseFailure": ("tool", "post", False),
}


def project_root(cwd):
    """Answer the project folder for a working folder, or None."""
    if not isinstance(cwd, str) or not cwd:
        return None
    marker = os.sep + WORKTREES + os.sep
    if marker in cwd + os.sep:
        return (cwd + os.sep).split(marker)[0] or os.sep
    path = os.path.abspath(cwd)
    while True:
        if os.path.isfile(os.path.join(path, config.CONFIG_PATH)):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def _item(cwd):
    marker = os.sep + WORKTREES + os.sep
    if marker not in cwd + os.sep:
        return ""
    rest = (cwd + os.sep).split(marker, 1)[1]
    return rest.split(os.sep)[0]


def _role(agent_type, cfg):
    if not isinstance(agent_type, str):
        return None
    if agent_type.startswith(PREFIX) and len(agent_type) > len(PREFIX):
        return agent_type[len(PREFIX):]
    for specialist in cfg.get("specialists") or []:
        if isinstance(specialist, dict) and specialist.get("agent") == agent_type:
            return agent_type
    return None


def _inside(root, path):
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        return None
    return None if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel) else rel


def _target(tool, tool_input, root):
    """Answer (target, item): a worktree file is shown relative to its worktree, and names that worktree."""
    if not isinstance(tool_input, dict):
        return "", ""
    if tool in FILE_TOOLS:
        path = tool_input.get(PATH_FIELD.get(tool, "file_path"))
        if not isinstance(path, str) or not path:
            return "", ""
        rel = _inside(root, path if os.path.isabs(path) else os.path.join(root, path))
        return _in_worktree(rel) if rel else (os.path.basename(path), "")
    if tool == "Bash":
        command = tool_input.get("command")
        words = command.split() if isinstance(command, str) else []
        if not words or ASSIGNMENT.match(words[0]):
            return "", ""  # never look past the first word: a value may hide a secret
        return SAFE_HEAD.match(os.path.basename(words[0])).group(0)[:MAX_COMMAND], ""
    return "", ""


def _in_worktree(rel):
    """Answer (path inside the worktree, slug) for .claude/worktrees/<slug>/<path>, else (rel, "")."""
    parts = rel.split(os.sep)
    prefix = WORKTREES.split(os.sep)
    if len(parts) > len(prefix) + 1 and parts[:len(prefix)] == prefix and parts[len(prefix)]:
        return os.path.join(*parts[len(prefix) + 1:]), parts[len(prefix)]
    return rel, ""


def _append(path, record):
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _log_path(root):
    cfg, _ = config.load_config(root)
    if cfg is None:
        return None, None
    return cfg, os.path.join(root, config.events_path(cfg))


def handle(payload, env=None):
    """Append at most one event line for a hook payload; swallow every error."""
    try:
        if not isinstance(payload, dict):
            return
        mapped = EVENTS.get(payload.get("hook_event_name"))
        cwd = payload.get("cwd")
        if mapped is None or not isinstance(cwd, str):
            return
        root = project_root(cwd)
        if root is None:
            return
        cfg, path = _log_path(root)
        if cfg is None:
            return
        role = _role(payload.get("agent_type"), cfg)
        agent_id = payload.get("agent_id")
        if role is None or not isinstance(agent_id, str) or not agent_id:
            return
        kind, phase, ok = mapped
        item = _item(cwd)
        record = {"ts": _now(), "event": kind, "agent_id": agent_id, "agent": printable(role), "item": printable(item)}
        if kind == "tool":
            tool = payload.get("tool_name")
            tool = tool if isinstance(tool, str) else ""
            target, path_item = _target(tool, payload.get("tool_input"), root)
            record.update(item=printable(item or path_item), tool=printable(tool), target=printable(target),
                          phase=phase, ok=ok)
            if ok is None:
                del record["ok"]
        _append(path, record)
    except Exception:
        return


def _plan(name):
    root = project_root(os.getcwd())
    if root is None:
        return
    cfg, path = _log_path(root)
    if cfg is None:
        return
    _append(path, {"ts": _now(), "event": "plan", "target": os.path.basename(name)})


def main(argv, stdin):
    """Entry point: always answers 0 and prints nothing."""
    try:
        if argv and argv[0] == "--plan":
            if len(argv) >= 2:
                _plan(argv[1])
            return 0
        raw = stdin.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            return 0
        handle(json.loads(raw))
    except Exception:
        pass
    return 0
