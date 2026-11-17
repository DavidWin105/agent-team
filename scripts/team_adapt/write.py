"""Write team-adapt's output into a project, all or nothing (spec sections 6 and 10)."""
import os

from team_adapt import marker

START = "<!-- agent-team:start -->"
END = "<!-- agent-team:end -->"


def with_block(text, block):
    """Answer text with the agent-team block replaced, or appended if absent."""
    start, end = text.find(START), text.find(END)
    full = START + "\n" + block + END
    if start != -1 and end > start:
        return text[:start] + full + text[end + len(END):]
    if start != -1 and end != -1:
        raise ValueError("has the agent-team markers out of order")
    if start != -1 or end != -1:
        raise ValueError("has only one of the agent-team markers")
    gap = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
    return text + gap + full + "\n"


def _read(path):
    """Answer the file's text, or None when it does not exist; raise OSError or UnicodeDecodeError otherwise."""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return None


def _outside(project_dir, rel):
    """True when rel resolves (through any symlink) to somewhere outside the project."""
    real = os.path.realpath(os.path.join(project_dir, rel))
    return not real.startswith(os.path.realpath(project_dir) + os.sep)


def plan_changes(project_dir, files, blocks, generated_dirs):
    """Answer (writes, deletes, problems) without touching the disk."""
    writes, problems = {}, []
    for rel, text in sorted(files.items()):
        if _outside(project_dir, rel):
            problems.append("%s is outside the project" % rel)
            continue
        try:
            current = _read(os.path.join(project_dir, rel))
        except (OSError, UnicodeDecodeError):
            problems.append("%s cannot be read" % rel)
            continue
        if current is not None and not marker.is_generated(current):
            problems.append("%s exists and was not written by team-adapt" % rel)
        writes[rel] = text
    for rel, block in sorted(blocks.items()):
        if _outside(project_dir, rel):
            problems.append("%s is outside the project" % rel)
            continue
        try:
            writes[rel] = with_block(_read(os.path.join(project_dir, rel)) or "", block)
        except (OSError, UnicodeDecodeError):
            problems.append("%s cannot be read" % rel)
        except ValueError as error:
            problems.append("%s %s" % (rel, error))
    deletes = []
    for rel in _generated_files(project_dir, generated_dirs):
        if rel in files:
            continue
        if _outside(project_dir, rel):
            problems.append("%s is outside the project" % rel)
        else:
            deletes.append(rel)
    return writes, deletes, problems


def _generated_files(project_dir, generated_dirs):
    found = []
    for rel_dir in generated_dirs:
        folder = os.path.join(project_dir, rel_dir)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            rel = os.path.join(rel_dir, name)
            path = os.path.join(project_dir, rel)
            if not os.path.isfile(path):
                continue
            try:
                text = _read(path)
            except (OSError, UnicodeDecodeError):
                continue
            if text is not None and marker.is_generated(text):
                found.append(rel)
    return found


def apply(project_dir, writes, deletes):
    for rel, text in sorted(writes.items()):
        path = os.path.join(project_dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    for rel in deletes:
        os.remove(os.path.join(project_dir, rel))
