# agent-team

A Claude Code plugin: an AI agent team with a model per role, one workflow from plan to pull request, steps only the owner may take, and a `team-status` command for the terminal.

The design is `docs/specs/2026-11-17-agent-team-plugin-design.md`.

## Install (once per machine)

In Claude Code:

```
/plugin marketplace add DavidWin105/agent-team
/plugin install agent-team@agent-team-local
```

## Use in a project

1. `/team-init` writes `.claude/team.json`.
2. Ask the lead to plan a task; approve the plan; ask it to run the plan.
3. `/team-status`, or from a clone of this repository in any terminal: `python3 -I agent-team/scripts/team-status <project-dir>`.
4. With [claude-flightdeck](https://github.com/scasella/claude-flightdeck) installed, `/flightdeck` shows one session's agents live.

## Tests

```bash
cd tests && PYTHONPATH=../scripts python3 -m unittest discover -v
```

## License

MIT. See `LICENSE`.
