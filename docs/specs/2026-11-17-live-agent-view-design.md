# Live agent view - design

Status: Draft, waiting for the owner's approval.
Builds on `2026-11-17-agent-team-plugin-design.md`. That document says "No monitor of our own. Flightdeck covers live sessions." This design reverses that line for the live view; Flightdeck stays optional.

## 1. Intent and why

The owner wants to see each agent's progress live, without asking the lead. Today a subagent reports only when it finishes, and `/team-status` is a snapshot of plans, worktrees and pull requests. Nothing shows what a builder or reviewer is doing while it works.

## 2. Goals

1. While a plan runs, one terminal window shows every team agent: its plan item, its role, what it is doing now, how long it has run, how many tool calls it has made, and whether it is running, finished or failed.
2. It also shows what is waiting on the owner (the same list `team-status` already builds).
3. It works without any agent choosing to report. The record comes from Claude Code hooks, so a forgetful or misbehaving agent cannot hide.
4. It works from any terminal on the same machine and keeps working across sessions, because it reads plain files.
5. Python 3.9+ standard library only, like `team-status`.

## 3. Non-goals and anti-goals

- No mod, no pane inside the session, no copy of Flightdeck's cost, context or permission-gate panels.
- No viewing from another machine or a phone in this version.
- No control: the viewer is read-only. It never starts, stops or messages an agent.
- Anti-goal: recording secrets. The log holds tool names and file paths, never file contents, command text beyond its first word, or tool output.
- Anti-goal: slowing or breaking agents. A hook that fails, times out or finds no config must exit 0 and change nothing.
- Anti-goal: a log that looks complete when it is not. The viewer must say when it has seen no events, or when events stopped arriving.

## 4. Constraints

- Hooks run in every project where the plugin is installed. They must do nothing unless `.claude/team.json` exists in the project.
- The log lives in the project, not the plugin folder, and is never committed (see section 7).
- Claude Code's hook events and their JSON fields can change between releases. The builder's first step is to confirm, in the installed Claude Code, which events fire for subagents and which fields name the agent and its type (see section 9).

## 5. Approaches considered

| | How | Trade-off |
|---|---|---|
| A. Agents self-report | Each agent runs a `team-event` command at each step | Simple, but works only when the agent remembers. Agents skip steps. |
| **B. Hooks record events (chosen)** | Plugin hooks append to an event log on agent start/stop and on tool calls; a viewer reads it | Does not depend on agent behaviour; shows real activity; plain files and Python. Depends on Claude Code hook events, which are steadier than the mod API. |
| C. Our own mod | A pane inside the session, like Flightdeck | Best looking, but largest build, tied to an early-access API, one session only, duplicates Flightdeck. |

The owner chose B.

## 6. Design

### 6.1 Event log

File: `paths.events` in `team.json`, default `.claude/team/events.jsonl`. One JSON object per line, appended; never rewritten.

| Field | Meaning |
|---|---|
| `ts` | UTC time, ISO 8601, to the second |
| `event` | `start`, `tool`, `stop` |
| `agent_id` | Claude Code's id for the agent run, when the hook input has one |
| `agent` | role name without the `agent-team:` prefix (`builder`, `code-reviewer`, ...); a specialist uses its name |
| `item` | the plan item, taken from the worktree folder name `.claude/worktrees/<slug>` in the hook's working directory; empty when the agent is not in a worktree |
| `tool` | tool name (`Edit`, `Bash`, `Read`, ...); `tool` events only |
| `target` | for `Edit`, `Write`, `Read`: the file path relative to the project; for `Bash`: the first word of the command only; otherwise empty |
| `ok` | `stop` events: true unless Claude Code reports a failure |

Only agents of the team are recorded: type starts with `agent-team:`, or equals a `specialists[].agent` in `team.json`. Anything else, including the lead's own tool calls, is ignored. The lead appears in the viewer as one row built from the session, only if the hooks give a clear way to know it; otherwise the lead is left out and the design says so (builder's call, section 9).

### 6.2 Hooks

A new `hooks/hooks.json` in the plugin registers three hooks that call one script, `scripts/team-event`:

- agent start -> `start` event
- before or after each tool call by an agent -> `tool` event
- agent stop -> `stop` event

The script reads the hook JSON from stdin, finds the project from the hook's working directory, loads `team.json` (skipping silently if absent or invalid), applies the filters in 6.1, and appends one line. It always exits 0 and writes nothing to stdout. Appends use one `write` of a whole line so two agents writing at once cannot interleave a line.

### 6.3 Viewer

`team-status --watch [project-dir]`. It reuses the existing report and adds an AGENTS section at the top, redrawn about once a second with plain terminal clearing, no curses. Stops on Ctrl+C.

```
agent-team  plan: calc-ops          14:02:11
AGENTS
  subtract  builder        ▶ Edit test_calc_sub.py       3m12s  12 calls
  multiply  builder        ✓ done                        5m01s  21 calls
  multiply  code-reviewer  ▶ Read mul.py                 0m48s   6 calls
WAITING ON OWNER
  merge PR for multiply
```

Rules for the AGENTS section:

- One row per `agent_id` (or per `agent` + `item` when there is no id).
- State: `▶` running (last event is `start` or `tool`), `✓` finished, `✗` failed (`ok` false), `?` no event for 5 minutes while still marked running ("silent").
- "Doing now": the latest `tool` event's tool and target.
- Time is from the first event to the last event (running agents: to now).
- No events in the log, or no log: print "no agent events recorded yet" and name the log path. Never print an empty table that looks like "nothing is running".
- A line that does not parse is counted and shown as "N lines not read", never guessed.
- Rows older than the latest plan run are dropped: the viewer shows runs since the log's most recent `start` that follows a 30-minute gap (builder's call on the exact rule, section 9).

