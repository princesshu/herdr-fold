"""Tests for the sidebar's own part of its Issues view (src/plugins/sidebar/issue_work.py): the latest answer kept
for the repository's other sidebars, and what a tab of its opens for an issue."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import SRC, set_env, stubs

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import github  # noqa: E402
import issue_work  # noqa: E402
from github import Query  # noqa: E402

ISSUES = [{"number": 42, "title": "Login fails on Safari", "state": "OPEN", "updatedAt": "2026-10-22T10:00:00Z",
           "url": "https://github.com/acme/app/issues/42",
           "labels": [{"name": "bug", "color": "d73a4a"}, {"name": "ui", "color": "ededed"}],
           "assignees": [{"login": "dev", "name": "Dev"}]},
          {"number": 38, "title": "Add a dark mode toggle", "state": "OPEN", "updatedAt": "2026-10-19T09:00:00Z",
           "url": "https://github.com/acme/app/issues/38", "labels": [], "assignees": []}]
# a GitHub CLI that writes its arguments to $GH_LOG and answers with $GH_ANSWER (or fails as $GH_FAIL says); a GraphQL
# request ("gh api graphql") with $GH_FIELDS and the exit code $GH_FIELDS_RC (gh's 1 when one part of it failed), or
# fails without it
FAKE_GH = """#!/bin/sh
printf '%s\\n' "$*" >> "$GH_LOG"
if [ -n "$GH_FAIL" ]; then printf '%s\\n' "$GH_FAIL" >&2; exit 4; fi
if [ "$1 $2" = "api graphql" ]; then [ -n "$GH_FIELDS" ] || exit 1; cat "$GH_FIELDS"; exit "${GH_FIELDS_RC:-0}"; fi
cat "$GH_ANSWER"
"""
# GitHub's issue fields as GraphQL gives them: the organization's Priority (Urgent, High, Medium, Low) on #42, another
# field beside it; none on #38
FIELDS = {"data": {"repository": {
    "i42": {"issueFieldValues": {"nodes": [{"name": "S", "field": {"name": "Effort"}},
                                           {"name": "High", "field": {"name": "Priority"}}]}},
    "i38": {"issueFieldValues": {"nodes": []}}}}}


class Shared(unittest.TestCase):
    """One question a minute for every sidebar of a repository: the latest answer kept in the state folder."""

    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        self.listing = github.Listing((github.Issue(42, "Login fails", ("bug",), ("dev",), "2026-10-22T10:00:00Z",
                                                    "OPEN", "https://github.com/acme/app/issues/42", "High"),))

    def test_an_answer_kept_comes_back_while_fresh(self):
        issue_work.keep(self.state, "acme/app", Query(), self.listing)
        self.assertEqual(issue_work.kept(self.state, "acme/app", Query(), 60), self.listing)

    def test_nothing_kept_where_the_state_folder_is_gone(self):
        # removed with herdr-fold while a sidebar still asked: not brought back
        gone = os.path.join(self.state, "gone")
        issue_work.keep(gone, "acme/app", Query(), self.listing)
        self.assertFalse(os.path.exists(gone))

    def test_none_when_old_for_another_query_or_repository_or_damaged(self):
        issue_work.keep(self.state, "acme/app", Query(), self.listing)
        self.assertIsNone(issue_work.kept(self.state, "acme/app", Query(), 0))
        self.assertIsNone(issue_work.kept(self.state, "acme/app", Query("closed"), 60))
        self.assertIsNone(issue_work.kept(self.state, "acme/web", Query(), 60))
        for name in os.listdir(self.state):
            with open(os.path.join(self.state, name), "w") as f:
                f.write("{")
        self.assertIsNone(issue_work.kept(self.state, "acme/app", Query(), 60))

    def test_none_when_it_is_not_as_kept(self):
        # a file not as keep() writes it (another version's, or edited by hand): GitHub is asked instead
        issue_work.keep(self.state, "acme/app", Query(), self.listing)
        path = issue_work.shared_path(self.state, "acme/app", Query())
        with open(path) as f:
            good = json.load(f)
        row = good["issues"][0]
        wrong = [{**good, "issues": [{**row, **change}]}
                 for change in ({"number": "42"}, {"number": True}, {"title": 7}, {"labels": "bug"},
                                {"assignees": [1]}, {"priority": None}, {"more": ""})]
        wrong += [{**good, "error": {"text": "x"}}, {**good, "issues": {"42": row}}, [good]]
        for data in wrong:
            with self.subTest(data=data):
                with open(path, "w") as f:
                    json.dump(data, f)
                self.assertIsNone(issue_work.kept(self.state, "acme/app", Query(), 60))


class Tabs(unittest.TestCase):
    def test_the_preview_shows_it_as_a_terminal_would(self):
        spec = issue_work.view_spec("acme/app", github.Issue(42, "Login fails on Safari"))
        self.assertEqual(spec["title"], "#42 Login fails on Safa…")             # a tab's name: its title cut short
        self.assertEqual(spec["pipeline"][0][1:], ["issue", "view", "42", "-R", "acme/app", "--comments"])
        self.assertTrue(os.path.isabs(spec["pipeline"][0][0]))
        self.assertTrue(spec["env"]["GH_FORCE_TTY"])

    def test_new_issue_and_comment_run_gh_s_own_prompts(self):
        self.assertEqual(issue_work.create_argv("acme/app")[1:], ["issue", "create", "-R", "acme/app"])
        self.assertEqual(issue_work.comment_argv("acme/app", 42)[1:], ["issue", "comment", "42", "-R", "acme/app"])


if __name__ == "__main__":
    unittest.main()
