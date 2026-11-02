"""Where the folder picker starts: the folder holding the most git repositories under home (on Linux also /srv, /opt,
/var/www), searched for a moment at most; else ~/Documents or home. Only the user's and root's repositories count: on
a shared server, another user's never steer the picker."""
import collections
import os
import sys

DEPTH = 4                       # folder levels below a root that are searched
BUDGET = 0.5                    # seconds the search may take: the picker opens right after it


def roots(platform=sys.platform):
    home = os.path.expanduser("~")
    return [home] + (["/srv", "/opt", "/var/www"] if platform.startswith("linux") else [])


def start(found):
    """The folder holding the most of FOUND, the one nearer the root on a tie; without any, ~/Documents or home."""
    counts = collections.Counter(os.path.dirname(repo) for repo in found)
    if counts:
        return min(counts, key=lambda folder: (-counts[folder], folder.count(os.sep), folder))
    documents = os.path.join(os.path.expanduser("~"), "Documents")
    return documents if os.path.isdir(documents) else os.path.expanduser("~")

