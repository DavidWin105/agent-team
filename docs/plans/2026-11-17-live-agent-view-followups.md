# Live Agent View Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the follow-up items listed in the description of pull request 1 (live agent view).

**Architecture:** Two tasks over disjoint files. Task 1 changes how the log is read, recorded and cleaned (`events.py`, `hook.py`, `report.py`, tests). Task 2 changes what the card view shows and how it is drawn (`cards.py`, `cli.py`, `repo`-call handling, one command doc). Task 2 builds on Task 1's `EventLog` behaviour.

**Tech Stack:** Python 3.9+ standard library only, `unittest`.

**Spec:** `docs/specs/2026-11-17-live-agent-view-design.md` (sections 6.1 to 6.3a, 12) and the merged implementation on `main`. Item rulings below were made by the controller.

## Global Constraints

- Python 3.9+, standard library only. Run tests: `cd tests && PYTHONPATH=../scripts python3 -m unittest <module> -v`.
- Baseline: 204 tests, 1 known unrelated failure (`test_config.test_broken_json_names_the_line`, Python 3.13). Do not fix it.
- The log still holds only tool names, project-relative paths and the sanitised first Bash word; the hook still exits 0 and prints nothing.
- Table report output for the existing good cases must not change except where an item below says so.
- Every test is seen failing before the code that passes it. Commit after each task.

## Review Focus

1. A plan marker arriving mid-run drops earlier events without losing rows that started after it, and `recent()` and memory stay consistent across a log reset.
2. A very tall agent list never pushes the WAITING ON YOU box off screen, and never produces a line wider than the terminal.
3. A slow or hanging `gh` never delays a frame, and its result still arrives later.
4. Wide (CJK, emoji) and combining characters never push a box edge out of line.
5. A payload just over the old 1 MB limit still records its event.

---

## Task 1: Log reading, recording and cleaning

**Files:**
- Modify: `scripts/team_status/events.py`, `scripts/team_status/hook.py`, `scripts/team_status/report.py`
- Test: `tests/test_events.py`, `tests/test_hook.py`, `tests/test_report.py`

