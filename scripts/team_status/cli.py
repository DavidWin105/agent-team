"""team-status entry point: gather, render, set the exit code (spec section 9)."""
import os
import sys
import time

from team_status import config, plans, repo, report, routing
from team_status.events import EventLog

CLEAR_SCREEN = "\x1b[H\x1b[2J"
SLOW_EVERY = 10  # frames between git and gh re-gathers in --watch


def main(argv, env=None, out=None, err=None, now=None, sleep=time.sleep, max_frames=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    watch = "--watch" in argv
    args = [arg for arg in argv if arg != "--watch"]
    project = os.path.abspath(args[0] if args else os.getcwd())
    cfg, problems = config.load_config(project)
    if problems:
        for problem in problems:
            print("team-status: %s" % problem, file=err)
        print("team-status: run /team-init to create or fix .claude/team.json", file=err)
        return 1
    try:
        head = repo.git_head(project, env)
    except repo.NotARepo:
        print("team-status: %s is not a git repository with a commit" % project, file=err)
        return 1
    events = config.events_path(cfg)
    log = EventLog(os.path.join(project, events))
    if not watch:
        out.write(_frame(project, cfg, head, log, _gather(project, env), events, now))
        return 0
    if not repo.is_ignored(project, events, env):
        print("team-status: %s is not ignored by git" % events, file=err)
    slow = None
    frame = 0
    try:
        while max_frames is None or frame < max_frames:
            if frame % SLOW_EVERY == 0:
                slow = _gather(project, env)
            out.write(CLEAR_SCREEN)
            out.write(_frame(project, cfg, head, log, slow, events, now))
            out.flush()
            frame += 1
            if max_frames is None or frame < max_frames:
                sleep(1)
    except KeyboardInterrupt:
        pass
    return 0


def _gather(project, env):
    """Answer the slow-changing git and gh state: (worktrees, open pull requests)."""
    return repo.worktrees(project, env), repo.open_prs(project, env)


def _frame(project, cfg, head, log, slow, events, now):
    """Refresh the event log and render one frame of text."""
    paths = cfg["paths"]
    log_path = os.path.join(project, paths["routing-log"])
    summary = routing.summarize(log_path) if os.path.isfile(log_path) else None
    log.refresh()
    worktrees, prs = slow
    return report.render(
        os.path.basename(project),
        head,
        plans.read_plans(project, paths),
        worktrees,
        prs,
        summary,
        paths["routing-log"],
        agents=log,
        now=now,
        events_path=events,
    )
