"""Turn the gathered state into the printed report (spec section 9)."""
from datetime import datetime, timezone

from team_status.config import DEFAULT_EVENTS
from team_status.events import printable
from team_status.plans import first_word

PLAN_NAME_WIDTH = 36
AGENT_NAME_WIDTH = 14
GLYPHS = {"running": "\u25b6", "done": "\u2713", "failed": "\u2717", "silent": "?"}


def render(project, head, plan_list, branches, prs, summary, routing_path, agents=None, now=None, events_path=DEFAULT_EVENTS,
           warning=None):
    now = now or datetime.now(timezone.utc)
    lines = ["agent-team · %s · %s %s" % (project, head.branch, head.commit)] + ([warning] if warning else []) + [""]
    lines += format_agents(agents, now, events_path) + [""]
    lines += _plans(plan_list) + [""]
    lines += ["WORKTREES   %d   %s" % (len(branches), ", ".join(branches)), ""]
    lines += _prs(prs) + [""]
    lines += _waiting(plan_list, prs) + [""]
    lines += _routing(summary, routing_path)
    return "\n".join(lines) + "\n"


def format_agents(log, now, events_path):
    """Answer the AGENTS section lines; say so when there is nothing to show."""
    rows = [] if _empty(log) else log.rows(now)
    lines = ["AGENTS"]
    if rows:
        item_width = max(len(row.item or "-") for row in rows)
        status = [_status(row) for row in rows]
        status_width = max(len(text) for text in status)
        for row, text in zip(rows, status):
            lines.append(
                "  %-*s  %-*s %-*s  %s  %s"
                % (item_width, row.item or "-", AGENT_NAME_WIDTH, row.agent or "-", status_width, text, _clock(row.seconds), calls_text(row.calls))
            )
            if row.shared > 1:
                lines.append("  " + shared_note(row))
    return lines + ["  " + note for note in log_notes(log, rows, events_path)]


def log_notes(log, rows, events_path):
    """Answer the notes that say the log is empty or incomplete; the table and the cards both print them."""
    if _empty(log):
        return ["no agent events recorded yet (%s)" % events_path]
    notes = []
    if not rows and log.seen:
        notes.append("no agent activity since the last plan marker")
    if log.unread:
        notes.append("%d line%s not read" % (log.unread, "" if log.unread == 1 else "s"))
    if log.plan is None and log.seen:
        notes.append("no plan marker: showing every event")
    return notes


def calls_text(count):
    """Answer "1 call" or "N calls"."""
    return "%d call%s" % (count, "" if count == 1 else "s")


def shared_note(row):
    """Answer the note for a row that several agents without an id share."""
    return "%d agents share this row" % row.shared


def _empty(log):
    return log is None or (log.seen == 0 and log.unread == 0)


def _status(row):
    text = row.doing if row.state == "running" and row.doing else row.state
    return "%s %s" % (GLYPHS[row.state], text)


def _clock(seconds):
    return "%dm%02ds" % divmod(seconds, 60)


def _plans(plan_list):
    if not plan_list:
        return ["PLANS", "  none found"]
    rows = []
    for plan in plan_list:
        if plan.problem:
            rows.append("  %-*s %s" % (PLAN_NAME_WIDTH, printable(plan.name), printable(plan.problem)))
        else:
            status = printable(first_word(plan.status))
            rows.append("  %-*s %-9s lead: %s" % (PLAN_NAME_WIDTH, printable(plan.name), status, printable(plan.lead or "(none)")))
    return ["PLANS"] + rows


def _prs(prs):
    if prs is None:
        return ["OPEN PRs    not checked: gh unavailable"]
    return ["OPEN PRs    %d" % len(prs)] + ["  #%d %s" % (pr.number, printable(pr.title)) for pr in prs]


def _waiting(plan_list, prs):
    return ["WAITING ON OWNER"] + ["  " + item for item in (waiting_items(plan_list, prs) or ["nothing"])]


def waiting_items(plan_list, prs):
    """Answer the plain list of things waiting on the owner."""
    items = ["merge #%d" % pr.number for pr in (prs or [])]
    items += [
        "plan %s: %d unanswered question%s" % (printable(plan.name), plan.unanswered, "" if plan.unanswered == 1 else "s")
        for plan in plan_list
        if plan.unanswered
    ]
    items += ["plan %s: still Draft" % printable(plan.name) for plan in plan_list if first_word(plan.status) == "Draft"]
    if prs is None:
        items.append("pull requests: not checked")
    return items


def _routing(summary, routing_path):
    if summary is None:
        return ["ROUTING LOG", "  no routing log at %s" % routing_path]
    if summary.problem:
        return ["ROUTING LOG", "  routing log at %s %s" % (routing_path, summary.problem)]
    header = "  %-8s %5s %10s %8s %15s %5s %9s" % ("model", "runs", "tokens", "minutes", "findings H/M/L", "kept", "not seen")
    rows = ["ROUTING LOG", header]
    for model in sorted(summary.models):
        totals = summary.models[model]
        rows.append(
            "  %-8s %5d %10s %8.1f %15s %5d %9d"
            % (
                model,
                totals.runs,
                "{:,}".format(totals.tokens),
                totals.minutes,
                "%d/%d/%d" % totals.findings,
                totals.kept,
                totals.not_seen,
            )
        )
    if summary.unread:
        rows.append("  rows not read: %d" % summary.unread)
    return rows
