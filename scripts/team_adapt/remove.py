"""team-adapt --remove: take every agent-team file back out of a project, after asking."""
import os
import shutil

from team_adapt import project, write
from team_status.config import CONFIG_PATH

EVENTS_DIR = os.path.join(".claude", "team")
GITIGNORE = ".gitignore"
IGNORE_LINE = ".claude/team/"
KEPT_NOTE = (
    "Plans and the routing log are kept; delete them yourself if you no longer want them. "
    "In Claude Code, also uninstall the agent-team plugin."
)


def plan_removal(project_dir):
    """Answer (writes, deletes, folders, problems) without touching the disk; team.json need not be valid."""
    writes, deletes, problems = write.plan_changes(project_dir, {}, {}, project.GENERATED_DIRS, project.INSTRUCTION_FILES)
    writes = dict(writes, **_gitignore_without_line(project_dir))
    emptied = sorted(rel for rel, text in writes.items() if not text.strip())
    writes = {rel: text for rel, text in writes.items() if text.strip()}
    deletes = deletes + emptied
    folders = []
    if os.path.lexists(os.path.join(project_dir, CONFIG_PATH)):
        deletes.append(CONFIG_PATH)
    if os.path.isdir(os.path.join(project_dir, EVENTS_DIR)):
        folders.append(EVENTS_DIR)
    problems = problems + ["%s is outside the project" % rel for rel in deletes + folders if write._outside(project_dir, rel)]
    return writes, deletes, folders, problems


def _gitignore_without_line(project_dir):
    try:
        text = write._read(os.path.join(project_dir, GITIGNORE))
    except (OSError, UnicodeDecodeError):
        return {}
    if text is None:
        return {}
    kept = "".join(line for line in text.splitlines(True) if line.strip() != IGNORE_LINE)
    return {} if kept == text else {GITIGNORE: kept}


def apply_removal(project_dir, writes, deletes, folders):
    write.apply(project_dir, writes, deletes)
    for rel in folders:
        shutil.rmtree(os.path.join(project_dir, rel))
    for rel in deletes + folders:
        _remove_empty_parents(project_dir, os.path.dirname(rel))


def _remove_empty_parents(project_dir, rel_dir):
    """Remove rel_dir and its parents while empty, never the project folder itself."""
    while rel_dir:
        try:
            os.rmdir(os.path.join(project_dir, rel_dir))
        except OSError:
            return
        rel_dir = os.path.dirname(rel_dir)


def run(project_dir, out, err, ask):
    writes, deletes, folders, problems = plan_removal(project_dir)
    if problems:
        for problem in problems:
            print(problem, file=err)
        print("nothing removed", file=err)
        return 1
    if not (writes or deletes or folders):
        print("nothing to remove", file=out)
        return 0
    for rel in sorted(deletes):
        print("delete %s" % rel, file=out)
    for rel in folders:
        print("delete %s/ and everything in it" % rel, file=out)
    for rel in sorted(writes):
        print("edit %s (take out the agent-team lines)" % rel, file=out)
    try:
        answer = ask("Remove these? [y/N] ")
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer.strip().lower() not in ("y", "yes"):
        print("nothing removed", file=err)
        return 1
    try:
        apply_removal(project_dir, writes, deletes, folders)
    except OSError as error:
        print("stopped while removing, some files may be removed: %s" % error, file=err)
        return 1
    print("removed. " + KEPT_NOTE, file=out)
    return 0
