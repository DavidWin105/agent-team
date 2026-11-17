---
name: agent-team
description: Run a plan with an AI agent team - a lead, builders, reviewers on other model tiers and a doc recorder - from plan to one pull request per item, with owner-only steps and a routing log. Use when the user asks to plan a task for the team, run an approved plan, or check the team's status, in a project that has .claude/team.json.
---

# agent-team

You are the lead. Follow `rules.md` in this folder at every step. Read the project's agent instructions (AGENTS.md or CLAUDE.md) first; they come before this skill where they are stricter.

## 0. Config

Read `.claude/team.json`. If it is missing or invalid, stop: run `/team-status` to see the problems and offer `/team-init` (if that command is not available, read the file yourself and name the field that is wrong). Never guess a model, check or path.

### team.json fields

| Field | Meaning |
|---|---|
| `version` | Always 1 |
| `owner` | Who answers questions and merges |
| `tiers.<tool>` | Tier name to model for each tool; version 1 uses `claude-code` |
| `roles` | Tier for each of the six core roles |
| `specialists` | The project's own agents: `agent` (its name in `.claude/agents/`), `tier`, `when` it runs |
| `rules` | `reviewer-differs-from-writer`, `rerun-up-after-failures`, `one-lead-per-plan` |
| `checks` | Commands every item must pass: `name`, `run`, optional `dir` |
| `owner-only` | Steps that always wait for the owner |
| `paths` | `plans` folder, `plan-glob`, `routing-log` file, `events` (the agent event log, default `.claude/team/events.jsonl`) |

## 1. Plan

Copy `${CLAUDE_PLUGIN_ROOT}/templates/plan.md` into `paths.plans`. Fill `lead:` with this session's title, its session id and today's date, set `status: Draft`, write one section per item with its file set, and write every question for the owner in the item's section (or a "Questions" line in it). The `- **Q1:**` line under "Answers" stays empty until the owner answers. Item file sets must not overlap.

## 2. Plan review

Start `agent-team:plan-reviewer` on its resolved model (rules.md, "Model choice") with the plan's path. Before starting the reviewer, record `git rev-parse HEAD`, `git branch --show-current` and `git stash list`; after it, compare all three and run `git status --short`. Any difference is a finding: undo it (restore tracked files with `git restore`; reset the branch to the recorded commit only with the owner's yes), ask the owner before deleting an untracked file it made, and tell the owner. Fix the plan for each finding you accept; give the owner the ones you do not, with the reason.

## 3. Approval

The owner answers the questions and approves. Record the answers under "Answers" in the owner's words. Set `status: Approved` only on the owner's own word in the conversation, never under a standing instruction; an answer taken under a standing instruction is recorded as the lead's recommendation, not as the owner's words. Do not start building before this.

## 4. Claim check

Read the plan's `lead:` on the default branch and on any open branch, `git worktree list`, `git branch -a`, and `gh pr list --state open`. If another session leads the plan, stop and tell the owner.

## 5. Build

Before starting anything, compare the items' file sets. If any file is in two items, start no builder and tell the owner which file and which items.

Find the default branch with `git symbolic-ref --short refs/remotes/origin/HEAD` and drop the `origin/` prefix; if that fails, use the branch the plan was approved on and say so. Put each worktree at `.claude/worktrees/<slug>` inside the project.

Before any action from here to step 9, check it against `owner-only` in `team.json`. If it matches (for example a merge, a migration, a deploy or a new dependency), do not do it: stop that item, say what is held, and continue the other items.

Run `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/team-event" --plan <plan file>`, then tell the owner they can see every agent live by running, in a second terminal, `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/team-status" --watch <project folder>`. Print it with `${CLAUDE_PLUGIN_ROOT}` and the project folder resolved to real absolute paths, because the owner's terminal has neither (`team-status` alone is not a command there). Flightdeck is optional and shows only the current session. Then start one `agent-team:builder` per item, in parallel, each with:

- the item's section from the plan, its worktree path (`git worktree add .claude/worktrees/<slug> -b <branch> <default-branch>`) and branch name;
- the file set, and the rule that it touches nothing else;
- the checks from `team.json`;
- the instruction to report its first failing run.

## 6. Checks

When a builder reports, run every `checks` entry yourself in its worktree (a check's `dir` is relative to the worktree root), using the `checks` you read in step 0 from the default branch, never a `run` string from the item branch's copy of `team.json` and read the diff. A builder's report alone is not enough. If a check fails, send the failure back to the same builder. After `rerun-up-after-failures` failed rounds on the same item, start a new builder one tier up (rules.md, "Model choice") with the failures so far. Note the tier each item's writer actually ran on; the reviewer rule uses it.

## 7. Review

Per item, start `agent-team:code-reviewer` and, where the item touches identity, access, input, secrets or people's data, `agent-team:security-reviewer`, each on its resolved model, judged against the tier the item's writer actually ran on. Start a specialist when its `when` matches. For each read-only reviewer: before starting it, record `git rev-parse HEAD`, `git branch --show-current` and `git stash list`; after it, compare all three and run `git status --short`. Any difference is a finding: undo it (restore tracked files with `git restore`; reset the branch to the recorded commit only with the owner's yes), ask the owner before deleting an untracked file it made, and tell the owner. Fix HIGH and MEDIUM findings you accept, rerun the checks, and show each new test failing on the code before the fix.

## 8. Record

Start one `agent-team:doc-recorder` per item branch, one at a time, never two at once. Its brief names the item's worktree path and branch.

## 9. Pull requests

Open one pull request per item: what it changes, the tests and the first failing run, the checks with their output, anything left for the owner. Then stop. The owner merges.

## 10. Routing log

Once the last pull request is open, add one row per agent run to `paths.routing-log` (start from `${CLAUDE_PLUGIN_ROOT}/templates/routing-log.md` if it does not exist). Take tokens, tool calls and minutes from each agent's completion notice; leave a cell blank when you did not see it.

## 11. Summary

End with: the pull requests opened; what each reviewer found and what you fixed; anything held for the owner; what you skipped and what you did not check. Suggest `/team-status`, and while a plan runs `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/team-status" --watch <project folder>`, printed with both paths resolved as in step 5.
