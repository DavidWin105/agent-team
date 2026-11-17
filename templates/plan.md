---
title: <plan title>
status: Draft
lead: <session title> (<session id>), <YYYY-MM-DD>
date: <YYYY-MM-DD>
---

# <plan title>

What this plan delivers, in two or three sentences, and what it does not.

## How the plan runs

1. The lead checks for another lead (the `lead:` line above, worktrees, branches, open pull requests) and stops if it finds one.
2. One builder per item, in parallel, each in its own worktree; item file sets must not overlap.
3. The lead runs every check in `.claude/team.json` itself, then the reviewers per item.
4. One doc-recorder adds the documents to each branch in turn.
5. One pull request per item. The owner merges.

## Item A: <name>

**What exists.** <the code and documents this item starts from, with file paths>

**Build.** <what changes, in plain steps>

**File set.** <every file this item may touch; no file appears in two items>

**Tests.** <the behaviours the tests must show, including the failure cases>

**Questions.** <questions for the owner, or none; the answers go under "Answers" below>

## Answers

- **Q1:**

## Change log

- 0.1.0, <YYYY-MM-DD>: first draft by the lead.
