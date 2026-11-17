"""team-adapt: write each tool's agent-team files into a project (multi-tool adapters spec)."""
import argparse
import os
import sys

from team_adapt import claude, init, project, write
from team_status import config

CURSOR_READS_CODEX = (
    "warning: Cursor also reads .codex/agents/ and may load agents with Codex model names; "
    "check which agent Cursor starts"
)


def main(argv, out=sys.stdout, err=sys.stderr, ask=input):
    parser = argparse.ArgumentParser(prog="team-adapt", description="Write Codex, Cursor and Gemini agent-team files.")
    parser.add_argument("project", nargs="?", default=".", help="project folder (default: current folder)")
    parser.add_argument("--plugin", action="store_true", help="regenerate this plugin's own Claude Code files")
    parser.add_argument("--init", action="store_true", help="ask for tools and models, write .claude/team.json, then adapt")
    args = parser.parse_args(argv)
    if args.plugin:
        for rel in claude.write_plugin_files():
            print("wrote %s" % rel, file=out)
        return 0
    project_dir = os.path.abspath(args.project)
    if args.init:
        try:
            init.run_init(project_dir, ask=ask, out=lambda line: print(line, file=out))
        except (EOFError, KeyboardInterrupt):
            print("stopped: no answer, nothing written", file=err)
            return 1
    return adapt(project_dir, out, err)


def adapt(project_dir, out, err):
    cfg, problems = config.load_config(project_dir)
    if problems:
        for problem in problems:
            print("team.json: %s" % problem, file=err)
        return 1
    files, blocks = project.project_outputs(cfg)
    writes, deletes, problems = write.plan_changes(project_dir, files, blocks, project.GENERATED_DIRS, project.INSTRUCTION_FILES)
    if problems:
        for problem in problems:
            print(problem, file=err)
        print("nothing written", file=err)
        return 1
    if not writes and not deletes:
        print("nothing to write: no codex, cursor or gemini block under tiers", file=out)
        return 0
    try:
        write.apply(project_dir, writes, deletes)
    except OSError as error:
        print("stopped while writing, some files may be written: %s" % error, file=err)
        return 1
    for rel in sorted(writes):
        print("wrote %s" % rel, file=out)
    for rel in deletes:
        print("deleted %s" % rel, file=out)
    if "codex" in cfg["tiers"] and "cursor" in cfg["tiers"]:
        print(CURSOR_READS_CODEX, file=err)
    return 0
