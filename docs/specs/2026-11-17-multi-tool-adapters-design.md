---
title: agent-team multi-tool adapters, design
date: 2026-11-17
status: Draft, for Win's review
owner: Win
---

# agent-team multi-tool adapters: design

## 1. Goal

Let the agent-team workflow run natively inside Codex CLI, Cursor and Gemini CLI, as it runs inside Claude Code today. Every role is written once in a tool-neutral form. A generator writes each tool's own files, with the models the owner declared for that tool in `.claude/team.json`.

This is the adapter that section 2, decision 5 of `docs/specs/2026-11-17-agent-team-plugin-design.md` left room for.

## 2. Decisions taken in the design conversation (2026-11-17)

1. **Native per tool.** The whole team (the lead and every agent) runs inside one tool at a time. Agents in different tools never mix in one plan.
2. **First tools:** Codex CLI, Cursor and Gemini CLI. Claude Code keeps working as now.
3. **Owner-declared models.** The owner says which model fills each tier for each tool, and `/team-init` (or `team-adapt --init`) asks. Nothing is auto-detected.
4. **Approach A:** one neutral source plus a generator. The rejected options were a hand-written copy of every agent per tool (it drifts) and a lead-only instruction file (it needs a model choice at start time, which these tools do not reliably offer; see section 4).

## 3. Non-goals (this version)

- **Cross-tool teams**, for example a Claude lead starting a Codex reviewer. That needs its own spec.
- **The live agent view for Codex, Cursor and Gemini.** Their hook payloads differ, and Gemini has no subagent start or stop events. `team-status` still shows plans, worktrees, pull requests and the routing log in every tool. Live-view adapters need their own spec.
- **Native plugin or extension packages for the new tools.** Codex plugins cannot carry agents, and Cursor's public marketplace is reviewed. This version writes files straight into the project.
- **Checking that a declared model name exists.**
- **Generating a project's specialist agents.**

## 4. What the official docs say (researched 2026-11-17)

Only official docs were used. Codex docs at developers.openai.com/codex redirect to learn.chatgpt.com/docs.

| | Codex CLI | Cursor | Gemini CLI |
|---|---|---|---|
| Agent files | TOML in `.codex/agents/`: `name`, `description`, `developer_instructions`, optional `model`; no tools field | Markdown and frontmatter in `.cursor/agents/`: `name`, `description`, `model`, `readonly`; no tools field; also reads `.claude/agents/` and `.codex/agents/` | Markdown and frontmatter in `.gemini/agents/`: `name`, `description`, `tools`, `model`; the body is the system prompt |
| Model at start time | A model set in the file beats one chosen at start | Not documented | `/model` and `--model` do not override a subagent's model |
| Skills | `.agents/skills/<name>/SKILL.md` | `.agents/skills/` (also `.cursor/skills/`) | `.agents/skills/` (also `.gemini/skills/`) |
| Instructions | `AGENTS.md` | `AGENTS.md` or `.cursor/rules/*.mdc` | `GEMINI.md` (configurable) |
| Subagent hooks | SubagentStart and SubagentStop | subagentStart and subagentStop | none |

Two consequences shape this design:

- `.agents/skills/` is read by all three tools, so one generated lead skill serves them all.
- The model is fixed in each agent file, so the lead cannot change it when it starts an agent. Tier moves (section 7) therefore pick between generated per-tier files.

Not verified, because the docs do not say: whether Gemini starts subagents in parallel, Cursor's custom command format, and Codex model names. None of these changes the design.

Sources:
- learn.chatgpt.com/docs/agent-configuration/subagents
- learn.chatgpt.com/docs/build-skills
- learn.chatgpt.com/docs/hooks
- cursor.com/docs/subagents
- cursor.com/docs/skills
- cursor.com/docs/hooks
- github.com/google-gemini/gemini-cli docs: `core/subagents.md`, `cli/skills.md`, `cli/gemini-md.md` and `hooks/index.md`

## 5. Layout

```
agent-team/
├── roles/                       NEW, the tool-neutral source of truth
│   ├── builder.md
│   ├── code-reviewer.md
│   ├── security-reviewer.md
│   ├── plan-reviewer.md
│   ├── doc-recorder.md
│   └── lead.md                  the SKILL.md workflow, with tool-specific lines as placeholders
├── scripts/team-adapt           NEW, the entry point; Python 3.9+, standard library only
├── scripts/team_adapt/          NEW, one module per tool: claude.py, codex.py, cursor.py, gemini.py
├── agents/                      GENERATED for Claude Code, committed
├── skills/agent-team/SKILL.md   GENERATED for Claude Code, committed
└── rules.md, templates/, scripts/team-status   unchanged
```

### 5.1 Role source format

Each `roles/<role>.md` file has frontmatter and a body.

The frontmatter holds:
- `name`
- `description`
- `read-only` (true or false)
- `tools`, as neutral names: `read`, `edit`, `write`, `shell`, `search`

The body is today's agent text. Wherever the text needs something tool-specific, it uses a placeholder instead:
- `{{plugin_root}}`
- `{{config_path}}`
- `{{start_agent role tier}}`

Each tool module fills these in. It also maps the neutral tool names to its tool's own names, or drops them where the tool has no tools field.

### 5.2 Generated-file marker

Every generated file starts with a marker line in the comment syntax its format allows:

> Generated by agent-team team-adapt from roles/<role>.md. Do not edit; edit the source and rerun team-adapt.

