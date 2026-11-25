"""The sidebar's own part of its Issues view: the latest answer kept for the repository's other sidebars, and what a
tab of its opens: an issue (gh's preview with its comments, a new issue, a comment), a pull request's review."""
import hashlib
import json
import os
import shutil
import time
from dataclasses import asdict

import preview
import statefile
from github import Issue, Listing
from pulls import MARKS, REVIEW
from screen import truncate


def shared_path(state_dir, repo, query):
    """Where the latest answer to QUERY about REPO waits for every sidebar of the repository, in the state folder."""
    key = hashlib.sha256(json.dumps([repo, asdict(query)], sort_keys=True).encode()).hexdigest()[:16]
    return os.path.join(state_dir, f"issues-{key}.json")


def keep(state_dir, repo, query, listing):
    """LISTING, the answer to QUERY about REPO just got, for the repository's other sidebars; when it cannot be
    written, each of them asks GitHub on its own. Never into a state folder that is gone (herdr-fold removed)."""
    if not os.path.isdir(state_dir):
        return
    try:
        statefile.write(shared_path(state_dir, repo, query),
                        {"at": time.time(), "issues": [asdict(issue) for issue in listing.issues],
                         "error": listing.error})
    except OSError:
        pass


def kept(state_dir, repo, query, fresh):
    """The answer to QUERY about REPO a sidebar kept less than FRESH seconds ago; None without one, or with one not as
    keep() writes it (another version's, or edited by hand): GitHub is asked instead."""
    try:
        with open(shared_path(state_dir, repo, query), encoding="utf-8") as f:
            data = json.load(f)
        if not 0 <= time.time() - float(data["at"]) < fresh:
            return None
        found, error = tuple(kept_issue(row) for row in data["issues"]), data["error"]
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None
    return Listing(found, error) if error is None or isinstance(error, str) else None


TEXTS, NAMES = ("title", "updated", "state", "url", "priority"), ("labels", "assignees")     # an Issue's, as kept


def kept_issue(row):
    """The issue ROW is, as keep() writes one; ValueError for anything else."""
    if (not isinstance(row, dict) or set(row) != {"number", *TEXTS, *NAMES} or type(row["number"]) is not int
            or not all(isinstance(row[name], str) for name in TEXTS)
            or not all(isinstance(row[name], list) and all(isinstance(item, str) for item in row[name])
                       for name in NAMES)):
        raise ValueError("not an issue as kept")
    return Issue(**{**row, "labels": tuple(row["labels"]), "assignees": tuple(row["assignees"])})


TAB_TITLE = 20                  # cells of an issue's title in its preview tab's name: herdr's tab row fits several

def view_spec(repo, issue):
    """The preview of ISSUE: gh's own view, with its comments, laid out as in a terminal; its tab named with the number
    and the start of the title (TAB_TITLE cells)."""
    binary = shutil.which("gh") or "gh"
    return {"title": f"#{issue.number} {truncate(issue.title, TAB_TITLE)}", "line": None, "file": None,
            "pipeline": [[binary, "issue", "view", str(issue.number), "-R", repo, "--comments"]],
            "env": {"GH_FORCE_TTY": "100", "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1"}}


def printable(text):
    """TEXT without a control character: a comment or a diff can carry escape codes for the terminal."""
    return "".join(ch for ch in text if ch.isprintable())


PAINT = {"added": "ok", "modified": "warn", "deleted": "bad", "muted": "dim"}     # a view's roles as the pager's


def pull_spec(review):
    """A pull request's REVIEW (core/github.py's review()) in the preview tab, read only: its head (number, title,
    state, branches, checks), then each file's diff, numbered, each thread under its line; the pager draws it."""
    word = REVIEW.get(review["review"])
    glyph, role = MARKS.get(review["mark"], ("", None))
    rows = [[(f"#{review['number']} ", "dim"), (printable(review["title"]), "bold"),
             *([(f"  {word[0]}", PAINT[word[1]])] if word else [])],
            [(printable(f"{review['branch']} → {review['base']} · {review['author']}"), "dim"),
             *([(" · ", "dim"), (glyph, PAINT[role]), (f" {review['checks_said']}", "dim")] if glyph else []),
             (f" · {len(review['files'])} file{'' if len(review['files']) == 1 else 's'}", "dim")]]
    side = {"+": "ok", "-": "bad"}
    for file in review["files"]:
        rows += [[], [(printable(file["path"]), "bold"), (f"  +{file['added']}", "ok"),
                      (f" −{file['removed']}", "bad")]]
        for row in file["rows"]:
            number = "" if row["kind"] == "@" else str(row["old"] if row["kind"] == "-" else row["new"])
            rows.append([(f"{number:>5} ", "dim"), (printable(row["text"]) if row["kind"] == "@" else
                                                    f"{row['kind'].strip() or ' '} {printable(row['text'])}",
                                                    "dim" if row["kind"] == "@" else side.get(row["kind"]))])
            rows += thread_rows(row.get("threads", ()))
        if file["cut"]:
            rows.append([(f"      {file['cut']} more lines: in the browser", "dim")])
        rows += thread_rows(file["loose"])
    title = f"#{review['number']} {truncate(review['title'], TAB_TITLE)}"
    return {"title": title, "line": None, "file": os.devnull, "pipeline": [],
            "views": [{"key": "r", "name": "Review", "lines": preview.painted(rows), "wrap": True}], "view": "r"}


def thread_rows(threads):
    """THREADS under their line, as the app shows them: each comment's author and age (a resolved thread's first one
    says so), then its words."""
    rows = []
    for thread in threads:
        for n, comment in enumerate(thread["comments"]):
            rows.append([("      ┃ ", "dim"), (printable(f"{comment['author']} · {comment['ago']}") +
                                                 (" · resolved" if thread["resolved"] and not n else ""), "dim")])
            rows += [[("      ┃ ", "dim"), (printable(line), None)] for line in comment["body"].splitlines()]
    return rows
