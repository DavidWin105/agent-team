"""Turn the gathered state into the printed report (spec section 9)."""
from team_status.plans import first_word

PLAN_NAME_WIDTH = 36


def render(project, head, plan_list, branches, prs, summary, routing_path):
    lines = ["agent-team · %s · %s %s" % (project, head.branch, head.commit), ""]
    lines += _plans(plan_list) + [""]
    lines += ["WORKTREES   %d   %s" % (len(branches), ", ".join(branches)), ""]
    lines += _prs(prs) + [""]
    lines += _waiting(plan_list, prs) + [""]
    lines += _routing(summary, routing_path)
    return "\n".join(lines) + "\n"


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
