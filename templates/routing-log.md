# Agent routing log

What each agent run cost and found, so the model routing is decided on data instead of guesses. The lead adds the rows when a plan's last pull request is open: one row per builder, reviewer or recorder run. The owner decides when there are enough rows to change the routing.

## How to fill a row

- **Tokens, tool calls, minutes:** from the agent's completion notice. Leave a cell blank when the notice was not seen; never estimate.
- **Findings:** HIGH / MEDIUM / LOW counts as the agent reported them. Builders and recorders write `-`.
- **Kept:** how many of those findings the lead checked and acted on.
- **Rework:** for a builder, the number of fix rounds after review, and `up` if it was rerun one tier up. For a reviewer, `-`.
- **Notes:** a finding only this run caught, or one that turned out wrong. One line, with no `|` character.

## Rows

| Date | Plan, item | Role | Agent | Model | Tokens | Tool calls | Minutes | Findings H/M/L | Kept | Rework | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