`team-adapt` overwrites or deletes only files that carry this marker.

## 6. Per-tool outputs

The generator writes the Claude Code output into this repository, where it is committed. The installed plugin needs those files, and they must stay identical to what Claude Code uses today.

It writes the output for every other tool into the project, as `team-adapt <project-dir>`, for each tool named under `tiers`. The project commits these files.

| | Codex | Cursor | Gemini |
|---|---|---|---|
| Agents | `.codex/agents/<role>-<tier>.toml`: `name`, `description`, `developer_instructions`, `model` | `.cursor/agents/<role>-<tier>.md`: `name`, `description`, `model`; `readonly: true` for reviewers | `.gemini/agents/<role>-<tier>.md`: `name`, `description`, `model`, `tools`; reviewers get no edit or write tools |
| Lead skill | `.agents/skills/agent-team/SKILL.md`, plus `rules.md` and the templates beside it (shared by all three tools) | same | same |
| Instructions | A marked block in `AGENTS.md` that points to the skill | same block in `AGENTS.md` | same block in `GEMINI.md` |
| Read-only enforcement | The role's instructions, plus the lead's existing `git status` check after each reviewer | `readonly`, plus the same check | the `tools` list, plus the same check |

**Instruction files.** The marked block sits between `<!-- agent-team:start -->` and `<!-- agent-team:end -->`. `team-adapt` replaces only that block, and appends it if it is missing. Text outside the block is never changed.

**Worktrees.** No change. The lead already runs `git worktree add` itself, and that works in any tool.

## 7. Model choice in tools with fixed-model agent files

Each role gets one agent file per tier it can reach: its own tier from `roles`, and every tier above it. For example, a builder on `standard` gets `builder-standard`, `builder-strong` and `builder-strongest`.

The lead resolves a tier with the rules in `rules.md` ("Model choice"), which are unchanged. It then starts the agent named `<role>-<resolved tier>`.

In Claude Code, the lead keeps passing the model when it starts the agent, and the Claude agent names stay unchanged.

## 8. `team.json` changes

- **Tool keys.** Under `tiers`, the allowed keys are `claude-code`, `codex`, `cursor` and `gemini`. Any other key is an error. `version` stays 1, so existing files stay valid.
- **All four tiers.** Every tool block names all four tiers: `strongest`, `strong`, `standard` and `fast`. A tier move can reach any of them. An owner with fewer models repeats a name.
- **Validation.** `team-status` and `team-adapt` validate every tool block, not only `claude-code`.
- **Specialists.** The lead starts a specialist by its name in the tool's own agent folder, on whatever model its file sets. Tier moves do not apply to specialists. The "team.json fields" table in the lead skill says so.

Example:

```json
"tiers": {
  "claude-code": { "strongest": "fable", "strong": "opus", "standard": "sonnet", "fast": "haiku" },
  "cursor": { "strongest": "<model id>", "strong": "<model id>", "standard": "<model id>", "fast": "<model id>" }
}
```

## 9. Setup

`/team-init` (in Claude Code) and `python3 -I <path-to>/agent-team/scripts/team-adapt --init <project-dir>` (in any terminal) ask the same questions:

1. Which tools do you use? The answer may name several.
2. For each tool, which model fills each of the four tiers?
3. Owner, checks and paths, as today.

Each then writes `.claude/team.json` and runs `team-adapt`. After the owner changes models, they rerun `team-adapt <project-dir>`.

## 10. Errors

In every error case, `team-adapt` writes nothing at all, never a partial set.

- **Invalid `team.json`:** names the field and exits 1.
- **Target file without the marker:** lists every such file and exits 1.
- **Tool or tier removed from `team.json`:** deletes only stale files that carry the marker, prints each path it deleted, and exits 0.
- **Codex and Cursor both configured:** prints a warning that Cursor also reads `.codex/agents/` and may load agents with Codex model IDs, then exits 0.

## 11. Testing

All tests use standard-library `unittest`. Each test is seen failing before the code that passes it.

- **Golden output per tool module.** A small fixture `team.json` and the roles produce exactly the expected files.
- **Drift test.** The committed `agents/` and `skills/agent-team/SKILL.md` equal the generator's Claude Code output.
- **Marker refusal.**
- **Marked-block rewrite.** Text outside the block in `AGENTS.md` and `GEMINI.md` is unchanged.
- **Tier variants.** Each role gets exactly the variants it can reach.
- **Stale-file deletion.** Only marked files are deleted.
- **All-or-nothing on error.**
- **Validation.** Unknown tool keys and missing tiers are rejected.
- **Manual check.** In a scratch repository in each of Codex, Cursor and Gemini, run one two-item plan from plan to pull request, and record the runs in its routing log. Until a tool has been run, the README says "not yet run" for it.

## 12. Risks

- **Cursor reads `.codex/agents/`.** In a project with both tools configured, Cursor may load Codex variants. Which file wins when names clash is not documented. The section 10 warning and the manual check cover it.
- **Formats may change.** These agent formats are young, and each tool may change them. The golden tests catch generator changes, not changes in the tools themselves.
- **Codex has no tools field.** Its read-only roles rely on instructions and the lead's `git status` check.
- **Wrong model names fail late.** A wrong model name fails only when the agent starts, as today.
- **Generated Claude files.** The Claude agents become generated files. Someone could edit `agents/` by hand, but the drift test fails on that.
