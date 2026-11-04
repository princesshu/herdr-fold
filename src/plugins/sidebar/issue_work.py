"""The sidebar's own part of its Issues view: the latest answer kept for the repository's other sidebars, and what a
tab of its opens for an issue (gh's preview with its comments, a new issue, a comment)."""
import hashlib
import json
import os
import shutil
import time
from dataclasses import asdict

import statefile
from github import Issue, Listing
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


def create_argv(repo):
    return [shutil.which("gh") or "gh", "issue", "create", "-R", repo]


def comment_argv(repo, number):
    return [shutil.which("gh") or "gh", "issue", "comment", str(number), "-R", repo]
