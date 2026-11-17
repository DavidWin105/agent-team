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


def draw(rows, recent=(), waiting=(), width=120, color=False, lead=LEAD, notes=(), warning=None):
    return cards.render(rows, list(recent), valid_config(), lead, list(waiting), width, color,
                        notes=list(notes), warning=warning)


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
