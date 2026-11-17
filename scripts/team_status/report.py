"""Turn the gathered state into the printed report (spec section 9)."""
from datetime import datetime, timezone

from team_status.config import DEFAULT_EVENTS
from team_status.plans import first_word

PLAN_NAME_WIDTH = 36
AGENT_NAME_WIDTH = 14
GLYPHS = {"running": "\u25b6", "done": "\u2713", "failed": "\u2717", "silent": "?"}


def render(project, head, plan_list, branches, prs, summary, routing_path, agents=None, now=None, events_path=DEFAULT_EVENTS):
    now = now or datetime.now(timezone.utc)
    lines = ["agent-team · %s · %s %s" % (project, head.branch, head.commit), ""]
    lines += format_agents(agents, now, events_path) + [""]
    lines += _plans(plan_list) + [""]
    lines += ["WORKTREES   %d   %s" % (len(branches), ", ".join(branches)), ""]
    lines += _prs(prs) + [""]
    lines += _waiting(plan_list, prs) + [""]
    lines += _routing(summary, routing_path)
    return "\n".join(lines) + "\n"


def format_agents(log, now, events_path):
    """Answer the AGENTS section lines; say so when there is nothing to show."""
    if log is None or (log.seen == 0 and log.unread == 0):
        return ["AGENTS", "  no agent events recorded yet (%s)" % events_path]
    rows = log.rows(now)
    lines = ["AGENTS"]
    if rows:
        item_width = max(len(row.item or "-") for row in rows)
        status = [_status(row) for row in rows]
        status_width = max(len(text) for text in status)
        for row, text in zip(rows, status):
            lines.append(
                "  %-*s  %-*s %-*s  %s  %d calls"
                % (item_width, row.item or "-", AGENT_NAME_WIDTH, row.agent or "-", status_width, text, _clock(row.seconds), row.calls)
            )
            if row.shared > 1:
                lines.append("  %d agents share this row" % row.shared)
    elif log.seen:
        lines.append("  no agent activity since the last plan marker")
    if log.unread:
        lines.append("  %d line%s not read" % (log.unread, "" if log.unread == 1 else "s"))
    if log.plan is None and log.seen:
        lines.append("  no plan marker: showing every event")
    return lines


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
            rows.append("  %-*s %s" % (PLAN_NAME_WIDTH, plan.name, plan.problem))
        else:
            status = first_word(plan.status)
            rows.append("  %-*s %-9s lead: %s" % (PLAN_NAME_WIDTH, plan.name, status, plan.lead or "(none)"))
    return ["PLANS"] + rows


def _prs(prs):
    if prs is None:
        return ["OPEN PRs    not checked: gh unavailable"]
    return ["OPEN PRs    %d" % len(prs)] + ["  #%d %s" % (pr.number, pr.title) for pr in prs]


def _waiting(plan_list, prs):
    items = ["merge #%d" % pr.number for pr in (prs or [])]
    items += [
        "plan %s: %d unanswered question%s" % (plan.name, plan.unanswered, "" if plan.unanswered == 1 else "s")
        for plan in plan_list
        if plan.unanswered
    ]
    items += ["plan %s: still Draft" % plan.name for plan in plan_list if first_word(plan.status) == "Draft"]
    if prs is None:
        items.append("pull requests: not checked")
    return ["WAITING ON OWNER"] + ["  " + item for item in (items or ["nothing"])]


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
