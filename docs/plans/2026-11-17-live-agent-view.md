# Live Agent View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hooks record what each team agent does into an event log, and `team-status --watch` shows every agent live.

**Architecture:** A new `scripts/team-event` script, called by plugin hooks, appends one JSON line per agent event to `paths.events`. A new `team_status/events.py` folds the log into one row per agent; `report.py` prints them as an AGENTS section and `cli.py` adds `--watch`, which draws a card layout (Task 9) on wide terminals and the table otherwise. A spike first checks what Claude Code's hooks really report.

**Tech Stack:** Python 3.9+ standard library, `unittest`, Claude Code plugin hooks (`hooks/hooks.json`).

**Spec:** `docs/specs/2026-11-17-live-agent-view-design.md` (approved by the owner, including the section 11 fallback; section 6.3a, the card layout, was added at the owner's request and is covered by Task 9 and the preview image `docs/media/live-view-preview-cards.png`).

## Global Constraints

- Python 3.9+, standard library only. Run tests: `cd tests && PYTHONPATH=../scripts python3 -m unittest <module> -v`.
- Hook script always exits 0, prints nothing to stdout, and does nothing unless `.claude/team.json` exists and is valid.
- The log holds tool names, project-relative file paths and the first word of a Bash command. Never file contents, command text beyond the first word, or tool output.
- Default log path `.claude/team/events.jsonl`; always in the main checkout, never in a worktree.
- Only agents whose type starts with `agent-team:` or equals a `specialists[].agent` are recorded.
- Card layout shows only data the log holds: no cost, no effort, no percent-complete bars.
- Silent = running with no event for 300 seconds and no open tool call.
- Plugin version goes to `0.2.0` in `.claude-plugin/plugin.json` (and `marketplace.json` if it carries a version).
- Hooks run `python3 -I`. Every test is seen failing before the code that passes it. Commit after each task.

## Review Focus

1. A line half-written when the viewer reads (no newline yet) is not counted or flagged until complete.
2. The log is truncated or replaced during `--watch`: the viewer starts over from the top, no crash.
3. Two agents with the same role and item and no `agent_id` show as one row marked "2 agents share this row".
4. A file path with spaces, unicode or a newline stays one valid JSON line; hook input that is not JSON, not an object, or enormous exits 0 and writes nothing.
5. An event timestamp in the future (clock skew) gives a duration of 0, not a negative.

---

## Task 1: Spike - what do the hooks report? (gate)

**Files:**
- Create: `docs/specs/2026-11-17-live-agent-view-hook-findings.md`

**Interfaces:**
- Produces: the findings file, which Tasks 6 and 7 read. It states, for the installed Claude Code: the hook event names that fire when a subagent starts and stops; the tool-call event names and whether each says which agent made the call; the JSON field names for agent id, agent type, working folder, tool name and tool input; and whether plugin agents carry the `agent-team:` prefix.

- [ ] **Step 1:** In a scratch git repo (outside this project), add a throwaway `.claude/settings.json` whose hooks for `SubagentStart`, `SubagentStop`, `PreToolUse`, `PostToolUse` run `cat >> /tmp/hook-dump.jsonl`.
- [ ] **Step 2:** In that repo, start a session, have it start one subagent that edits a file, then read `/tmp/hook-dump.jsonl`.
- [ ] **Step 3:** Write the findings file with one real (made-up-data) example line per event and the answers listed under Produces.
- [ ] **Step 4: Gate.** If subagent start/stop events are missing, or tool-call events cannot be tied to one agent, stop. Tell the owner what is missing and offer the two options in design section 11. Do not start Task 6 until the owner answers. Tasks 2 to 5 do not depend on hooks and may proceed.
- [ ] **Step 5: Commit** `docs/specs/2026-11-17-live-agent-view-hook-findings.md`.

## Task 2: `paths.events` in the config

**Files:**
- Modify: `scripts/team_status/config.py` (add `DEFAULT_EVENTS`, `events_path`, accept optional `paths.events`)
- Modify: `templates/team.json` (add `"events": ".claude/team/events.jsonl"` to `paths`)
- Test: `tests/test_config.py`, `tests/test_templates.py`

**Interfaces:**
- Produces: `config.DEFAULT_EVENTS = ".claude/team/events.jsonl"`; `config.events_path(cfg: dict) -> str` returning `cfg["paths"].get("events", DEFAULT_EVENTS)` (relative to the project).

- [ ] **Step 1:** Failing tests in `test_config.py`: `test_events_path_defaults_when_missing` (valid config without `paths.events` is valid and `events_path` returns `DEFAULT_EVENTS`); `test_events_path_used_when_set`; `test_events_must_be_non_empty_string` (value `""` or `3` gives the problem `paths.events must be a non-empty string`). In `test_templates.py` assert the template's `paths.events` equals `DEFAULT_EVENTS`.
- [ ] **Step 2:** Run the new tests; expect FAIL (no `events_path`).
- [ ] **Step 3:** Implement `events_path`; in `_check_paths` validate `events` only when present.
- [ ] **Step 4:** Run `test_config` and `test_templates`; expect PASS.
- [ ] **Step 5: Commit.**

## Task 3: Fold the log into agent rows (`events.py`)

**Files:**
- Create: `scripts/team_status/events.py`
- Test: `tests/test_events.py`; helper `write_events(root, lines)` added to `tests/fixtures.py`

**Interfaces:**
- Produces:
  - `Row = namedtuple("Row", "agent item state doing calls seconds shared")`; `state` is one of `"running"`, `"done"`, `"failed"`, `"silent"`; `doing` is `"Edit test_calc.py"` or `""`; `shared` is how many agents share the row (1 normally).
  - `class EventLog: __init__(self, path: str)`; `refresh(self) -> None` reads only new complete lines (remembers byte offset; resets if the file shrinks or vanishes); `rows(self, now: datetime) -> list[Row]`; attributes `seen: int` (events read), `unread: int` (lines that did not parse), `plan: Optional[str]` (file name of the last `plan` event).
- Event line fields (JSON): `ts` (UTC, `2026-11-17T14:02:11Z`), `event` (`start`|`tool`|`stop`|`plan`), `agent_id`, `agent`, `item`, `tool`, `target`, `phase` (`pre`|`post`, tool events), `ok` (bool, on `post` and `stop`).

- [ ] **Step 1:** Failing tests in `test_events.py` (each builds a log with `write_events`, makes an `EventLog`, calls `refresh()`, `rows(NOW)`):
  - `test_running_builder`: start, then pre-tool `Edit test_calc.py` gives one Row `("builder", "subtract", "running", "Edit test_calc.py", 1, 192, 1)`.
  - `test_done_and_failed`: stop with `ok` true gives `done`; `ok` false gives `failed`.
  - `test_calls_counted_on_pre_only`: pre+post pair counts 1.
  - `test_silent_after_300_seconds`, and `test_long_open_tool_call_is_not_silent` (last event is a `pre` 10 minutes ago stays `running`).
  - `test_only_events_since_last_plan_marker` and `test_no_plan_marker_shows_everything` (`plan` stays `None`).
  - `test_agents_without_id_share_row` (two starts, same agent and item, no ids: one Row, `shared == 2`).
  - `test_broken_line_counted_not_guessed` (`unread == 1`); `test_partial_last_line_waits` (no newline: not counted, not unread; appended newline: counted on next `refresh`).
  - `test_truncated_log_starts_over`; `test_missing_log_is_empty` (`seen == 0`, `rows == []`).
  - `test_future_timestamp_gives_zero_seconds`.
- [ ] **Step 2:** Run `test_events`; expect FAIL (module missing).
- [ ] **Step 3:** Implement `events.py`. Row key is `agent_id` when present, else `(agent, item)`. Seconds run from the row's first event to its last (to `now` while running). Read the file in binary from the saved offset and consume only up to the last `\n`.
- [ ] **Step 4:** Run `test_events`; expect PASS.
- [ ] **Step 5: Commit.**

## Task 4: AGENTS section in the report

**Files:**
- Modify: `scripts/team_status/report.py` (`render` gains `agents` argument), `scripts/team_status/cli.py`
- Test: `tests/test_report.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `EventLog`, `Row`, `config.events_path`.
- Produces: `report.render(project, head, plan_list, branches, prs, summary, routing_path, agents=None)` where `agents` is an `EventLog` or `None`; the AGENTS section goes after the header line and before PLANS. `report.format_agents(log: EventLog, now: datetime, events_path: str) -> list[str]`.

- [ ] **Step 1:** Failing tests:
  - `test_agents_section_rows`: running builder row prints `  subtract  builder        ▶ Edit test_calc.py  3m12s  12 calls`; done prints `✓ done`; failed `✗ failed`; silent `? silent`.
  - `test_no_events_message`: no log or empty log prints `  no agent events recorded yet (.claude/team/events.jsonl)`, never an empty table.
  - `test_shared_row_note` prints `  2 agents share this row` under the row; `test_unread_line_note` prints `  N lines not read`; `test_no_plan_marker_note` prints `  no plan marker: showing every event`.
  - In `test_cli.py`: `test_snapshot_shows_agents_before_plans` writes a log into a made-up project and finds AGENTS before PLANS in the output.
- [ ] **Step 2:** Run both modules; expect FAIL.
- [ ] **Step 3:** Implement `format_agents` and wire it. Time format `%dm%02ds`. Existing report tests must still pass (an absent log keeps `agents` unset in old tests by default).
- [ ] **Step 4:** Run `test_report` and `test_cli`; expect PASS.
- [ ] **Step 5: Commit.**

## Task 5: `--watch`

**Files:**
- Modify: `scripts/team_status/cli.py` (argument parsing, loop), `scripts/team_status/repo.py` (`is_ignored`)
- Test: `tests/test_cli.py`, `tests/test_repo.py`

**Interfaces:**
- Consumes: `report.render`, `EventLog`.
- Produces: `cli.main(argv, env=None, out=None, err=None, sleep=time.sleep, max_frames=None)`; `--watch` may appear before or after the project folder; `repo.is_ignored(project_dir: str, relative_path: str, env=None) -> bool` using `git check-ignore -q`.

- [ ] **Step 1:** Failing tests: `test_watch_draws_two_frames_and_sees_new_event` (`max_frames=2`, a fake `sleep` appends an event between frames; second frame shows the new row; frames separated by the clear-screen sequence `\x1b[H\x1b[2J`); `test_watch_exit_0_on_ctrl_c` (fake `sleep` raises `KeyboardInterrupt`, code 0); `test_watch_warns_once_when_log_not_ignored` (one line `team-status: .claude/team/events.jsonl is not ignored by git` on `err`, not repeated on frame 2); `test_watch_no_warning_when_ignored`. In `test_repo.py`: `is_ignored` true for an ignored file, false otherwise, false outside a repo.
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement. One `EventLog` lives across frames so only new lines are read; the other gatherers (git, gh) run again every 10th frame, not every second; `sleep(1)` between frames.
- [ ] **Step 4:** Run `test_cli` and `test_repo`; expect PASS.
- [ ] **Step 5: Commit.**

## Task 6: `team-event` hook script

**Files:**
- Create: `scripts/team-event`, `scripts/team_status/hook.py`
- Test: `tests/test_hook.py`

**Interfaces:**
- Consumes: `config.load_config`, `config.events_path`; the field names from Task 1's findings (the plan below uses `hook_event_name`, `cwd`, `agent_id`, `agent_type`, `tool_name`, `tool_input`; rename to match the findings).
- Produces: `hook.handle(payload: dict, env=None) -> None` (appends at most one line, never raises); `hook.project_root(cwd: str) -> Optional[str]` (folder holding `.claude/team.json`; for a path containing `.claude/worktrees/<slug>` it is the part before `.claude/worktrees`); `hook.main(argv: list, stdin) -> int` (always 0); `team-event --plan <file>` appends one `plan` event.

- [ ] **Step 1:** Failing tests in `test_hook.py` (made-up project from `make_project`, payload dicts, read the log back):
  - `test_no_config_writes_nothing`; `test_invalid_config_writes_nothing`.
  - `test_non_team_agent_writes_nothing`; `test_specialist_is_recorded` (fixture config has `devops-sre`).
  - `test_start_tool_stop_lines` (role without the `agent-team:` prefix; `item` filled when `cwd` is `<root>/.claude/worktrees/subtract`, empty otherwise; the log lands in `<root>`, not the worktree).
  - `test_bash_keeps_first_word_only` (`"npm test --token=abc123"` gives `target == "npm"` and `abc123` appears nowhere in the file); `test_edit_target_relative_to_project`; `test_path_outside_project_keeps_file_name_only`.
  - `test_newline_in_path_stays_one_line`; `test_not_json_exit_0`; `test_not_an_object_exit_0`; `test_huge_input_exit_0` (over 1 MB is ignored); `test_unwritable_log_exit_0`.
  - `test_plan_flag_appends_plan_event` (`main(["--plan", "docs/plans/x.md"], ...)` writes `{"event": "plan", "target": "x.md"}`).
  - `test_script_prints_nothing_and_exits_0` runs `scripts/team-event` as a subprocess with `python3 -I`.
- [ ] **Step 2:** Run `test_hook`; expect FAIL.
- [ ] **Step 3:** Implement. Append with one `os.write` of a whole line on a descriptor opened `O_APPEND | O_CREAT`; create the folder if needed; wrap everything in a catch-all that returns quietly.
- [ ] **Step 4:** Run `test_hook` and the whole suite; expect PASS.
- [ ] **Step 5: Commit.**

## Task 7: Register the hooks, bump the version

**Files:**
- Create: `hooks/hooks.json`
- Modify: `.claude-plugin/plugin.json` (`"version": "0.2.0"`), `.claude-plugin/marketplace.json` if it has a version
- Test: `tests/test_hooks_json.py`

**Interfaces:**
- Consumes: event names and the command form from Task 1's findings; `scripts/team-event`.
- Produces: hooks for subagent start, subagent stop, and tool calls before and after, each running `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/team-event"`.

- [ ] **Step 1:** Failing test: `hooks.json` parses; registers the four event names from the findings; every command starts with `python3 -I` and names `team-event`; `plugin.json` version is `0.2.0`; the manifest paths it references exist.
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Write `hooks.json`.
- [ ] **Step 4:** Run the whole suite and `claude plugin validate .` (skip with a note if the command is not installed); expect PASS.
- [ ] **Step 5: Commit.**

## Task 8: Skill, command, docs, and the real run

**Files:**
- Modify: `skills/agent-team/SKILL.md` (step 5; step 0 table row `paths`; step 11), `commands/team-init.md` (add `.claude/team/` to `.gitignore`), `README.md`, `docs/specs/2026-11-17-agent-team-plugin-design.md` (the "No monitor of our own" line points to the live view design)
- Test: `tests/test_skill_text.py`

**Interfaces:**
- Consumes: `team-event --plan <file>`, `team-status --watch`.

- [ ] **Step 1:** Failing test: `SKILL.md` step 5 contains `team-event --plan` and `team-status --watch` and no longer says "so every agent gets a card"; the paths table row mentions `events`; `team-init.md` mentions `.claude/team/`; README mentions `--watch`.
- [ ] **Step 2:** Run `test_skill_text`; expect FAIL.
- [ ] **Step 3:** Edit the four files. Step 5 becomes: run `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/team-event" --plan <plan file>`, tell the owner to run `team-status --watch` in a second terminal (Flightdeck optional), then start the builders.
- [ ] **Step 4:** Run the whole suite; expect PASS.
- [ ] **Step 5: Real run (owner's design section 8).** Install in a scratch git repo, run the two-item `subtract`/`multiply` plan with `team-status --watch` open, and confirm each agent appears, shows what it is doing, and ends `✓`. Paste the screen into the pull request.
- [ ] **Step 6: Commit.**

## Task 9: Card layout for `--watch`

Build after Tasks 3 to 5. The target look is `docs/media/live-view-preview-cards.png`.

**Files:**
- Create: `scripts/team_status/cards.py`
- Modify: `scripts/team_status/config.py` (`model_for`), `scripts/team_status/events.py` (`recent`), `scripts/team_status/cli.py` (choose layout in `--watch`)
- Test: `tests/test_cards.py`, `tests/test_config.py`, `tests/test_events.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `EventLog`, `Row`, `config.events_path`.
- Produces:
  - `config.model_for(cfg: dict, agent: str) -> Optional[str]`: the model name for a core role (`cfg["roles"][agent]` then `cfg["tiers"]["claude-code"]`) or a specialist (its `tier`); `None` for an unknown agent.
  - `events.Event = namedtuple("Event", "ts event agent_id agent item tool target phase ok")`; `EventLog.recent(self, n: int) -> list[Event]` newest first, from the last 50 events kept in memory.
  - `cards.render(rows: list[Row], recent: list[Event], cfg: dict, lead_line: str, waiting: list[str], width: int, color: bool) -> list[str]`: the full card screen. Layout: a lead box (`<Model> · lead`, then `lead_line`), a "Dispatch builders" box, rows of cards (at most 4 per row, equal widths from `width`), an end box `back to lead · verify · open PRs`, the 5 newest `recent` events as a log, and a `WAITING ON YOU` box. Each card has the title `<role> · <Model>`, the item, the state and what it is doing (the same glyphs as the table), and a footer `3m12s   12 calls`. Colour (ANSI) only when `color` is true: tier colours Fable violet, Opus orange, Sonnet blue; running blue, done green, failed red, silent amber.
  - `--watch` uses `cards.render` when the terminal width is 100 columns or more (`shutil.get_terminal_size`), `report.render` otherwise; the width and a `color` flag (stdout is a terminal and `NO_COLOR` is unset) come from `cli.main`, injectable for tests.

- [ ] **Step 1:** Failing tests in `test_cards.py` (rows built by hand, `color=False`, `width=120`): `test_card_title_has_role_and_model` (`builder · sonnet` per the fixture config tiers); `test_four_cards_per_row_then_wrap` (5 rows give 2 card rows); `test_card_shows_state_doing_and_footer`; `test_waiting_box_lists_items`; `test_log_shows_five_newest_first`; `test_narrow_width_never_cuts_a_line` (every output line fits `width`; use `width=100`); `test_unknown_agent_has_no_model_in_title`; `test_color_adds_ansi_only_when_asked`; `test_no_agents_prints_the_no_events_message`. Add `test_model_for_*` to `test_config.py` (core role, specialist, unknown) and `test_recent_returns_newest_first` to `test_events.py`. In `test_cli.py`: `test_watch_uses_cards_when_wide_and_table_when_narrow`.
- [ ] **Step 2:** Run the four modules; expect FAIL.
- [ ] **Step 3:** Implement `model_for`, `Event`/`recent`, `cards.render` and the layout switch. Draw boxes with `┌─┐│└┘`; measure text with `len` after stripping ANSI so colour never breaks alignment; truncate long targets with `…`.
- [ ] **Step 4:** Run the whole suite; expect PASS. Compare a rendered frame with the preview image by eye and note differences in the pull request.
- [ ] **Step 5: Commit.**