**Items and rulings (all binding):**
1. **Memory and rescanning.** `EventLog` keeps only events at or after the last `plan` event (the plan event itself is kept). When a `plan` event is read, everything before it is dropped from memory, and `recent()` is rebuilt from the kept events only. Rows are computed from the kept events as before. If there is no `plan` event, behaviour is unchanged. Resetting the log (shrink, replace) still starts over.
2. **Card log before the marker.** `EventLog.recent(n)` returns only events from the current run (after the drop in item 1), newest first.
3. **Killed agent's clock.** An open tool call (a `pre` with no matching `post`) older than 1800 seconds (module constant `OPEN_CALL_LIMIT = 1800`) stops counting as open, so the row becomes `silent` once its last event is also older than 300 seconds. Elapsed time for a still-`running` row keeps counting to `now`; for a `silent` row it stops at the last event.
4. **Payloads over 1 MB.** `hook.MAX_INPUT` becomes 8 * 1024 * 1024 characters, so a large `Write` payload still records its event. A payload over the new limit is still dropped (no parsing of huge input). Update the existing tests that assert the old limit.
5. **Pluralisation.** `1 call` / `N calls` in rows and cards; `1 line not read` / `N lines not read`; `1 agent shares this row` is never shown (shared is always 2 or more). Check every place the three phrases are produced (`report.py`, `cards.py`).
6. **Unicode and spaces in paths.** Add tests: a path with spaces and a path with unicode characters (`src/日本語 notes/café.py`) are logged on one JSON line, relative to the project, and read back unchanged by `EventLog`.
7. **PR titles and plan names.** Text from `gh` (PR titles) and from plan files (name, status, lead) is passed through `events.printable` before it reaches the terminal in `report.py` (table report, both layouts' WAITING items). Add `printable` import from `events`; do not duplicate it.

- [ ] **Step 1:** Write failing tests for items 1, 2, 3, 5, 6, 7 and the changed limit in item 4 (names: `test_plan_marker_drops_earlier_events`, `test_recent_only_current_run`, `test_open_call_older_than_limit_goes_silent`, `test_one_call_is_singular`, `test_one_line_not_read_is_singular`, `test_unicode_and_space_path_roundtrip`, `test_pr_title_control_characters_are_replaced`, `test_plan_name_control_characters_are_replaced`, `test_payload_between_one_and_eight_mb_is_recorded`).
- [ ] **Step 2:** Run them; expect FAIL.
- [ ] **Step 3:** Implement the changes in `events.py`, `hook.py`, `report.py`.
- [ ] **Step 4:** Run the whole suite; expect only the known failure.
- [ ] **Step 5: Commit.**

## Task 2: Card view and loop behaviour

**Files:**
- Modify: `scripts/team_status/cards.py`, `scripts/team_status/cli.py`, `scripts/team_status/report.py` (header and plan line only), `commands/team-status.md`
- Test: `tests/test_cards.py`, `tests/test_cli.py`, `tests/test_report.py`

**Interfaces:**
- Consumes: Task 1's `EventLog` (current-run `recent`, memory drop).
- Produces: `cards.display_width(text: str) -> int` (East Asian wide and fullwidth characters count 2, combining and zero-width characters count 0, everything else 1); `cli.main(..., height=None)` (injectable terminal height; default `shutil.get_terminal_size().lines` per frame); a `cards.render` that accepts `height: Optional[int]` and `plan: Optional[str]` and `clock: Optional[str]`.

**Items and rulings (all binding):**
1. **Header clock and plan name.** In `--watch` frames, both layouts show the plan marker name when `log.plan` is set: table AGENTS line becomes `AGENTS   plan: <name>`; cards get a first line `AGENT TEAM · plan: <name>` and the clock `HH:MM:SS` (local time of `now`, right-aligned in the cards header; in the table it is appended to the header line). The one-off snapshot shows the plan name but no clock, so snapshot output stays deterministic.
2. **"Dispatch builders" only when needed.** Draw that box only when at least one row has the agent `builder`; otherwise the lead box connects straight to the cards.
3. **Tall screens.** When the cards output has more lines than `height`: first drop the log section; if still too tall, show only the card rows that fit and add the line `+K more agents (use a taller terminal)`. The WAITING ON YOU box and the end box are always kept. When `height` is unknown or 0, nothing is dropped. The table layout is unchanged.
4. **Wide characters.** `cards.py` measures and pads with `display_width` (after stripping ANSI), and truncates with `…` by display width so no line is wider than the terminal; a wide character is never cut in half.
5. **`gh` stalls.** In `--watch`, `repo.open_prs` runs in a background daemon thread started on frames 0, 10, 20, ...; frames use the latest finished result (`None` until the first result, shown as today's "not checked" wording). A frame never waits for `gh`. The one-off snapshot still calls `open_prs` directly. At most one `gh` thread runs at a time.
6. **Command doc.** `commands/team-status.md` description (front matter) and body mention the AGENTS section and `--watch`.

- [ ] **Step 1:** Write failing tests: `test_header_shows_plan_name_and_clock` (cards and table), `test_snapshot_shows_plan_name_without_clock`, `test_dispatch_box_hidden_without_builders`, `test_tall_screen_drops_log_then_cards`, `test_tall_screen_keeps_waiting_box`, `test_unknown_height_drops_nothing`, `test_display_width_wide_and_combining`, `test_wide_characters_keep_box_aligned_at_widths_100_120_200`, `test_slow_gh_does_not_delay_frames` (fake `open_prs` that blocks on an event; two frames complete before it is released; a later frame shows its result), `test_only_one_gh_thread_at_a_time`, and a test that `commands/team-status.md` mentions `--watch`.
- [ ] **Step 2:** Run them; expect FAIL.
- [ ] **Step 3:** Implement in `cards.py`, `cli.py`, `report.py`, `commands/team-status.md`.
- [ ] **Step 4:** Run the whole suite; expect only the known failure.
- [ ] **Step 5: Commit.**
