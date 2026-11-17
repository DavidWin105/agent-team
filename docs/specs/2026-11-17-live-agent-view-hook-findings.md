# Live agent view - hook findings

Source: Claude Code hooks reference (https://code.claude.com/docs/en/hooks.md), read by a documentation agent on 2026-11-17.
**Status: documented, NOT observed.** Observing a real hook run could not be done in the build container (launching a nested Claude Code session was refused). The owner's real run (plan Task 8, step 5) is the check. Items marked NOT DOCUMENTED were not in the text read.

## Events

| Need | Event | Fields used |
|---|---|---|
| Agent start | `SubagentStart` | `hook_event_name`, `cwd`, `agent_id`, `agent_type` |
| Agent stop | `SubagentStop` | same, plus `agent_transcript_path`, `last_assistant_message`; no success or failure field |
| Tool about to run | `PreToolUse` | `cwd`, `tool_name`, `tool_input`, `tool_use_id`, `agent_id`, `agent_type` |
| Tool finished ok | `PostToolUse` | same, plus `tool_response`, `duration_ms`; fires only when the tool succeeded |
| Tool failed | `PostToolUseFailure` | same, plus `error`, `is_interrupt`; not fired for permission denials |

- Tool-call events inside a subagent carry `agent_id` and `agent_type` (stated in the Configuration text; not shown in the doc's JSON examples). A call from the lead's own session has no `agent_id`, so it is ignored by the team filter.
- `cwd` is the folder Claude is working in; after it enters a worktree it is the worktree root. For a subagent started with worktree isolation the exact value is NOT DOCUMENTED; the plan's worktree path rule (`.claude/worktrees/<slug>`) matches how the lead creates worktrees by hand.
- Plugin agents: `agent_type` is `<plugin-name>:<agent>`, so this plugin's agents arrive as `agent-team:builder` etc. (the plugin-name prefix is documented; the literal `agent-team:` is that rule applied to this plugin's name).
- No hook field says an agent "failed". `SubagentStop` has no result.

## Plugin hooks file

`hooks/hooks.json` has an optional `description` and a `hooks` object keyed by event name; each event holds `[{ "matcher": "", "hooks": [ { "type": "command", "command": ..., "args": [...], "timeout": <seconds> } ] }]`. `${CLAUDE_PLUGIN_ROOT}` expands to the plugin folder. Exec form (`command` plus `args`) is preferred. Default timeout is 600 seconds; a timed-out PreToolUse hook does not block the tool.

## Rulings that follow (controller, recorded in the SDD ledger)

- R4: register `SubagentStart`, `SubagentStop`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`. `team-event` maps them to `start`, `stop`, `tool`/`pre`, `tool`/`post` ok true, `tool`/`post` ok false.
- R5: hooks cannot report that an agent failed, so `stop` events from hooks carry no `ok` and the row shows `done`. The `failed` state exists in the viewer but is reachable only from a `stop` event with `ok: false`. A tool failure (for example a failing test run) is shown in "doing now" as `Bash (failed)`, not as a failed agent. Left for the owner: let the lead mark an agent failed (a `team-event --failed` call) in a later change.
- R6: use exec form with `"timeout": 5` for every hook.