`team-status` without `--watch` prints the AGENTS section once, in the same place, so the snapshot and the live view agree.

### 6.4 Plugin changes

- `hooks/hooks.json` and `scripts/team-event` (new).
- `scripts/team_status/events.py` (new) reads and folds the log into rows; `report.py` and `cli.py` gain the AGENTS section and `--watch`.
- `templates/team.json` gains `paths.events`; `config.py` validates it (optional, with the default).
- `skills/agent-team/SKILL.md` step 5: "Open Flightdeck" becomes "Tell the owner to run `team-status --watch` in a second terminal; Flightdeck is optional". Step 0 and `/team-status` mention `--watch`.
- `README.md`: install and use notes.
- `docs/specs/2026-11-17-agent-team-plugin-design.md`: the "No monitor of our own" line is updated to point here.

## 7. The log is never committed

`/team-init` appends `.claude/team/` to the project's `.gitignore` if it is not already there, and tells the owner. A project without `/team-init` gets the log anyway; `team-status` warns when the log is inside the work tree and not ignored.

## 8. Testing

- `team-event`: unit tests with sample hook JSON on stdin for each event: no `team.json` (writes nothing), non-team agent (writes nothing), each of start/tool/stop, a worktree cwd (item filled), a non-worktree cwd (item empty), `Bash` (only first word kept), secrets in the command (not in the log), invalid JSON on stdin (exit 0, nothing written), unwritable log path (exit 0).
- `events.py`: fixture logs for running, finished, failed, silent, missing log, empty log, a broken line, two agents interleaved, and an old run followed by a new one.
- `--watch`: run with a short loop count so a test can read two frames; a test appends an event between frames and sees the row change.
- Each test is seen failing before the code that passes it, as in the first design.
- Manual: install in a scratch repo, run the two-item plan from the first design's section 10 with `--watch` open in a second terminal, and check each agent appears and finishes.

## 9. Left to the builder (marked as calls to check)

1. **First step, before any code:** in the installed Claude Code, find which hook events fire for subagents (start and stop), and which JSON fields give the agent id and type. If subagent start/stop hooks do not exist or lack an agent type, stop and report; the design then falls back to approach A for those events, and the owner decides.
2. Whether `tool` events come from before or after the tool call (after gives `ok`; before shows what is running now).
3. The exact rule for "the current run" (default: events since the last 30-minute gap).
4. Whether the lead gets a row (see 6.1).
5. Column widths and wrapping for narrow terminals.
6. How `/team-init` edits `.gitignore` when the file does not exist.

## 10. Calls made after the review (mine, for the owner to check)

A reviewer read this design cold and asked nine questions. Answers already in the project or settled as small calls:

- **Specialists:** `config.py` already validates `specialists[].agent`, `tier` and `when`, so the team-agent filter in 6.1 uses that field. The template's list is empty, so by default only `agent-team:*` agents are recorded.
- **Where the log goes:** always the main checkout's `paths.events`, never a worktree's. `team-event` finds the main checkout by walking up from the hook's folder to the folder that holds `.claude/team.json` and, when the path contains `.claude/worktrees/<slug>`, taking the part before `.claude/worktrees`. The viewer then reads one file from the project folder. Worktrees are created under `.claude/worktrees/<slug>` by step 5 of `SKILL.md`.
- **Tool events:** the hook is registered both before and after the tool call. Before gives "doing now" during a long command; after gives `ok`. `tool` events therefore carry an optional `ok`, and `silent` (5 minutes with no event) only counts agents whose last event is not a still-open tool call.
- **Current run:** the 30-minute gap rule is replaced by a marker. The lead's step 5 appends one `plan` event (`ts`, plan file name) when it starts the builders, by running `team-event --plan <file>`. The viewer shows events since the last `plan` event. If there is none, it shows everything and says so. A long wait can no longer hide a running agent.
- **Row identity:** `agent_id` when the hook gives one. Without it, `agent` + `item`; two agents sharing both merge into one row, and the viewer says "2 agents share this row" rather than hiding it.
- **Hook registration:** `hooks/hooks.json` at the default location, commands run `python3 -I`. The plugin version goes to 0.2.0 in `plugin.json` and `marketplace.json`.
- **Ignored-log warning:** a one-time line when the viewer starts, using `git check-ignore`, only inside a git repository. `/team-init` is a prompt, so its `.gitignore` step is checked by the manual run only; `team-status` carries the tested warning.
- **Log growth:** the viewer remembers the file offset and reads only new lines each frame, folding them into the rows it already holds. No pruning in this version; a long-lived log is listed under risks.

## 11. Held for the owner

- **If hooks cannot tell which agent is acting** (no subagent start/stop events, or tool-call hooks that do not name the agent), what should happen? My proposal: the plan puts a short spike first that checks the hooks in the installed Claude Code. The hook-independent parts (`events.py`, the viewer, `--watch`) are built first, and the hooks last. If the spike shows agents cannot be told apart, work stops and you choose: tool events only with no per-agent rows, or agent self-reporting (approach A) for start and stop.

## 12. Risks

- Hook event names and fields may change between Claude Code releases. The first step above and a `claude plugin validate` run catch structure, not behaviour; the manual run in section 8 is the real check.
- Read-only reviewers may run in the lead's folder, not a worktree, so their `item` can be empty. The viewer shows them by role with no item rather than guessing.
- A hook adds a little time to every team tool call. The script does one small append and nothing else.
- The log grows without bound. At roughly 150 bytes per event it stays small for a long time; pruning is a later change.
