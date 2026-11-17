"""Read plan files: front matter status and lead, and unanswered questions (spec section 9)."""
import glob
import os
import re
from collections import namedtuple

Plan = namedtuple("Plan", "name status lead unanswered problem")
ANSWERS_HEADING = "## Answers"
# An unanswered question: "- **A1:**" with nothing after the bold label.
QUESTION = re.compile(r"^- \*\*[^*]+:\*\*\s*$")


def read_plans(project_dir, paths):
    """Answer every plan matching paths.plans + paths.plan-glob, sorted by file name.

    The routing log often sits in the plans folder and matches the glob; it is not a plan.
    """
    pattern = os.path.join(project_dir, paths["plans"], paths["plan-glob"])
    routing_log = os.path.normpath(os.path.join(project_dir, paths["routing-log"]))
    return [read_plan(path) for path in sorted(glob.glob(pattern)) if os.path.isfile(path) and os.path.normpath(path) != routing_log]


def read_plan(path):
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return Plan(name, None, None, 0, "cannot be read")
    front = _front_matter(lines)
    if front is None:
        return Plan(name, None, None, 0, "no front matter")
    return Plan(name, front.get("status"), front.get("lead"), _unanswered(lines), None)


def first_word(text):
    """Answer the first word of a status such as 'Done 2026-11-17 (...)'."""
    words = text.split() if text else []
    return words[0] if words else "(none)"


def _front_matter(lines):
    if not lines or lines[0].strip() != "---":
        return None
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            pairs = (line.split(":", 1) for line in lines[1:end] if ":" in line)
            return {key.strip(): value.strip() for key, value in pairs}
    return None


def _unanswered(lines):
    count = 0
    inside = False
    for line in lines:
        if line.startswith("## "):
            inside = line.strip() == ANSWERS_HEADING
        elif inside and QUESTION.match(line):
            count += 1
    return count
