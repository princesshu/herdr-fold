// @ts-check
// Tests for the chat's agents (agents.js): how Claude is started and resumed, the settings that bring the chat's hook
// and status line, and the modes, efforts and commands it names in its own words.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ADAPTERS, cardFor, claudeArgv, claudeSettings, contextColor, contextLine, effortLabel, limitNotice,
  modelName, modeOf, nextScope, promptText, replyFor, ringArc, screenChoices, screenMode, shellQuote }
  from "../mods/herdr-fold/agents.js";
import { CHAT_HOOK } from "../mods/herdr-fold/helper.js";

const SESSION = "5f0c6d9e-1b2a-4c3d-8e9f-0a1b2c3d4e5f";
const PYTHON = "/usr/bin/python3";
const claude = ADAPTERS.claude;

const CHOICES = [{ key: "1", label: "Yes, and use auto mode" }, { key: "2", label: "Yes, manually approve edits" },
  { key: "3", label: "Tell Claude what to change" }];

test("a new chat starts Claude with its session id, the settings, the mode and the effort chosen", () => {
  const argv = claudeArgv({ python: PYTHON, session: SESSION, mode: "plan", effort: "high" });
  assert.deepEqual(argv, ["claude", "--session-id", SESSION, "--settings", claudeSettings(PYTHON),
    "--permission-mode", "plan", "--effort", "high"]);
});

test("a first prompt goes last, after --, so a dash at its start is no option", () => {
  assert.deepEqual(claudeArgv({ python: PYTHON, session: SESSION, prompt: "-q: why does page 4 answer page 3?" })
    .slice(-2), ["--", "-q: why does page 4 answer page 3?"]);
});

test("a reopened chat resumes its session, its mode and effort left as Claude kept them", () => {
  assert.deepEqual(claudeArgv({ python: PYTHON, session: SESSION, resume: true }),
    ["claude", "--resume", SESSION, "--settings", claudeSettings(PYTHON)]);
});

test("a session id, a mode and an effort Claude does not know are refused, never passed on", () => {
  for (const bad of [{ session: "--dangerously-skip-permissions" }, { session: SESSION, mode: "bypassPermissions" },
    { session: SESSION, effort: "ultra" }]) {
    assert.throws(() => claudeArgv({ python: PYTHON, ...bad }), /not/);
  }
});

test("the settings bring the hook and the status line, each running the hook's source with Python", () => {
  const settings = JSON.parse(claudeSettings(PYTHON));
  const [rule] = settings.hooks.PermissionRequest;
  assert.equal(rule.matcher, "*");
  assert.deepEqual(Object.keys(rule.hooks[0]).sort(), ["command", "timeout", "type"]);
  assert.equal(rule.hooks[0].timeout, 600);
  const python = `'${PYTHON}' '-X' 'utf8' '-I' '-c' ${shellQuote(CHAT_HOOK)}`;
  assert.equal(rule.hooks[0].command, `${python} permission`);
  assert.deepEqual(settings.statusLine, { type: "command", command: `${python} status` });
});

