import re
import shutil
import unittest
from datetime import datetime, timezone

from fixtures import make_project, valid_config, write_events
from team_status import cards, report
from team_status.events import Event, EventLog, Row

ANSI = re.compile(r"\x1b\[[0-9;]*m")
LEAD = "1 running · 1 done"


def row(agent="builder", item="subtract", state="running", doing="Edit test_calc.py", calls=12, seconds=192, shared=1):
    return Row(agent, item, state, doing, calls, seconds, shared)


def event(ts="2026-11-17T14:02:09Z", kind="tool", agent="builder", tool="Edit", target="src/calc.py"):
    return Event(ts, kind, "a1", agent, "subtract", tool, target, "pre", None)


def draw(rows, recent=(), waiting=(), width=120, color=False, lead=LEAD, notes=(), warning=None, height=None, plan=None,
         clock=None):
    return cards.render(rows, list(recent), valid_config(), lead, list(waiting), width, color,
                        notes=list(notes), warning=warning, height=height, plan=plan, clock=clock)


BORDERS = "│┌┐└┘"


def border_columns(line):
    """Answer the display columns of the box border characters in a line."""
    columns, col = [], 0
    for char in line:
        if char in BORDERS:
            columns.append(col)
        col += cards.display_width(char)
    return columns


class CardsTest(unittest.TestCase):
    def text(self, *args, **kwargs):
        return "\n".join(draw(*args, **kwargs))

    def test_card_title_has_role_and_model(self):
        self.assertIn("builder · sonnet", self.text([row()]))

    def test_unknown_agent_has_no_model_in_title(self):
        out = self.text([row(agent="stranger")])
        self.assertIn("stranger", out)
        self.assertNotIn("stranger ·", out)

    def test_four_cards_per_row_then_wrap(self):
        out = draw([row(item="i%d" % n) for n in range(5)])
        tops = [line for line in out if line.count("┌") == 4]
        self.assertEqual(len(tops), 1)
        self.assertEqual(len([line for line in out if line.startswith("┌")]), 3)  # two card rows and the waiting box
        self.assertEqual(len([line for line in out if line.startswith("┌") and line.count("┌") == 1 and len(line) < 40]), 1)

    def test_card_shows_state_doing_and_footer(self):
        out = self.text([row()])
        self.assertIn("▶ Edit test_calc.py", out)
        self.assertIn("3m12s", out)
        self.assertIn("12 calls", out)
        self.assertIn("subtract", out)
        self.assertIn("✓ done", self.text([row(state="done", doing="")]))
        self.assertIn("✗ failed", self.text([row(state="failed", doing="")]))
        self.assertIn("? silent", self.text([row(state="silent", doing="")]))

    def test_waiting_box_lists_items(self):
        out = self.text([row()], waiting=["merge #7", "plan x: still Draft"])
        self.assertIn("WAITING ON YOU", out)
        self.assertIn("merge #7", out)
        self.assertIn("plan x: still Draft", out)
        self.assertIn("nothing", self.text([row()]))

    def test_log_shows_five_newest_first(self):
        recent = [event(ts="2026-11-17T14:02:%02dZ" % (59 - n), target="file%d" % n) for n in range(7)]
        out = self.text([row()], recent=recent)
        self.assertIn("14:02:59  builder  Edit file0", out)
        self.assertIn("file4", out)
        self.assertNotIn("file5", out)
        self.assertLess(out.index("file0"), out.index("file4"))

    def test_log_words_for_start_stop_plan(self):
        recent = [event(kind="start", tool="", target=""), event(kind="stop", tool="", target=""), event(kind="plan", agent="", tool="", target="a.md")]
        out = self.text([row()], recent=recent)
        self.assertIn("builder  started", out)
        self.assertIn("builder  stopped", out)
        self.assertIn("plan a.md", out)

    def test_narrow_width_never_cuts_a_line(self):
        for width in (100, 120, 200):
            rows = [row(agent="security-reviewer", item="a-very-long-item-name-" * 4, doing="Edit " + "very/long/path/" * 10) for _ in range(6)]
            recent = [event(target="x" * 300)]
            out = draw(rows, recent, ["waiting " * 40], width=width, lead="x" * 300)
            for line in out:
                self.assertLessEqual(len(line), width, line)

    def test_color_adds_ansi_only_when_asked(self):
        self.assertNotIn("\x1b", self.text([row()]))
        colored = draw([row()], [event()], ["merge #7"], color=True)
        joined = "\n".join(colored)
        self.assertIn("\x1b[", joined)
        self.assertEqual(draw([row()], [event()], ["merge #7"], color=False), [ANSI.sub("", line) for line in colored])
        for line in colored:
            self.assertLessEqual(len(ANSI.sub("", line)), 120)

    def test_no_agents_prints_the_no_events_message(self):
        notes = report.log_notes(None, [], ".claude/team/events.jsonl")
        out = draw([], lead="no agents yet", notes=notes)
        self.assertIn("no agent events recorded yet (.claude/team/events.jsonl)", out)
        self.assertIn("│ no agents yet", "\n".join(out))
        self.assertFalse([line for line in out if line.count("│") >= 4])  # no card row

    def test_notes_print_above_the_log(self):
        out = draw([row()], recent=[event()], notes=["2 lines not read", "no plan marker: showing every event"])
        self.assertIn("2 lines not read", out)
        self.assertIn("no plan marker: showing every event", out)
        log_line = next(i for i, line in enumerate(out) if "Edit src/calc.py" in line)
        self.assertLess(out.index("2 lines not read"), log_line)
        self.assertGreater(out.index("2 lines not read"), max(i for i, line in enumerate(out) if "┘" in line and i < log_line))

    def test_one_call_is_singular(self):
        out = self.text([row(calls=1)])
        self.assertIn("1 call", out)
        self.assertNotIn("1 calls", out)

    def test_shared_row_note_names_the_card(self):
        out = draw([row(shared=2)])
        self.assertIn("subtract · builder: 2 agents share this row", out)
        self.assertFalse([line for line in draw([row()]) if "share this row" in line])

    def test_warning_line_on_top(self):
        out = draw([row()], warning="WARNING: x is not ignored by git; add x to .gitignore")
        self.assertEqual(out[0], "WARNING: x is not ignored by git; add x to .gitignore")
        self.assertNotIn("WARNING", "\n".join(draw([row()])))
        colored = draw([row()], color=True, warning="WARNING: " + "y" * 300)
        self.assertLessEqual(len(ANSI.sub("", colored[0])), 120)

    def test_cards_equal_width_and_aligned(self):
        out = draw([row(item="i%d" % n) for n in range(4)], width=120)
        card = [line for line in out if line.count("│") == 8]
        self.assertTrue(card)
        self.assertEqual(len({len(line) for line in card}), 1)

    def test_header_shows_plan_name_and_clock(self):
        out = draw([row()], plan="plans/2026-11-17-calc.md", clock="14:02:11", warning="WARNING: x")
        self.assertTrue(out[0].startswith("AGENT TEAM · plan: plans/2026-11-17-calc.md"), out[0])
        self.assertTrue(out[0].endswith("14:02:11"), out[0])
        self.assertEqual(cards.display_width(out[0]), 120)
        self.assertEqual(out[1], "WARNING: x")
        no_plan = draw([row()], clock="14:02:11")
        self.assertTrue(no_plan[0].startswith("AGENT TEAM "), no_plan[0])
        self.assertNotIn("plan:", no_plan[0])
        colored = draw([row()], plan="p" * 300, clock="14:02:11", color=True)
        self.assertLessEqual(cards.display_width(colored[0]), 120)
        self.assertTrue(ANSI.sub("", colored[0]).endswith("14:02:11"))

    def test_dispatch_box_hidden_without_builders(self):
        self.assertIn("Dispatch builders", self.text([row(), row(agent="code-reviewer")]))
        out = self.text([row(agent="code-reviewer"), row(agent="doc-recorder")])
        self.assertNotIn("Dispatch builders", out)
        self.assertNotIn("one per item", out)
        self.assertIn("code-reviewer · opus", out)
        self.assertIn("back to lead", out)

    def tall(self):
        rows = [row(item="item%02d" % n) for n in range(12)]
        recent = [event(target="logfile%d" % n) for n in range(5)]
        return rows, recent

    def test_tall_screen_drops_log_then_cards(self):
        rows, recent = self.tall()
        full = draw(rows, recent, ["merge #7"])
        self.assertIn("logfile0", "\n".join(full))
        less = draw(rows, recent, ["merge #7"], height=len(full) - 1)
        self.assertLessEqual(len(less), len(full) - 1)
        self.assertNotIn("logfile", "\n".join(less))
        self.assertIn("item11", "\n".join(less))
        self.assertNotIn("more agents", "\n".join(less))
        small = draw(rows, recent, ["merge #7"], height=len(full) - 12)
        joined = "\n".join(small)
        self.assertLessEqual(len(small), len(full) - 12)
        self.assertNotIn("logfile", joined)
        self.assertIn("item03", joined)
        self.assertNotIn("item04", joined)
        self.assertIn("+8 more agents (use a taller terminal)", small)
        self.assertIn("back to lead", joined)
        self.assertIn("WAITING ON YOU", small[-2])

    def test_tall_screen_keeps_waiting_box(self):
        rows, recent = self.tall()
        out = draw(rows, recent, ["merge #7"], height=10)
        joined = "\n".join(out)
        self.assertIn("+12 more agents (use a taller terminal)", out)
        self.assertNotIn("item00", joined)
        self.assertIn("back to lead · verify · open PRs", joined)
        self.assertIn("WAITING ON YOU   merge #7", out[-2])
        self.assertTrue(out[-1].startswith("└"))

    def test_unknown_height_drops_nothing(self):
        rows, recent = self.tall()
        full = draw(rows, recent, ["merge #7"])
        self.assertEqual(draw(rows, recent, ["merge #7"], height=0), full)
        self.assertNotIn("more agents", "\n".join(full))
        self.assertEqual(len([line for line in full if line.count("┌") == 4]), 3)

    def test_display_width_wide_and_combining(self):
        self.assertEqual(cards.display_width("abc"), 3)
        self.assertEqual(cards.display_width("日本語"), 6)
        self.assertEqual(cards.display_width("ＡＢ"), 4)  # fullwidth
        self.assertEqual(cards.display_width("😀"), 2)
        self.assertEqual(cards.display_width("cafe\u0301"), 4)
        self.assertEqual(cards.display_width("a\u200bb"), 2)
        self.assertEqual(cards.display_width("\x1b[1;38;5;75m日本\x1b[0m"), 4)
        self.assertEqual(cards.display_width("…"), 1)
        self.assertEqual(cards.display_width(""), 0)

    def test_wide_characters_keep_box_aligned_at_widths_100_120_200(self):
        wide = "日本語のアイテム名前" * 3
        rows = [row(item=wide, doing="Edit src/日本語 notes/cafe\u0301.py 😀" * 3),
                row(agent="security-reviewer", item="cafe\u0301" * 30, doing="Read ＡＢＣ" * 20),
                row(item="i😀" * 40)] * 2
        recent = [event(target="src/日本語/" * 30), event(agent="日本語", target="x")]
        for width in (100, 120, 200):
            for color in (False, True):
                out = draw(rows, recent, ["plan 日本語: still Draft " * 10], width=width, color=color,
                           lead="日本語 " * 40, plan="計画" * 80, clock="14:02:11")
                for line in out:
                    self.assertLessEqual(cards.display_width(line), width, (width, line))
                plain = [ANSI.sub("", line) for line in out]
                card_lines = [line for line in plain if line.count("│") == 8 or line.count("┌") == 4 or line.count("└") == 4]
                self.assertTrue(card_lines)
                self.assertEqual(len({tuple(border_columns(line)) for line in card_lines}), 1, (width, card_lines))
                waiting = plain[-3:]
                self.assertEqual({tuple(border_columns(line)) for line in waiting}, {(0, width - 1)}, waiting)
                self.assertEqual({cards.display_width(line) for line in waiting}, {width})

    def test_clip_never_cuts_a_wide_character(self):
        self.assertEqual(cards._clip("日本語", 4), "日…")
        self.assertEqual(cards._clip("日本語", 6), "日本語")
        self.assertEqual(cards.display_width(cards._pad("日本語", 5)), 5)


