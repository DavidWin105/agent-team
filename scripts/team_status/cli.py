"""team-status entry point: gather, render, set the exit code (spec section 9)."""
import os
import sys

from team_status import config, plans, repo, report, routing
from team_status.events import EventLog


def main(argv, env=None, out=None, err=None, now=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    project = os.path.abspath(argv[0] if argv else os.getcwd())
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
    paths = cfg["paths"]
    log_path = os.path.join(project, paths["routing-log"])
    summary = routing.summarize(log_path) if os.path.isfile(log_path) else None
    events = config.events_path(cfg)
    log = EventLog(os.path.join(project, events))
    log.refresh()
    text = report.render(
        os.path.basename(project),
        head,
        plans.read_plans(project, paths),
        repo.worktrees(project, env),
        repo.open_prs(project, env),
        summary,
        paths["routing-log"],
        agents=log,
        now=now,
        events_path=events,
    )
    out.write(text)
    return 0
