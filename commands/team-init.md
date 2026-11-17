---
description: Create .claude/team.json for this project from the agent-team template, asking the owner for the values that differ.
allowed-tools: Read, Write, Bash(python3:*), Bash(ls:*)
---

Create `.claude/team.json` for this project.

1. If `.claude/team.json` already exists, show it and ask the owner whether to replace it. Do nothing else without a clear yes.
2. Read the template at `${CLAUDE_PLUGIN_ROOT}/templates/team.json`.
3. Look at the project (its package files, its agent instructions, an existing plans folder) and propose, in one message: the owner's name; the `checks` (lint, type-check, tests, any other check its instructions require); `paths.plans`, `paths.plan-glob` and `paths.routing-log`; any specialist agents already in `.claude/agents/` with a suggested tier and `when`.
4. Wait for the owner's answer. Write only the values the owner confirmed into a copy of the template; keep the template's tiers, roles, rules and `owner-only` unless the owner changes them.
5. Write `.claude/team.json`, then run:

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/team-status" "$PWD"
```

6. Show the output. If it reports a config problem, fix only that field with the owner and run it again.
