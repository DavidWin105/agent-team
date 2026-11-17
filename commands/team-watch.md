---
description: Print the exact command that shows the agent team live (team-status --watch), ready to paste into a second terminal.
allowed-tools: Bash(printf:*)
---

The live view redraws every second until Ctrl+C, so it cannot run inside this session. Print the command for the user to run in a second terminal.

Run this from the project folder and show its output to the user unchanged:

```bash
printf '%s\n' "python3 -I \"${CLAUDE_PLUGIN_ROOT}/scripts/team-status\" --watch \"$PWD\""
```

Then tell the user, in one or two lines: open a second terminal, paste that line, and press Ctrl+C to stop; on a terminal 100 columns wide or more it draws cards, otherwise a table. Do not run `--watch` yourself. Change no file.
