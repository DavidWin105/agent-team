"""Draw the --watch screen as boxes and cards (spec section 6.3a). Shows only what the log holds."""
import re
import unicodedata

from team_status.config import model_for
from team_status.report import GLYPHS, calls_text, shared_note

MAX_PER_ROW = 4
GAP = 2
LOG_LINES = 5
ZERO_WIDTH = ("Mn", "Me", "Cf")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
RESET = "\x1b[0m"
TIER_COLOR = {"fable": "38;5;141", "opus": "38;5;209", "sonnet": "38;5;75"}
STATE_COLOR = {"running": "38;5;75", "done": "38;5;78", "failed": "38;5;203", "silent": "38;5;214"}
GREY = "38;5;245"
AMBER = "38;5;214"


def display_width(text):
    """Answer the terminal columns text takes once ANSI codes are removed: wide and fullwidth 2, combining and zero-width 0."""
    return sum(_char_width(char) for char in _plain(text))


def _char_width(char):
    if unicodedata.combining(char) or unicodedata.category(char) in ZERO_WIDTH:
        return 0
    return 2 if unicodedata.east_asian_width(char) in "WF" else 1


def render(rows, recent, cfg, lead_line, waiting, width, color, notes=(), warning=None, height=None, plan=None, clock=None):
    """Answer the card screen as a list of lines, none wider than width, or None when it cannot fit height.

    plan and clock make the AGENT TEAM header line; warning comes next. notes say the log is empty or
    incomplete (report.log_notes). With a height, a screen too tall first loses the log, then the card
    rows that do not fit; the end box and the WAITING ON YOU box always stay. When not even one card row
    fits, or the parts always kept are taller than height, the answer is None: the caller draws the table.
    Returns Optional[list]."""
    paint = _painter(color)
    top = _header(plan, clock, width, paint) if plan or clock else []
    top += [_clip(paint(warning, "1;" + AMBER), width)] if warning else []
    lead = model_for(cfg, "lead")
    lead_title = paint(("%s · lead" % lead) if lead else "lead", "1;" + TIER_COLOR.get(lead, "0"))
    top += _centered(_box([lead_title, paint(lead_line, GREY)], min(width, 70), TIER_COLOR.get(lead), paint), width)
    groups, end = [], []
    if rows:
        if any(row.agent == "builder" for row in rows):
            top += _centered(_box([paint("Dispatch builders", "1"), paint("one per item", GREY)], min(width, 40), None, paint), width)
        groups = _card_rows(rows, cfg, width, paint)
        end = _centered(_box(["back to lead · verify · open PRs"], min(width, 40), GREY, paint), width)
    notes = list(notes) + ["%s · %s: %s" % (row.item or "-", row.agent or "-", shared_note(row)) for row in rows if row.shared > 1]
    middle = [""] + [_clip(paint(note, AMBER), width) for note in notes]
    log = _log(recent, cfg, width, paint)
    items = " · ".join(waiting) if waiting else "nothing"
    bottom = [""] + _box([paint("WAITING ON YOU", "1;" + AMBER) + "   " + items], width, AMBER, paint)
    shown = [line for group in groups for line in group]
    if height and len(top) + len(shown) + len(end) + len(middle) + len(log) + len(bottom) > height:
        log = []
        room = height - len(top) - len(end) - len(middle) - len(bottom)
        if room < 0:
            return None
        if len(shown) > room:
            room -= 1  # the "+K more agents" line
            fit = 0
            while fit < len(groups) and sum(len(group) for group in groups[:fit + 1]) <= room:
                fit += 1
            if fit == 0:
                return None
            shown = [line for group in groups[:fit] for line in group]
            hidden = len(rows) - min(fit * MAX_PER_ROW, len(rows))
            shown.append(_clip(paint("+%d more agents (use a taller terminal)" % hidden, AMBER), width))
    return top + shown + end + middle + log + bottom


def _header(plan, clock, width, paint):
    """Answer the AGENT TEAM line: the plan name on the left, the clock right-aligned."""
    right = paint(clock, GREY) if clock else ""
    room = width - display_width(right) - (2 if clock else 0)
    left = _clip(paint("AGENT TEAM" + (" · plan: %s" % plan if plan else ""), "1;" + TIER_COLOR["opus"]), room)
    return [left + " " * (width - display_width(left) - display_width(right)) + right]


def _painter(color):
    def paint(text, code):
        return "\x1b[%sm%s%s" % (code, text, RESET) if color and code and text else text
    return paint


def _plain(text):
    return ANSI.sub("", text)


def _clip(text, room):
    """Cut text to room display columns with an ellipsis, keeping ANSI codes intact and wide characters whole."""
    if display_width(text) <= room:
        return text
    room = max(room, 0)
    keep = max(room - 1, 0)
    out, shown, pos, full = [], 0, 0, False
    for match in list(ANSI.finditer(text)) + [None]:
        chunk = text[pos:match.start() if match else len(text)]
        for char in chunk:
            if full:
                break
            size = _char_width(char)
            if shown + size > keep:
                full = True
                break
            out.append(char)
            shown += size
        if match:
            out.append(match.group())
            pos = match.end()
    return "".join(out) + ("…" if room else "") + (RESET if "\x1b" in text else "")


def _pad(text, room):
    text = _clip(text, room)
    return text + " " * (room - display_width(text))


def _box(content, width, border, paint):
    """Answer the box lines for content lines, left aligned, exactly width wide."""
    inner = max(width - 4, 0)
    lines = [paint("┌" + "─" * (width - 2) + "┐", border)]
    for text in content:
        lines.append(paint("│", border) + " " + _pad(text, inner) + " " + paint("│", border))
    lines.append(paint("└" + "─" * (width - 2) + "┘", border))
    return lines


def _centered(lines, width):
    shift = " " * ((width - display_width(lines[0])) // 2)
    return [shift + line for line in lines]


def _card_rows(rows, cfg, width, paint):
    """Answer the card rows, each a list of lines, MAX_PER_ROW cards side by side."""
    per_row = MAX_PER_ROW
    card_width = max((width - GAP * (per_row - 1)) // per_row, 6)
    cards = [_card(row, cfg, card_width, paint) for row in rows]
    groups = []
    for start in range(0, len(cards), per_row):
        group = cards[start:start + per_row]
        groups.append([(" " * GAP).join(parts) for parts in zip(*group)])
    return groups


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
    footer_right = calls_text(row.calls)
    gap = max(inner - display_width(footer_left) - display_width(footer_right), 3)
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
        room = max(width - display_width(clock) - display_width(role) - 4, 0)
        lines.append("%s  %s  %s" % (paint(clock, GREY), paint(role, code), _clip(what, room)))
    return [_clip(line, width) for line in lines]
