"""The Changes and Issues panels' work in the dock (scm.py, issues.py and pulls.py draw them): staging, a message
written by Claude or Codex, the commit, push and sync, a diff or a commit in the preview tab; the repository's issues
and pull requests, handed to the agent, answered, closed, a new one opened; done through the sidebar hosting them."""
import os

import commit_message
import git
import github
import issue_work
import panes
import preview
from family import Family
from fileops import Ops
from issues import Issues
from pulls import PullForm
from github import STALE
from scm import Scm
from screen import DONE, SPIN, SPINNER

TAB_NAME = 24                 # characters of a new agent's tab name (an issue's number and title), as a chat's
BUSY = {"commit": "Committing…", "sync": "Syncing…", "pull": "Pulling…", "push": "Pushing…"}   # the first running shows
EMPTY = git.Status()


class Changes(Family):
    PANELS = ("changes", "issues")

    def __init__(self, host):
        super().__init__(host)
        icons, settings = host.settings["icons"], host.settings
        self.views = {"changes": Scm(settings["commit_mode"], icons, settings["folded"]), "issues": Issues(icons)}
        self.repo_ops = Ops(host.repo) if host.repo else None
        self.issues_asked = {}                            # when each query's issues (or state's pulls) were last asked
        self.branch_asked = (None, float("-inf"))         # what the branch's pull request was asked for, and when
        self.suggesting = None                            # the message as it was when ✦ asked; None: no answer wanted
        self.writing, self.spun = "", 0.0                 # who writes it (commit_message.writing()), its last frame
        self.pull_writing = ""                            # who writes a new pull request's title and body
        self.views["changes"].linked = self.linked()

    def tick(self, now):
        listing = self.views["issues"].listing            # asked on screen; behind it only while it lists any
        if self.host.github and (self.host.showing("issues") or listing and listing.issues):
            self.fresh_issues(STALE)
        if self.spinning() and now >= self.spun + SPIN:
            self.spun = now
            return True
        return False

    def deadlines(self):
        return [self.spun + SPIN] if self.spinning() else []

    def spinning(self):
        """Whether a spinner turns: ✦ writing the message, a commit or a sync running (the sync glyph's cell), or the
        issues shown asked for again (Issues' header)."""
        issues, running = self.views["issues"], self.host.running
        return bool(running & {"suggest", "write_pull", *BUSY}) or bool(issues.asked and issues.list.items) or \
            bool(issues.pulls.asked and issues.pulls.list.items)

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
        self.fresh_branch_pull()

    def drawing(self):
        scm = self.views["changes"]
        frame = SPINNER[int(self.host.clock() / SPIN) % len(SPINNER)]
        scm.busy(next((text for kind, text in BUSY.items() if kind in self.host.running), None), frame)
        scm.writer = self.writing if "suggest" in self.host.running else None
        scm.writing = f"{frame} {scm.writer}" if scm.writer else None
        if scm.form:
            scm.form.writing = f"{frame} {self.pull_writing}" if "write_pull" in self.host.running else None

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
        if issues.board == "pulls":
            pulls = issues.pulls
            if self.host.clock() - self.issues_asked.get(("pulls", pulls.query), float("-inf")) > after \
                    and not pulls.asked:
                self.do_load_pulls(pulls.ask().args[0])
        elif self.host.clock() - self.issues_asked.get(issues.query, float("-inf")) > after and not issues.asked:
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

    def do_fail(self, error):
        """What a view could not do, on the sidebar's foot line, as every failure."""
        self.host.error = error

    def do_remember_mode(self, mode):
        self.host.save(commit_mode=mode)

    def do_remember_folded(self, folded):
        self.host.save(folded=folded)

    def do_sync(self, how="sync"):
        """The branch synced with its upstream, or only pulled or pushed (HOW), as the repository row asks."""
        repo = self.host.repo
        if not repo or self.host.running & set(BUSY):              # its spinner is no button while one runs
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
            self.host.act(self.views["issues"].show(listing, query), "issues")      # its search, once it is full

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
                self.host.note = f"{DONE} {done} #{issue.number}"
            self.host.act(self.views["issues"].ask(), "issues")

        self.host.job("issue", lambda: github.change(name, issue.number, what), then)

    def do_issue_set(self, issue, what, value, words, field):
        """ISSUE's priority or type (WHAT) set to VALUE on GitHub (WORDS its name), its row set already: the note says
        so; a failure says why, and the list is asked again, as it is."""
        def then(error):
            self.host.error = error
            if error:
                self.host.act(self.views["issues"].ask(), "issues")
            else:
                self.host.note = f"{DONE} Set #{issue.number} to {words}"

        self.host.job("issue", lambda: github.set_field(issue.node, what, value, field), then)

    def do_issue_to_agent(self, issue):
        """The tab's Claude or Codex gets the issue as a prompt, not sent yet, and the focus; with none there, the agent
        started last in a new tab of the workspace (the TUI's new chat); the next commit fixes it."""
        def then(error):
            self.host.error = error
            if not error:
                self.link((issue.number, issue.title))

        self.to_agent(issue, github.prompt(self.host.github, issue), then)

    def to_agent(self, item, prompt, then):
        """PROMPT, for ITEM (an issue or a pull request), to the tab's Claude or Codex, else to a new agent as
        do_issue_to_agent says; THEN with the line that says why not, or None."""
        me, herdr = os.environ.get("HERDR_PANE_ID"), self.host.herdr

        def work():
            pane = herdr.call("pane", "get", me).get("pane", {}) if me else {}
            agents = herdr.call("agent", "list").get("agents", [])
            target = next((a["pane_id"] for a in agents if a.get("tab_id") == pane.get("tab_id") and a.get("agent") in
                           panes.AGENTS), None)
            workspace = pane.get("workspace_id") or os.environ.get("HERDR_WORKSPACE_ID")
            if target is None and not workspace:
                return "It opens in a herdr tab: run the sidebar in herdr"
            if target is None:
                target = self.new_agent(workspace, item)
            herdr.call("pane", "send-text", target, prompt)
            herdr.call("agent", "focus", target)
            return None

        self.host.job("agent", work, then)

    def new_agent(self, workspace, issue):
        """A new tab in WORKSPACE for ISSUE (or a pull request), as Chats reopens one: the agent started last on the
        left, ready for input, the right column beside it; its pane."""
        call, state, folder = self.host.herdr.call, self.host.state_dir, self.host.repo or self.host.root
        agent, title = panes.last_agent(state), preview.label(f"#{issue.number} {issue.title}")
        made = call("tab", "create", "--workspace", workspace, "--cwd", folder, "--label",
                    title if len(title) <= TAB_NAME else title[:TAB_NAME - 1] + "…", "--no-focus")
        pane = made["root_pane"]["pane_id"]
        call("pane", "rename", pane, agent)            # named, so the new-tab plugin leaves it alone
        panes.build(call, pane, folder, state)         # the right column, as elsewhere
        call("agent", "start", f"{agent}-{issue.number}", "--kind", agent, "--pane", pane, "--timeout", "60000")
        call("tab", "focus", made["tab"]["tab_id"])
        return pane

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

    # --- the pull requests: the repository's (Issues' other list), the branch's (Changes' row), a new one's form

    def do_load_pulls(self, query):
        name = self.host.github
        if not name:
            return

        def then(found):
            self.issues_asked[("pulls", query)] = self.host.clock()
            self.host.act(self.views["issues"].pulls.show(found, query), "issues")

        self.host.job("pulls", lambda: github.pulls(name, query), then)

    def fresh_branch_pull(self):
        """The pushed branch's pull request asked for again once the branch or its last commit changed, or STALE
        seconds went by (Changes' own rhythm would ask gh every few seconds)."""
        scm, name = self.views["changes"], self.host.github
        branch = scm.status and scm.status.upstream and scm.status.branch      # never pushed: no pull request yet
        if not name or not branch or "branch_pull" in self.host.running:
            return
        key = (name, branch, scm.graph[0].hash if scm.graph else None)
        if key == self.branch_asked[0] and self.host.clock() - self.branch_asked[1] < STALE:
            return
        self.branch_asked = (key, self.host.clock())

        def then(answer):
            pull, base, error = answer
            scm.pull = None if error else (pull, base)

        self.host.job("branch_pull", lambda: github.branch_pull(name, branch), then)

    def do_pull_row(self):
        """Changes' row: the branch's pull request in the preview tab, or with none the form that opens one."""
        scm = self.views["changes"]
        if not scm.pull_shown():
            return
        pull, base = scm.pull
        if pull:
            self.do_preview_pull(pull)
            return
        scm.form = PullForm(scm.status.branch, [base], self.host.settings["icons"])
        repo = self.host.repo

        def then(bases):
            if scm.form:
                scm.form.bases = list(dict.fromkeys([base, *bases]))

        self.host.job("bases", lambda: git.bases(repo), then)
        self.do_write_pull(base)

    def do_new_pull(self):
        """Issues' + and c: Changes shown, its form open (or the branch's pull request there already)."""
        self.host.show("changes")
        self.do_pull_row()

    def do_write_pull(self, base):
        form, repo, state = self.views["changes"].form, self.host.repo, self.host.state_dir
        if not form or not repo:
            return
        self.pull_writing = commit_message.writing(what="the pull request")

        def then(answer):
            if self.views["changes"].form is form:
                form.fill(answer)

        self.host.job("write_pull", lambda: commit_message.pull_answer(repo, base, state), then)

    def do_open_pull(self, base, branch, title, body, draft):
        scm, name = self.views["changes"], self.host.github

        def then(answer):
            url, error = answer
            if error:
                if scm.form:
                    scm.form.note = (error, "deleted")
                return
            scm.form, self.branch_asked = None, (None, float("-inf"))
            self.host.note = f"Opened {url}"
            self.fresh_branch_pull()

        self.host.job("open_pull", lambda: github.open_pull(name, base, branch, title, body, draft), then)

    def do_pull_cancel(self):
        self.views["changes"].form = None

    def do_preview_pull(self, pull):
        """PULL's review in the preview tab, read only: its diff by file, each thread under its line."""
        name, cwd = self.host.github, self.host.repo or self.host.root

        def then(answer):
            review, error = answer
            if error:
                self.host.error = error
            else:
                self.host.open_preview(issue_work.pull_spec(review), cwd)

        self.host.job("pull", lambda: github.review(name, pull.number), then)

    def do_pull_web(self, pull):
        name = self.host.github

        def then(error):
            if error:
                self.host.error = f"{error}: {pull.url}"
        self.host.job("pull", lambda: github.open_in_browser(name, pull.number, "pr"), then)

    def do_pull_to_agent(self, pull):
        """The tab's Claude or Codex gets the pull request as a prompt, as an issue: to review it."""
        def then(error):
            self.host.error = error

        self.to_agent(pull, github.pull_prompt(self.host.github, pull.number), then)
