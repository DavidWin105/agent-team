"""Draw the --watch screen as boxes and cards (spec section 6.3a). Shows only what the log holds."""
import re

from team_status.config import model_for
from team_status.report import GLYPHS, shared_note

MAX_PER_ROW = 4
GAP = 2
LOG_LINES = 5
ANSI = re.compile(r"\x1b\[[0-9;]*m")
RESET = "\x1b[0m"
TIER_COLOR = {"fable": "38;5;141", "opus": "38;5;209", "sonnet": "38;5;75"}
STATE_COLOR = {"running": "38;5;75", "done": "38;5;78", "failed": "38;5;203", "silent": "38;5;214"}
GREY = "38;5;245"
AMBER = "38;5;214"


def render(rows, recent, cfg, lead_line, waiting, width, color, notes=(), warning=None):
    """Answer the card screen as a list of lines, none wider than width.

    notes say the log is empty or incomplete (report.log_notes); warning goes on the first line."""
    paint = _painter(color)
    lines = [_clip(paint(warning, "1;" + AMBER), width)] if warning else []
    lead = model_for(cfg, "lead")
    lead_title = paint(("%s · lead" % lead) if lead else "lead", "1;" + TIER_COLOR.get(lead, "0"))
    lines += _centered(_box([lead_title, paint(lead_line, GREY)], min(width, 70), TIER_COLOR.get(lead), paint), width)
    if rows:
        lines += _centered(_box([paint("Dispatch builders", "1"), paint("one per item", GREY)], min(width, 40), None, paint), width)
        lines += _card_rows(rows, cfg, width, paint)
        lines += _centered(_box(["back to lead · verify · open PRs"], min(width, 40), GREY, paint), width)
    notes = list(notes) + ["%s · %s: %s" % (row.item or "-", row.agent or "-", shared_note(row)) for row in rows if row.shared > 1]
    lines += [""] + [_clip(paint(note, AMBER), width) for note in notes] + _log(recent, cfg, width, paint) + [""]
    items = " · ".join(waiting) if waiting else "nothing"
    lines += _box([paint("WAITING ON YOU", "1;" + AMBER) + "   " + items], width, AMBER, paint)
    return lines


def _painter(color):
    def paint(text, code):
        return "\x1b[%sm%s%s" % (code, text, RESET) if color and code and text else text
    return paint


def _plain(text):
    return ANSI.sub("", text)


def _clip(text, room):
    """Cut text to room display columns with an ellipsis, keeping ANSI codes intact."""
    if len(_plain(text)) <= room:
        return text
    room = max(room, 0)
    out, shown, pos = [], 0, 0
    keep = max(room - 1, 0)
    for match in ANSI.finditer(text):
        chunk = text[pos:match.start()]
        take = chunk[: max(keep - shown, 0)]
        out.append(take)
        shown += len(take)
        out.append(match.group())
        pos = match.end()
    take = text[pos:][: max(keep - shown, 0)]
    out.append(take)
    shown += len(take)
    return "".join(out) + ("…" if room else "") + (RESET if "\x1b" in text else "")


def _pad(text, room):
    text = _clip(text, room)
    return text + " " * (room - len(_plain(text)))


def _box(content, width, border, paint):
    """Answer the box lines for content lines, left aligned, exactly width wide."""
    inner = max(width - 4, 0)
    lines = [paint("┌" + "─" * (width - 2) + "┐", border)]
    for text in content:
        lines.append(paint("│", border) + " " + _pad(text, inner) + " " + paint("│", border))
    lines.append(paint("└" + "─" * (width - 2) + "┘", border))
    return lines


def _centered(lines, width):
    shift = " " * ((width - len(_plain(lines[0]))) // 2)
    return [shift + line for line in lines]


def _card_rows(rows, cfg, width, paint):
    per_row = MAX_PER_ROW
    card_width = max((width - GAP * (per_row - 1)) // per_row, 6)
    cards = [_card(row, cfg, card_width, paint) for row in rows]
    lines = []
    for start in range(0, len(cards), per_row):
        group = cards[start:start + per_row]
        for parts in zip(*group):
            lines.append((" " * GAP).join(parts))
    return lines


def _card(row, cfg, width, paint):
    model = model_for(cfg, row.agent)
    code = TIER_COLOR.get(model)
    inner = max(width - 4, 0)
    title = paint(row.agent or "-", "1;" + code if code else "1")
    if model:
        title += paint(" · " + model, code)
    item = paint(row.item or "-", GREY)
    text = row.doing if row.state == "running" and row.doing else row.state
    state = paint("%s %s" % (GLYPHS[row.state], text), STATE_COLOR[row.state])
    footer_left = "%dm%02ds" % divmod(row.seconds, 60)
    footer_right = "%d calls" % row.calls
    gap = max(inner - len(footer_left) - len(footer_right), 3)
    footer = paint(footer_left + " " * gap + footer_right, GREY)
    return _box([title, item, state, "", footer], width, code or STATE_COLOR[row.state], paint)


def _log(recent, cfg, width, paint):
    lines = []
    for event in recent[:LOG_LINES]:
        clock = event.ts[11:19]
        role = event.agent or "-"
        code = TIER_COLOR.get(model_for(cfg, event.agent))
        if event.event == "start":
            what = "started"
        elif event.event == "stop":
            what = "stopped"
        elif event.event == "plan":
            what = ("plan " + event.target).strip()
        else:
            what = ("%s %s" % (event.tool, event.target)).strip()
        room = max(width - len(clock) - len(role) - 4, 0)
        lines.append("%s  %s  %s" % (paint(clock, GREY), paint(role, code), _clip(what, room)))
    return [_clip(line, width) for line in lines]
