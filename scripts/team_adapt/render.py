"""Fill the lead skill for one tool family (spec section 5.1; line tags per plan ruling 4)."""
import re

FAMILIES = ("claude", "other")
LINE_TAG = re.compile(r"^\{\{(claude|other)\}\} ?")
AGENT = re.compile(r"\{\{agent ([a-z-]+)\}\}")
AGENT_NAME = {"claude": "`agent-team:%s`", "other": "`%s-<tier>`"}


def render(text, family, plugin_root):
    """Keep untagged lines and lines tagged for this family, then fill the placeholders."""
    if family not in FAMILIES:
        raise ValueError("unknown family: %s" % family)
    kept = []
    for line in text.split("\n"):
        tag = LINE_TAG.match(line)
        if tag and tag.group(1) != family:
            continue
        kept.append(line[tag.end():] if tag else line)
    out = AGENT.sub(lambda match: AGENT_NAME[family] % match.group(1), "\n".join(kept))
    return out.replace("{{templates}}", plugin_root + "/templates").replace("{{plugin_root}}", plugin_root)