class CardsFromLogTest(unittest.TestCase):
    def test_escape_and_newline_in_target_never_reach_the_cards(self):
        root = make_project(commit=False)
        self.addCleanup(shutil.rmtree, root)
        bad = "x\x1b]0;PWNED\x07\x1b[2J\n  multiply  builder  \u2713 done.py"
        log = EventLog(write_events(root, [
            {"ts": "2026-11-17T10:09:50Z", "event": "start", "agent_id": "a1", "agent": "builder", "item": "subtract"},
            {"ts": "2026-11-17T10:09:51Z", "event": "tool", "agent_id": "a1", "agent": "builder", "item": "subtract",
             "tool": "Edit", "target": bad, "phase": "pre"},
        ]))
        log.refresh()
        rows = log.rows(datetime(2026, 11, 17, 10, 10, 0, tzinfo=timezone.utc))
        out = cards.render(rows, log.recent(5), valid_config(), LEAD, [], 120, False)
        joined = "\n".join(out)
        self.assertNotIn("\x1b", joined)
        self.assertNotIn("\x07", joined)
        self.assertFalse(any("\n" in line for line in out))
        self.assertIn("builder  Edit x?]0;PWNED??[2J?  multiply  builder  \u2713 done.py", joined)
        card = [line for line in out if line.startswith(("\u250c", "\u2502", "\u2514")) and len(line) < 60]
        self.assertEqual(len(card), 7)
        self.assertEqual(len({len(line) for line in card}), 1)
