"""The Changes and Issues panels' work in the dock (scm.py and issues.py draw them): staging, a message written by
Claude or Codex, the commit, push and sync, a diff or a commit in the preview tab; the repository's GitHub issues,
handed to the agent, answered, closed; done through the sidebar that hosts them."""
import os

import commit_message
import git
import github
import issue_work
import preview
from family import Family
from fileops import Ops
from issues import Issues
from scm import Scm

STALE = 60.0                  # seconds: the issues shown or listed here asked for again (a new one shows up)
BUSY = {"commit": "Committing…", "sync": "Syncing…", "pull": "Pulling…", "push": "Pushing…"}   # the first running shows
SPINNER, SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏", 0.1     # ✦'s writing in the message field: a frame every SPIN seconds
EMPTY = git.Status()


class Changes(Family):
    PANELS = ("changes", "issues")

    def __init__(self, host):
        super().__init__(host)
        icons, settings = host.settings["icons"], host.settings
        self.views = {"changes": Scm(settings["commit_mode"], icons, settings["folded"]), "issues": Issues(icons)}
        self.repo_ops = Ops(host.repo) if host.repo else None
        self.issues_asked = {}                            # when each query's issues were last asked for
        self.suggesting = None                            # the message as it was when ✦ asked; None: no answer wanted
        self.writing, self.spun = "", 0.0                 # who writes it (commit_message.writing()), its last frame
        self.views["changes"].linked = self.linked()

    def tick(self, now):
        listing = self.views["issues"].listing            # asked on screen; behind it only while it lists any
        if self.host.github and (self.host.showing("issues") or listing and listing.issues):
            self.fresh_issues(STALE)
        if "suggest" in self.host.running and now >= self.spun + SPIN:
            self.spun = now
            return True
        return False

    def deadlines(self):
        return [self.spun + SPIN] if "suggest" in self.host.running else []

    def came(self, panel):
        if panel == "changes":
            self.host.refresh()
        elif panel == "issues":
            self.fresh_issues(STALE)

    def resume(self):
        if self.host.showing("issues"):
            self.fresh_issues(STALE)

    def took_status(self, answer):
        self.repo_ops = Ops(answer.repo) if answer.repo else None
        scm = self.views["changes"]
        scm.linked, scm.repo, scm.github, scm.status = answer.issue, answer.repo, answer.github, answer.status
        if answer.graph is not None:
            scm.graph = answer.graph

    def drawing(self):
        scm = self.views["changes"]
        scm.busy(next((text for kind, text in BUSY.items() if kind in self.host.running), None))
        frame = SPINNER[int(self.host.clock() / SPIN) % len(SPINNER)]
        scm.writing = f"{frame} {self.writing}" if "suggest" in self.host.running else None

    def holds(self):
        return self.views["changes"].confirm, self.views["issues"].confirm

    def left(self):
        return {"message": self.views["changes"].field.text, "changes": self.views["changes"].kept(),
                "issues": self.views["issues"].kept()}

    def take(self, left):
        self.views["issues"].take(left.get("issues"))
        if isinstance(left.get("message"), str) and left["message"]:
            self.views["changes"].set_message(left["message"])
        self.views["changes"].take(left.get("changes"))

    def fresh_issues(self, after):
        """The issues asked for again when their last answer is older than AFTER seconds and none is on its way: an
        answer another sidebar of the repository got less than STALE seconds ago is taken (one question a minute)."""
        issues = self.views["issues"]
        if self.host.clock() - self.issues_asked.get(issues.query, float("-inf")) > after and not issues.asked:
            issues.ask()
            self.do_load_issues(issues.query, shared=True)

    # --- the changes

    def do_preview_diff(self, path, staged):
        repo = self.host.repo
        untracked = not staged and any(c.path == path and c.code == "?" for c in (self.host.status or EMPTY).changes)
        if untracked:                                   # no diff to show: the file itself
            self.host.open_preview(preview.file_spec(repo, os.path.join(repo, path), None), repo)
        else:
            self.host.open_preview(preview.diff_spec(repo, path, staged), repo)

    def do_preview_commit(self, commit):
        self.host.open_preview(preview.commit_spec(self.host.repo, commit), self.host.repo)

    def git_job(self, kind, work, reload=False):
        def then(error):
            if error:
                self.host.error = error
            if reload:
                self.host.reload()                  # a discarded change: the files as they are now
            self.host.refresh()
        self.host.job(kind, work, then)

    def do_stage(self, paths):
        repo = self.host.repo
        self.git_job("git", lambda: git.stage(repo, list(paths)))

    def do_unstage(self, paths):
        repo = self.host.repo
        self.git_job("git", lambda: git.unstage(repo, list(paths)))

    def do_discard(self, paths):
        repo, ops = self.host.repo, self.repo_ops
        untracked = {change.path for change in (self.host.status or EMPTY).changes if change.code == "?"}

        def work():
            for path in paths:
                if path in untracked:           # never deleted: an untracked file goes to the Trash
                    ops.trash(os.path.join(repo, path))
                else:
                    error = git.discard(repo, path)
                    if error:
                        return error
            return None

        self.git_job("git", work, reload=True)

    def do_suggest(self):
        """The message written for what a commit takes: the staged changes, or every change, staged first."""
        if "suggest" in self.host.running:
            return
        status = self.host.status or EMPTY
        if not (status.staged or status.changes):
            self.host.error = "Nothing to commit"
            return
        self.suggesting, repo = self.views["changes"].field.text, self.host.repo
        self.writing = commit_message.writing()

        def work():
            git.stage_all(repo)
            return commit_message.write(commit_message.request(repo))

        self.host.job("suggest", work, self.got_suggestion)

    def got_suggestion(self, suggestion):
        """The written message goes into the field only if nothing happened meanwhile: no commit, no typing."""
        wanted, self.suggesting = self.suggesting, None
        scm = self.views["changes"]
        if suggestion.message:
            if wanted is not None and scm.field.text == wanted:
                scm.set_message(commit_message.with_fixes(suggestion.message, scm.linked and scm.linked[0]))
        else:
            self.host.error = "No message: " + commit_message.explain(suggestion.problems)
        self.host.refresh()                             # what was staged for it

    def do_commit(self, message, mode, paths):
        if self.host.running & {"commit", "sync", "pull", "push"}:
            self.host.note = "A commit or sync is still running"
            return
        self.suggesting, repo = None, self.host.repo     # a message still being written is for changes now committed

        def work():
            ok, line = git.commit(repo, message, paths)
            if not ok:
                return False, line
            if mode in ("push", "sync"):
                ok, line = (git.push if mode == "push" else git.sync)(repo)
            return True, None if ok else git.advice(line)

        def then(answer):
            committed, error = answer
            if committed:
                self.views["changes"].set_message("")
                linked = self.views["changes"].linked
                if linked and commit_message.fixes(message, linked[0]):
                    self.do_unlink()                    # GitHub closes it with the push
            self.host.error = error
            self.host.refresh()

        self.host.job("commit", work, then)

    def do_remember_mode(self, mode):
        self.host.save(commit_mode=mode)

    def do_remember_folded(self, folded):
        self.host.save(folded=folded)

    def do_sync(self, how="sync"):
        """The branch synced with its upstream, or only pulled or pushed (HOW), as the repository row asks."""
        repo = self.host.repo
        if not repo or self.host.running & {"sync", "pull", "push"}:
            return

        def work():
            ok, line = getattr(git, how)(repo)
            return None if ok else git.advice(line)

        self.git_job(how, work)

    def do_repo_web(self):
        name = self.host.github

        def then(error):
            if error:
                self.host.error = error
        self.host.job("repo", lambda: github.open_in_browser(name), then)

    # --- the issues

    def do_load_issues(self, query, shared=False):
        """The issues of QUERY from GitHub, kept for the repository's other sidebars; SHARED: one of them got less
        than STALE seconds ago taken instead (R and a change made here always ask GitHub)."""
        name, state_dir = self.host.github, self.host.state_dir
        if not name:
            return

        def work():
            listing = issue_work.kept(state_dir, name, query, STALE) if shared else None
            if listing is None:
                listing = github.issues(name, query)
                issue_work.keep(state_dir, name, query, listing)
            return listing

        def then(listing):
            self.issues_asked[query] = self.host.clock()
            self.views["issues"].show(listing, query)

        self.host.job("issues", work, then)

    def do_preview_issue(self, issue):
        self.host.open_preview(issue_work.view_spec(self.host.github, issue), self.host.repo or self.host.root)

    def do_issue_web(self, issue):
        name = self.host.github

        def then(error):
            if error:
                self.host.error = f"{error}: {issue.url}"
        self.host.job("issue", lambda: github.open_in_browser(name, issue.number), then)

    def do_issue_comment(self, issue):
        self.host.open_tab(f"issue: #{issue.number}", github.comment_argv(self.host.github, issue.number))

    def do_new_issue(self):
        self.host.open_tab("issue: new", github.create_argv(self.host.github))

    def do_issue_change(self, issue, what):
        name, done = self.host.github, {"close": "Closed", "reopen": "Reopened", "assign": "Assigned to you:"}[what]

        def then(error):
            self.host.error = error
            if not error:
                self.host.note = f"{done} #{issue.number}"
            self.host.act(self.views["issues"].ask(), "issues")

        self.host.job("issue", lambda: github.change(name, issue.number, what), then)

    def do_issue_to_agent(self, issue):
        """The tab's Claude or Codex gets the issue as a prompt, not sent yet, and the focus; the next commit fixes
        it."""
        me, herdr, name = os.environ.get("HERDR_PANE_ID"), self.host.herdr, self.host.github

        def work():
            tab = herdr.call("pane", "get", me).get("pane", {}).get("tab_id") if me else None
            agents = herdr.call("agent", "list").get("agents", [])
            target = next((a["pane_id"] for a in agents if a.get("tab_id") == tab and a.get("agent") in
                           ("claude", "codex")), None)
            if target is None:
                return "No Claude or Codex in this tab to hand the issue to"
            herdr.call("pane", "send-text", target, github.prompt(name, issue))
            herdr.call("agent", "focus", target)
            return None

        def then(error):
            self.host.error = error
            if not error:
                self.link((issue.number, issue.title))

        self.host.job("agent", work, then)

    def linked(self):
        """The issue this repository's next commit fixes: (number, title), or None."""
        repo = self.host.repo
        found = self.host.settings["linked"].get(repo) if repo else None
        return (int(found[0]), str(found[1])) if isinstance(found, list) and len(found) == 2 else None

    def do_unlink(self):
        self.link(None)

    def link(self, issue):
        """ISSUE ((number, title), or None) as the one this repository's next commit fixes, as the app mod links it."""
        try:
            commit_message.link(self.host.repo, issue, self.host.state_dir)
        except OSError as err:
            self.host.error = f"settings not saved: {err}"
            return
        self.views["changes"].linked = issue
