"""team-status entry point: gather, render, set the exit code (spec section 9)."""
import os
import shutil
import sys
import time
from datetime import datetime, timezone

from team_status import cards, config, plans, repo, report, routing
from team_status.events import EventLog

CLEAR_SCREEN = "\x1b[H\x1b[2J"
CARD_MIN_WIDTH = 100
SLOW_EVERY = 10  # frames between git and gh re-gathers in --watch
WARNING = "WARNING: %s is not ignored by git; add %s to .gitignore"


def main(argv, env=None, out=None, err=None, now=None, sleep=time.sleep, max_frames=None, width=None, color=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    if color is None:
        color = _is_terminal(out) and "NO_COLOR" not in (os.environ if env is None else env)
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
        out.write(_frame(project, cfg, log, _gather(project, env, head, events), events, now))
        return 0
    slow = None
    frame = 0
    try:
        while max_frames is None or frame < max_frames:
            if frame % SLOW_EVERY == 0:
                slow = _gather(project, env, slow[0] if slow else head, events, reread=frame > 0)
            columns = shutil.get_terminal_size().columns if width is None else width
            out.write(CLEAR_SCREEN)
            out.write(_frame(project, cfg, log, slow, events, now, columns, color))
            out.flush()
            frame += 1
            if max_frames is None or frame < max_frames:
                sleep(1)
    except KeyboardInterrupt:
        pass
    return 0


def _gather(project, env, head, events, reread=False):
    """Answer the slow-changing git and gh state: (head, worktrees, open pull requests, log ignored by git).

    With reread, the head is read again; if git cannot answer, the last head is kept."""
    if reread:
        try:
            head = repo.git_head(project, env)
        except repo.NotARepo:
            pass
    return head, repo.worktrees(project, env), repo.open_prs(project, env), repo.is_ignored(project, events, env)


def _frame(project, cfg, log, slow, events, now, width=0, color=False):
    """Refresh the event log and render one frame of text."""
    paths = cfg["paths"]
    log_path = os.path.join(project, paths["routing-log"])
    summary = routing.summarize(log_path) if os.path.isfile(log_path) else None
    log.refresh()
    head, worktrees, prs, ignored = slow
    warning = None if ignored or not os.path.isfile(log.path) else WARNING % (events, _ignore_hint(events))
    plan_list = plans.read_plans(project, paths)
    if width >= CARD_MIN_WIDTH:
        rows = log.rows(now or datetime.now(timezone.utc))
        notes = report.log_notes(log, rows, events)
        waiting = report.waiting_items(plan_list, prs)
        lines = cards.render(rows, log.recent(5), cfg, _lead_line(rows), waiting, width, color, notes, warning)
        return "\n".join(lines) + "\n"
    return report.render(
        os.path.basename(project),
        head,
        plan_list,
        worktrees,
        prs,
        summary,
        paths["routing-log"],
        agents=log,
        now=now,
        events_path=events,
        warning=warning,
    )


def _ignore_hint(events):
    """Answer what to add to .gitignore: the log's folder (.claude/team/ for the default path), else the file."""
    folder = os.path.dirname(events.replace(os.sep, "/"))
    return folder + "/" if folder else events


def _is_terminal(out):
    try:
        return bool(out.isatty())
    except (AttributeError, ValueError):
        return False


def _lead_line(rows):
    """Answer '2 running · 1 done' from the rows; zero counts are left out."""
    parts = []
    for state in ("running", "done", "failed", "silent"):
        count = sum(1 for row in rows if row.state == state)
        if count:
            parts.append("%d %s" % (count, state))
    return " · ".join(parts) or "no agents yet"