test("the status line's command runs through the shell and keeps the chat's numbers", () => {
  const home = mkdtempSync(join(tmpdir(), "herdr-fold-agents-"));
  try {
    const done = spawnSync("/bin/sh", ["-c", JSON.parse(claudeSettings(PYTHON)).statusLine.command], {
      input: JSON.stringify({ session_id: SESSION, model: { display_name: "Opus" },
        context_window: { used_percentage: 7 } }),
      env: { HOME: home, PATH: "/usr/bin:/bin" }, encoding: "utf8" });
    assert.equal(done.stdout, "Opus · ctx 7%\n", done.stderr);
    assert.ok(existsSync(join(home, ".local", "state", "herdr-fold", "chat", SESSION, "status.json")));
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("a quoted text comes back whole through the shell: quotes, a new line, a dollar", () => {
  for (const text of ["it's", "a\nb", "$HOME `x` \\n", "'''", ""]) {
    const done = spawnSync("/bin/sh", ["-c", `printf %s ${shellQuote(text)}`], { encoding: "utf8" });
    assert.equal(done.stdout, text);
  }
});

test("every mode has a label, a line and an icon the mod has; every effort a label", () => {
  assert.deepEqual(claude.modes.map((m) => m.id), ["manual", "acceptEdits", "plan", "auto"]);
  assert.deepEqual(claude.modes.map((m) => m.label), ["Manual", "Edit automatically", "Plan", "Auto"]);
  for (const mode of claude.modes) {
    assert.ok(mode.description, mode.id);
    assert.ok(existsSync(new URL(`../mods/herdr-fold/icons/lucide/${mode.icon}.svg`, import.meta.url)), mode.icon);
  }
  assert.deepEqual(claude.efforts.map((e) => e.label), ["Low", "Medium", "High", "Extra high", "Max"]);
  assert.deepEqual(claude.commands.map((c) => c.name), ["/compact", "/review"]);
  for (const command of claude.commands) assert.ok(command.description, command.name);
});

test("a command runs at once from its menu; one that takes words waits in the prompt for them", () => {
  assert.deepEqual(claude.commands.filter((c) => c.words).map((c) => c.name), ["/review"]);
});

test("the agent's name is in its copy once at most: never in a label, once in a line", () => {
  for (const { label, description } of [...claude.modes, ...claude.commands.map((c) => ({ label: c.name, ...c }))]) {
    assert.ok(!label.includes(claude.name), label);
    assert.ok(description.split(claude.name).length <= 2, description);
  }
});

test("the mode Claude's session file names: Manual is default there", () => {
  assert.equal(modeOf(claude, "default")?.label, "Manual");
  assert.equal(modeOf(claude, "acceptEdits")?.label, "Edit automatically");
  assert.equal(modeOf(claude, "bypassPermissions"), null);
});

test("a prompt goes to the terminal without its control codes: an escape sequence and a bell out, lines kept", () => {
  assert.equal(promptText("Fix it\x1b[31m now\x07\n\tthe pager  \r\n"), "Fix it now\n\tthe pager");
  assert.equal(promptText("\x1b]0;title\x07plain"), "plain");
});

test("the context ring's color: the status line's own thresholds", () => {
  assert.deepEqual([0, 49, 50, 79, 80, 100].map(contextColor), ["green", "green", "yellow", "yellow", "red", "red"]);
});

test("the context ring's arc runs from the top clockwise to its share; none at nothing, the whole at all", () => {
  const end = (/** @type {number} */ percent) => {
    const arc = ringArc(percent);
    return arc && typeof arc === "object" ? [Math.round(arc.x * 1000) / 1000, Math.round(arc.y * 1000) / 1000,
      arc.large] : arc;
  };
  assert.deepEqual([0, 25, 50, 75, 100, 130].map(end), [null, [14, 8, false], [8, 14, false], [2, 8, true],
    "whole", "whole"]);
});

test("the context in use in words: its share, and how much of the window that is when known", () => {
  assert.equal(contextLine({ context: 34, window: 200000 }), "68k of 200k · 34%");
  assert.equal(contextLine({ context: 12, window: 1000000 }), "120k of 1M · 12%");
  assert.equal(contextLine({ context: 34, window: null }), "34%");
});

test("a limit at 80% or more is said once until its next reset; under it nothing", () => {
  const zone = process.env.TZ;
  process.env.TZ = "America/New_York";
  try {
    const reset = Date.parse("2026-11-10T14:00:00Z") / 1000, now = new Date("2026-11-08T14:00:00Z");
    const status = (used) => ({ limits: { five_hour: { used: 12, resets: null }, week: { used, resets: reset } } });
    assert.equal(limitNotice(status(79), new Set(), now), null);
    const notice = limitNotice(status(84), new Set(), now);
    assert.equal(notice?.text, "You've used 84% of your weekly limit · resets Tue 10 Nov, 09:00");   // 24 hours
    assert.equal(limitNotice(status(84), new Set([notice?.key]), now), null);           // dismissed
    const later = { limits: { five_hour: { used: 0, resets: null }, week: { used: 90, resets: reset + 604800 } } };
    assert.ok(limitNotice(later, new Set([notice?.key]), now));                         // the next reset's
    assert.equal(limitNotice(null, new Set(), now), null);
  } finally {
    if (zone === undefined) delete process.env.TZ;
    else process.env.TZ = zone;
  }
});

test("an effort is named in the agent's own words", () => {
  assert.deepEqual(["xhigh", "low", "turbo"].map((id) => effortLabel(claude, id)), ["Extra high", "Low", "turbo"]);
});

test("a model's id reads as its name, as the status line names it, until the status line says it", () => {
  assert.deepEqual(["claude-opus-5-5", "claude-opus-5-5[1m]", "claude-sonnet-5-5-20261001", "claude-fable-5-1",
    "gpt-x"].map(modelName), ["Opus 5.5", "Opus 5.5", "Sonnet 5.5", "Fable 5.1", "gpt-x"]);
});

// requests as core/chat_hook.py writes them (request.json)
const RULE = { type: "addRules", rules: [{ toolName: "Bash", ruleContent: "pytest:*" }], behavior: "allow",
  destination: "localSettings" };
const asked = (tool_name, tool_input, permission_suggestions = []) => ({ id: "r1", kind: "permission", tool_name,
  tool_input, permission_suggestions });

// a plan, which Claude asks in its own dialog (core/chat_hook.py's DIALOG)
const PLAN = { ...asked("ExitPlanMode", { plan: "1. Cap the page" }), kind: "dialog" };

test("a command's card: Run a command?, the command and Claude's words, kept for a rule where one is suggested", () => {
  const card = cardFor(asked("Bash", { command: "pytest -q", description: "Run the tests" }, [RULE]));
  assert.deepEqual([card.kind, card.title, card.sentence, card.detail], ["command", "Run a command?", "pytest -q",
    "Run the tests"]);
  assert.deepEqual(card.options.map((o) => [o.key, o.label, o.choice, o.scope]), [
    ["1", "Yes", "allow", undefined], ["2", "Yes, and don't ask again for pytest commands", "keep", "project"],
    ["3", "No, tell Claude what to do instead", "deny", undefined]]);
  assert.deepEqual(cardFor(asked("Bash", { command: "ls" })).options.map((o) => [o.key, o.choice]),
    [["1", "allow"], ["2", "deny"]]);                     // numbered in order: the digit picks the one drawn
});

test("a change's card: the file as its folder names it, its old and new text, edits allowed for now", () => {
  const card = cardFor({ ...asked("Edit", { file_path: "/repo/lumen/src/books.py", old_string: "a", new_string: "b" },
    [{ type: "setMode", mode: "acceptEdits", destination: "session" }]), cwd: "/repo/lumen" });
  assert.deepEqual([card.kind, card.title, card.sentence, card.old, card.new], ["change", "Change a file?",
    "src/books.py", "a", "b"]);
  assert.deepEqual(card.options.map((o) => [o.label, o.choice, o.scope]), [["Yes", "allow", undefined],
    ["Yes, and allow edits for the rest of this conversation", "keep", undefined],     // a mode for now, never kept
    ["No, tell Claude what to do instead", "deny", undefined]]);
  assert.equal(cardFor({ ...asked("Edit", { file_path: "/etc/hosts" }), cwd: "/repo/lumen" }).sentence, "/etc/hosts");
  assert.deepEqual([cardFor(asked("Write", { file_path: "docs/a.md", content: "# A" })).new], ["# A"]);
});

test("a question's card holds every question; a plan's offers how to go on; another tool its name", () => {
  const questions = [{ question: "Which page size?", header: "Size", options: [{ label: "20", description: "" }],
    multiSelect: false }];
  const question = cardFor(asked("AskUserQuestion", { questions }));
  assert.deepEqual([question.kind, question.sentence, question.questions],
    ["question", "Which page size?", questions]);
  const plan = cardFor(PLAN, CHOICES);
  assert.deepEqual([plan.kind, plan.title, plan.detail], ["plan", "Ready to code?", "1. Cap the page"]);
  assert.deepEqual(plan.options.map((o) => [o.key, o.label, o.choice]), [["1", "Yes, and use auto mode", "key"],
    ["2", "Yes, manually approve edits", "key"], ["3", "Tell Claude what to change", "deny"]]);
  assert.deepEqual(cardFor(PLAN).options, []);                    // its dialog not drawn yet
  const other = cardFor(asked("WebFetch", { url: "https://example.com/api", prompt: "Read it" }));
  assert.deepEqual([other.kind, other.title, other.sentence], ["tool", "Use WebFetch?", "https://example.com/api"]);
});

test("a reply carries the request's id, its choice, the scope where a rule is kept, the words, the answers", () => {
  const card = cardFor(asked("Bash", { command: "pytest -q" }, [RULE]));
  assert.deepEqual(replyFor(card, card.options[0]), { id: "r1", choice: "allow" });
  assert.deepEqual(replyFor(card, card.options[1], { scope: "user" }), { id: "r1", choice: "keep", scope: "user" });
  assert.deepEqual(replyFor(card, card.options[1]), { id: "r1", choice: "keep", scope: "project" });
  assert.deepEqual(replyFor(card, card.options[2], { text: "Run only the pager's tests" }),
    { id: "r1", choice: "deny", text: "Run only the pager's tests" });
  assert.deepEqual(replyFor(card, { key: "1", label: "Submit", choice: "allow" }, { answers: { "Which?": "20" } }),
    { id: "r1", choice: "allow", answers: { "Which?": "20" } });
});

test("Claude's own dialog's choices are read off its screen: the run of numbered lines its cursor is in", () => {
  const screen = (/** @type {string[]} */ lines) => lines.join("\n");
  assert.deepEqual(screenChoices(screen(["  Steps", "  1. Cap the page", "  2. Test it", "",
    " Claude has written up a plan and is ready to execute. Would you like to proceed?",
    " ❯ 1. Yes, and use auto mode", "   2. Yes, manually approve edits", "   3. Tell Claude what to change",
    "      shift+tab to approve with this feedback", " ctrl+g to edit in Vim · ~/.claude/plans/x.md"])), CHOICES);
  assert.deepEqual(screenChoices(screen(["  1. Cap the page", "  2. Test it", "> "])), []);   // a plan's steps alone
});

test("a choice in Claude's own dialog is answered by its key there, its words after it", () => {
  const plan = cardFor(PLAN, CHOICES);
  assert.deepEqual(replyFor(plan, plan.options[1]), { id: "r1", choice: "key", key: "2" });
  assert.deepEqual(replyFor(plan, plan.options[2], { text: "Keep the old size" }),
    { id: "r1", choice: "deny", key: "3", text: "Keep the old size" });
});

test("a kept rule's scope moves with the arrows and stops at its ends", () => {
  assert.deepEqual([nextScope("session", 1), nextScope("project", 1), nextScope("user", 1)],
    ["project", "user", "user"]);
  assert.deepEqual([nextScope("user", -1), nextScope("project", -1), nextScope("session", -1)],
    ["project", "session", "session"]);
});

test("the mode in effect is read off Claude's own screen, its last mode line; none there, none known", () => {
  const screen = (line) => `─────\nOpus 5.5 · ctx 4%\n${line}\n`;
  assert.deepEqual(["⏸ manual mode on", "⏵⏵ auto mode on (shift+tab to cycle)", "⏵⏵ accept edits on",
    "⏸ plan mode on (shift+tab to cycle)", "> waiting"].map((line) => screenMode(claude, screen(line))),
  ["manual", "auto", "acceptEdits", "plan", null]);
});
