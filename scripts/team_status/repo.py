"""Read git and gh state for a project, read-only (spec section 9)."""
import json
import shutil
import subprocess
from collections import namedtuple

Head = namedtuple("Head", "branch commit")
PullRequest = namedtuple("PullRequest", "number title")
TIMEOUT_SECONDS = 20
BRANCH_PREFIX = "branch refs/heads/"


class NotARepo(Exception):
    """The project folder is not a git repository with at least one commit."""


def _run(args, cwd, env):
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)


def git_head(project_dir, env=None):
    try:
        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], project_dir, env)
        commit = _run(["git", "rev-parse", "--short", "HEAD"], project_dir, env)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise NotARepo(project_dir) from error
    if branch.returncode != 0 or commit.returncode != 0:
        raise NotARepo(project_dir)
    return Head(branch.stdout.strip(), commit.stdout.strip())


def is_ignored(project_dir, relative_path, env=None):
    """Answer whether git ignores the path; False when unsure (no git, not a repo, any error)."""
    try:
        result = _run(["git", "check-ignore", "-q", relative_path], project_dir, env)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def worktrees(project_dir, env=None):
    """Answer the branch of every worktree except the main checkout."""
    try:
        result = _run(["git", "worktree", "list", "--porcelain"], project_dir, env)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    blocks = [block for block in result.stdout.split("\n\n") if block.strip()]
    return [_branch_of(block) for block in blocks[1:]]


def _branch_of(block):
    for line in block.splitlines():
        if line.startswith(BRANCH_PREFIX):
            return line[len(BRANCH_PREFIX):]
        if line == "detached":
            return "(detached)"
    return "(unknown)"


def open_prs(project_dir, env=None):
    """Answer the open pull requests, or None when gh is missing, signed out or answers nonsense."""
    search_path = env.get("PATH") if env else None
    if shutil.which("gh", path=search_path) is None:
        return None
    try:
        result = _run(["gh", "pr", "list", "--state", "open", "--limit", "1000", "--json", "number,title"], project_dir, env)
        items = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    if not isinstance(items, list) or not all(_is_pr(item) for item in items):
        return None
    return [PullRequest(item["number"], item["title"]) for item in items]


def _is_pr(item):
    return (
        isinstance(item, dict)
        and isinstance(item.get("number"), int)
        and not isinstance(item["number"], bool)
        and isinstance(item.get("title"), str)
    )
