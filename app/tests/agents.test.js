// @ts-check
// Tests for the chat's agents (agents.js): how Claude is started and resumed, the settings that bring the chat's hook
// and status line, and the modes, efforts and commands it names in its own words.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { budgetNotice, costBlock } from "../mods/herdr-fold/agents.js";
import { ADAPTERS, agentChoices, agentsOpen, barFolds, cardFor, claudeArgv, claudeSettings, contextColor,
  contextLine, contextParts, DRAWABLE, effortAt, effortLabel, exportName, limitNotice, menuSkills, modelName,
  defaultRan, modelOf, modelRows, modeOf, modeRows, nearEffort, newAgent, nextScope, opensAs, panelStep, promptText,
  rememberAgent, reopensAs, replyFor, ringArc, screenChoices, screenMode, shellQuote, skillCommand, skillOf,
  shellsOnly, slashMenu, slashQuery, slashRank, SLIDER, switchCommand, switchRefused, terminalSpace, terminalTab,
  usedSkills,
  atTyped, mentionMenu, mentionPick, mentionQuery, mentions, uploadPaths, withFiles }
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

test("a model picked before the chat starts goes with --model; Default, Claude's own, with none", () => {
  assert.deepEqual(claudeArgv({ python: PYTHON, session: SESSION, mode: "manual" }).slice(5), ["--permission-mode",
    "manual"]);                                                               // Manual as Claude's CLI names it
  const argv = claudeArgv({ python: PYTHON, session: SESSION, model: "claude-sonnet-5-5", effort: "low" });
  assert.deepEqual(argv.slice(5), ["--model", "claude-sonnet-5-5", "--effort", "low"]);
  assert.deepEqual(claudeArgv({ python: PYTHON, session: SESSION, model: "default" }),
    ["claude", "--session-id", SESSION, "--settings", claudeSettings(PYTHON)]);
});

test("a reopened chat resumes its session, its mode and effort left as Claude kept them", () => {
  assert.deepEqual(claudeArgv({ python: PYTHON, session: SESSION, resume: true }),
    ["claude", "--resume", SESSION, "--settings", claudeSettings(PYTHON)]);
});

test("a session id, a model, a mode and an effort Claude does not know are refused, never passed on", () => {
  for (const bad of [{ session: "--dangerously-skip-permissions" }, { session: SESSION, mode: "bypassPermissions" },
    { session: SESSION, effort: "ultra" }, { session: SESSION, model: "--dangerously-skip-permissions" }]) {
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

test("the context in use in words by the number rule: its share, and how much of the window when known", () => {
  assert.equal(contextLine({ context: 34, window: 200000 }), "68.0k of 200k · 34%");
  assert.equal(contextLine({ context: 12, window: 1000000 }), "120k of 1M · 12%");    // a window's size as core's head
  assert.equal(contextLine({ context: 1, window: 1000000 }), "10.0k of 1M · 1%");
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
    ["Yes, and allow edits for the rest of this chat", "keep", undefined],             // a mode for now, never kept
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

test("a rule is kept only as its card says it: one rule, or edits for now; anything else offers no keep", () => {
  const keys = (/** @type {any} */ card) => card.options.map((o) => o.choice);
  const dirs = { type: "addDirectories", directories: ["/elsewhere"], destination: "session" };
  const two = { type: "addRules", behavior: "allow", destination: "localSettings",
    rules: [{ toolName: "Bash", ruleContent: "pytest:*" }, { toolName: "Bash", ruleContent: "rm:*" }] };
  assert.deepEqual(keys(cardFor(asked("Bash", { command: "touch a" }, [dirs]))), ["allow", "deny"]);
  assert.deepEqual(keys(cardFor(asked("Bash", { command: "pytest" }, [two]))), ["allow", "deny"]);
  assert.deepEqual(keys(cardFor(asked("Edit", { file_path: "a.py" }, [dirs]))), ["allow", "deny"]);
  assert.deepEqual(keys(cardFor(asked("WebFetch", { url: "https://a.example" }, [dirs]))), ["allow", "deny"]);
  const fetch = cardFor(asked("WebFetch", { url: "https://a.example" }, [{ type: "addRules", behavior: "allow",
    destination: "localSettings", rules: [{ toolName: "WebFetch", ruleContent: "domain:a.example" }] }]));
  assert.equal(fetch.options[1].label, "Yes, and don't ask again for WebFetch(domain:a.example)");
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
  assert.deepEqual(screenChoices(screen([" ❯ 1. Yes", "   2. No", ...Array(8).fill("Claude's words"), "> "])), []);
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
  // the words in Claude's output never pass for its mode: only its footer, the screen's last lines, at a line's start
  const spoof = "  I printed: ⏵⏵ auto mode on\n⏵⏵ auto mode on\n" + "output\n".repeat(8);
  assert.equal(screenMode(claude, `${spoof}─────\n⏸ manual mode on\n`), "manual");
  assert.equal(screenMode(claude, `${spoof}─────\n> waiting\n`), null);
  assert.equal(screenMode(claude, "─────\n  echo ⏵⏵ auto mode on\n"), null);
});

test("Claude's models are its CLI's, Default first (its own), each with a name and a line; ids it takes", () => {
  assert.deepEqual(claude.models.map((m) => m.label), ["Default", "Opus 5.5", "Fable 5.2", "Sonnet 5.5", "Haiku 5.5"]);
  for (const m of claude.models) {
    assert.ok(m.description && !m.description.endsWith("."), m.id);            // one line, no full stop, as a menu's
    assert.match(m.id, /^(default|claude-[a-z]+-\d+(-\d+)?)$/);
  }
});

test("the model the agent names is its row: by id (dated, [1m]) or by the status line's name; else none", () => {
  const id = (/** @type {string | null} */ name) => modelOf(claude, name)?.id ?? null;
  assert.deepEqual(["claude-opus-5-5", "claude-opus-5-5[1m]", "Opus 5.5", "Opus 5.5 (1M context)", "Opus",
    "claude-haiku-5-5-20261001", "Sonnet 5.5"].map(id), ["claude-opus-5-5", "claude-opus-5-5", "claude-opus-5-5",
    "claude-opus-5-5", "claude-opus-5-5", "claude-haiku-5-5", "claude-sonnet-5-5"]);
  // one it does not list (an older one, another agent's), none said, and Default, which no agent names, are none
  assert.deepEqual(["claude-opus-4-8", "claude-opus-5-5-preview", "gpt-x", "", null, "default", "Default"].map(id),
    [null, null, null, null, null, null, null]);
});

test("the model chip's rows are its adapter's models, the one in use first where it lists none such", () => {
  assert.deepEqual(modelRows(claude, { id: "claude-opus-5-5", label: "Opus 5.5" }).map((r) => r.kind === "model"
    && r.id), ["default", "claude-opus-5-5", "claude-fable-5-2", "claude-sonnet-5-5", "claude-haiku-5-5"]);
  const unlisted = modelRows(claude, { id: null, label: "Opus 4.8" });
  assert.deepEqual([unlisted.length, unlisted[0]], [6, { kind: "model", id: null, label: "Opus 4.8",
    description: "In use in this chat" }]);
  assert.deepEqual(modelRows({ ...claude, models: [] }, null), []);
  assert.equal(modelRows(claude, null, { label: "Opus 5.5" })[0].description,     // what Default runs as, on its line
    "The recommended model for your account: Opus 5.5");
});

test("a chat on Default not started yet names the model and level Default last ran as, never the word", () => {
  assert.deepEqual(defaultRan(claude, { model: "claude-opus-5-5", effort: "xhigh" }), { label: "Opus 5.5",
    effort: "xhigh" });
  assert.deepEqual(defaultRan(claude, { model: "Opus 5.5" }), { label: "Opus 5.5", effort: null });
  assert.equal(defaultRan(claude, { model: "claude-opus-4-8" })?.label, modelName("claude-opus-4-8"));  // unlisted
  assert.deepEqual([defaultRan(claude, null), defaultRan(claude, { effort: "high" })], [null, null]);   // never ran
});

test("the mode chip's rows: the adapter's modes, Effort where it has levels, its switches (Codex: none)", () => {
  const ids = (/** @type {any[]} */ rows) => rows.map((r) => (r.kind === "effort" ? "effort" : r.id));
  assert.deepEqual(ids(modeRows(claude)), ["manual", "acceptEdits", "plan", "auto", "effort", "ultracode"]);
  // an agent with levels and no switch (as Codex's would be) has no Ultracode row; one with neither, its modes only
  assert.deepEqual(ids(modeRows({ ...claude, switches: [] })).slice(-2), ["auto", "effort"]);
  assert.ok(modeRows({ ...claude, efforts: [], switches: [] }).every((r) => r.kind === "mode"));
});

test("the panel's keys step its rows from the model in use, over a switch refused, held at the ends", () => {
  const none = () => false, refused = (/** @type {number} */ n) => n === 6;
  assert.equal(panelStep(7, null, 1, none, 1), 1);                           // first: the model in use
  assert.equal(panelStep(7, null, -1, none, -1), 0);                         // none in use: the first row
  assert.equal(panelStep(7, 1, 1, none), 2);
  assert.equal(panelStep(7, 0, -1, none), 0);                                // held at the top
  assert.equal(panelStep(7, 6, 1, none), 6);                                 // and at the foot
  assert.equal(panelStep(7, 5, 1, refused), 5);                              // Ultracode refused: never on it
  assert.equal(panelStep(0, null, 1, none), null);
});

test("a narrow bar leaves the context's words out first, then the chip's level; each back only with room to spare",
  () => {
    const both = [60, 50];                                                   // the words' px, the level's
    assert.equal(barFolds(0, 40, both), 0);                                  // room left: both shown
    assert.equal(barFolds(0, 0, both), 1);                                   // none left (or cut): the words out
    assert.equal(barFolds(1, 0, both), 2);                                   // still none: the level too
    assert.equal(barFolds(2, 0, both), 2);                                   // nothing more gives way
    assert.equal(barFolds(2, 57, both), 2);                                  // just enough: still out, no flicker
    assert.equal(barFolds(2, 58, both), 1);                                  // room to spare: the level back
    assert.equal(barFolds(1, 60, both), 1);
    assert.equal(barFolds(1, 68, both), 0);                                  // and then the words
    // a part not there (no context yet) is never kept out: the level goes first, and comes back by its own room
    assert.equal(barFolds(0, 0, [null, 50]), 2);
    assert.equal(barFolds(2, 58, [null, 50]), 1);
    assert.equal(barFolds(1, 4, [null, 50]), 0);
    assert.equal(barFolds(0, 0, [null, null]), 0);
  });

test("the context's parts: the rules read at the start, the skills' list, the connectors, the rest", () => {
  const setup = { rules: [{ tokens: 2400, paths: [] }, { tokens: 1800, paths: [] }, { tokens: 700, paths: ["src/**"] }],
    skills: [{ tokens: 150 }, { tokens: 50 }], servers: [{ tokens: 6800 }, { tokens: null }] };
  assert.deepEqual(contextParts({ context: 34, window: 200000 }, setup), [
    { key: "rules", label: "Rules", tokens: 4200, share: 0.021 },        // a rule read for its paths: not known in use
    { key: "skills", label: "Skills", tokens: 200, share: 0.001 },
    { key: "connectors", label: "Connectors", tokens: 6800, share: 0.034 },
    { key: "rest", label: "Chat & tools", tokens: 56800, share: 0.284 }]);
  // estimates past what is in use take only what there is; a part with nothing is left out
  const parts = (/** @type {number} */ context, /** @type {any} */ given) => contextParts({ context, window: 200000 },
    given).map((p) => [p.key, p.tokens]);
  assert.deepEqual(parts(1, setup), [["rules", 2000]]);
  assert.deepEqual(parts(10, { rules: [], skills: [] }), [["rest", 20000]]);
  // the setup not read yet, or the window not known: what is in use, as one
  for (const [status, setupNow] of [[{ context: 34, window: 200000 }, null], [{ context: 34, window: null }, setup]]) {
    const parts = contextParts(status, setupNow);
    assert.deepEqual(parts.map((p) => [p.key, p.label, p.share]), [["used", null, 0.34]]);
  }
});

test("a skill called is the setup's: its name and source, a plugin's by plugin:skill; one not listed as called", () => {
  const skills = [{ name: "api-routes", source: "Project", scope: "Project", path: "/w/api-routes/SKILL.md" },
    { name: "review", source: "Global", scope: "Global", path: "/h/review/SKILL.md" },
    { name: "review", source: "code-review", scope: "Global", path: "/h/plugins/review/SKILL.md" }];
  assert.deepEqual(skillOf(claude, "api-routes", skills), { name: "api-routes", source: "Project",
    path: "/w/api-routes/SKILL.md", known: true });
  assert.equal(skillOf(claude, "review", skills).source, "Global");          // the user's own, not the plugin's
  assert.deepEqual(skillOf(claude, "code-review:review", skills), { name: "review", source: "code-review",
    path: "/h/plugins/review/SKILL.md", known: true });
  // not in the setup (not read yet, or gone): a plugin's still says its plugin; another, nothing
  assert.deepEqual(skillOf(claude, "superpowers:brainstorming", []), { name: "brainstorming", source: "superpowers",
    path: null, known: false });
  assert.deepEqual(skillOf(claude, "notes", skills), { name: "notes", source: null, path: null, known: false });
  // an agent that names no plugin's skill so: the name as called
  assert.equal(skillOf({ ...claude, skill: null }, "code-review:review", skills).name, "code-review:review");
});

test("the skills a chat used: each once, the latest call first, with when it was called last", () => {
  const rows = [{ kind: "skill", name: "api-routes", at: "t1" }, { kind: "tool", name: "Read", at: "t2" },
    { kind: "skill", name: "code-review:review", at: "t3" }, { kind: "skill", name: "api-routes", at: "t4" },
    { kind: "skill", name: "", at: "t5" }];
  assert.deepEqual(usedSkills(claude, rows, []).map(({ skill, at }) => [skill.name, at]),
    [["api-routes", "t4"], ["review", "t3"]]);
  assert.deepEqual(usedSkills(claude, [], []), []);
});

test("a skill is typed as Claude takes it: /name, a plugin's /plugin:name", () => {
  assert.equal(skillCommand(claude, { name: "api-routes", source: "Project", scope: "Project" }), "/api-routes");
  assert.equal(skillCommand(claude, { name: "review", source: "code-review", scope: "Global" }),
    "/code-review:review");
  assert.equal(skillCommand({ ...claude, skill: null }, { name: "x", source: "Project", scope: "Project" }), null);
});

test("Claude's setup is read, its chats compacted by its own command, its skills named as it calls them", () => {
  assert.equal(claude.setup, "claude");                                      // agent_setup.py claude FOLDER
  assert.equal(claude.compact, "/compact");
  assert.ok(claude.commands.some((c) => c.name === claude.compact && !c.words));
  assert.deepEqual(claude.skill, { command: "/", plugin: ":" });
});

test("the slider's arrows step through the agent's own efforts, held at their ends", () => {
  const claude = ADAPTERS.claude;
  assert.equal(nearEffort(claude, "high", 1), "xhigh");
  assert.equal(nearEffort(claude, "high", -1), "medium");
  assert.equal(nearEffort(claude, "max", 1), "max");
  assert.equal(nearEffort(claude, "low", -1), "low");
  assert.equal(nearEffort(claude, null, 1), "xhigh");                      // none said yet: from the middle, High
  assert.equal(nearEffort(claude, "turbo", -1), "medium");
});

test("a press or a drag on the slider's track picks the level whose stop is under the pointer", () => {
  const claude = ADAPTERS.claude, left = 100, width = 2 * SLIDER.pad + claude.efforts.length * SLIDER.stop;
  const start = left + SLIDER.pad;                                             // the first stop's room starts here
  assert.equal(effortAt(claude, start, left), "low");
  assert.equal(effortAt(claude, start + 2 * SLIDER.stop + SLIDER.stop / 2, left), "high");     // the middle stop
  assert.equal(effortAt(claude, start + 5 * SLIDER.stop - 1, left), "max");
  assert.equal(effortAt(claude, left - 40, left), "low");                     // dragged past either end: held there
  assert.equal(effortAt(claude, left + width + 40, left), "max");
  assert.ok(SLIDER.knob <= SLIDER.stop && SLIDER.dot < SLIDER.knob);         // the knob in a stop's room: nothing moves
  assert.ok(SLIDER.knob < SLIDER.high);                                        // and inside the pill
});

test("Claude's Ultracode is its adapter's switch: on at launch by --settings, then /effort ultracode [off]", () => {
  const claude = ADAPTERS.claude, ultracode = claude.switches.find((sw) => sw.id === "ultracode");
  assert.ok(ultracode);
  assert.equal(ultracode?.label, "Ultracode");
  const argv = claudeArgv({ python: "python3", session: "0b9f6d1e-1c2a-4f3b-8d4e-5f6a7b8c9d0e",
    switches: { ultracode: true } });
  assert.equal(JSON.parse(argv[argv.indexOf("--settings") + 1]).ultracode, true);
  assert.ok(!argv.includes("ultracode"));                                     // never --effort ultracode (xhigh)
  const plain = claudeArgv({ python: "python3", session: "0b9f6d1e-1c2a-4f3b-8d4e-5f6a7b8c9d0e" });
  assert.equal("ultracode" in JSON.parse(plain[plain.indexOf("--settings") + 1]), false);
  assert.equal(switchCommand(claude, "ultracode", true), "/effort ultracode");
  assert.equal(switchCommand(claude, "ultracode", false), "/effort ultracode off");
});

test("a switch Claude refuses says why in Claude's words; one it took, or an agent with none, says nothing", () => {
  const claude = ADAPTERS.claude;
  const refused = "> /effort ultracode\n  ⎿ Ultracode needs dynamic workflows enabled (see /config). Valid options";
  assert.equal(switchRefused(claude, "ultracode", `${refused} are: low, medium, high, xhigh, max, auto\n`),
    "Ultracode needs dynamic workflows enabled (see /config)");
  assert.equal(switchRefused(claude, "ultracode", "  ⎿ Ultracode on (this session only). Effort stays high.\n"), null);
  assert.equal(switchRefused(claude, "ultracode", `${refused}\n> /effort ultracode\n  ⎿ Ultracode on.\n`), null);
  const codex = { ...claude, name: "Codex", switches: [] };                   // Codex: its own levels, no Ultracode
  assert.equal(codex.switches.length, 0);
  assert.equal(switchCommand(codex, "ultracode", true), null);
  assert.equal(switchRefused(codex, "ultracode", "anything"), null);
});

// the app's knownAgents(), as it lists them: most picked first, each with its icon and how it starts
const KNOWN = [{ key: "codex", name: "Codex", icon: "icons/codex.svg", tint: true, run: ["codex", "--no-daemon"],
  installed: true }, { key: "claude", name: "Claude", icon: "icons/claude.png", tint: false, run: ["claude"],
  installed: true }, { key: "aider", name: "Aider", run: ["aider"], installed: false },
  { key: "gemini", name: "Gemini", run: ["gemini"], installed: true },
  { key: "amp", name: "Amp", run: ["amp"], installed: true }];

test("a new chat's list: installed agents only, the recent ones first in their order, the rest by name", () => {
  const listed = agentChoices(KNOWN, DRAWABLE, ["codex", "claude", "aider"]);
  assert.deepEqual(listed.map((a) => a.key), ["codex", "claude", "amp", "gemini"]);      // aider: not installed
  assert.deepEqual(listed.map((a) => a.recent), [true, true, false, false]);
  assert.deepEqual(listed.map((a) => a.terminal), [true, false, true, true]);    // Claude alone has an adapter
  assert.deepEqual(listed[0].run, ["codex", "--no-daemon"]);                  // as the app starts it
  assert.deepEqual([listed[0].icon, listed[0].tint, listed[3].icon], ["icons/codex.svg", true, null]);
  // none remembered: by name; the app's check failed (none known): the agents a chat draws all the same
  assert.deepEqual(agentChoices(KNOWN, DRAWABLE, null).map((a) => a.key), ["amp", "claude", "codex", "gemini"]);
  assert.deepEqual(agentChoices([], DRAWABLE, ["codex"]), [{ key: "claude", name: "Claude", installed: true,
    terminal: false, recent: false, signIn: false, icon: null, tint: false, run: ["claude"] }]);
});

test("a new chat's list marks the agents core says are to sign in; one core finds nowhere is left out", () => {
  const machine = [{ key: "claude", installed: true, signed_in: true }, { key: "codex", installed: true,
    signed_in: false }, { key: "gemini", installed: true, signed_in: null }];
  const listed = agentChoices(KNOWN, DRAWABLE, [], machine);
  assert.deepEqual(listed.map((a) => [a.key, a.signIn]), [["amp", false], ["claude", false], ["codex", true],
    ["gemini", false]]);                                    // not told (Gemini CLI's, one core knows nothing of): none
  // the app's own word on what is installed stands (it starts it); where it tells nothing, core's does
  assert.deepEqual(agentChoices([], DRAWABLE, [], [{ key: "claude", installed: false, signed_in: null }]), []);
  assert.deepEqual(agentChoices(KNOWN, DRAWABLE, [], [{ key: "codex", installed: false, signed_in: null }])
    .map((a) => a.key), ["amp", "claude", "codex", "gemini"]);
  assert.deepEqual(agentChoices(KNOWN, DRAWABLE, [], "nonsense").map((a) => a.signIn), [false, false, false, false]);
});

test("an agent started goes first among the recent ones, once, eight at most", () => {
  assert.deepEqual(rememberAgent(["claude", "codex"], "codex"), ["codex", "claude"]);
  assert.deepEqual(rememberAgent(undefined, "claude"), ["claude"]);
  assert.deepEqual(rememberAgent([1, "amp", null], "claude"), ["claude", "amp"]);       // a stray value dropped
  const many = ["a", "b", "c", "d", "e", "f", "g", "h"];
  assert.deepEqual(rememberAgent(many, "z"), ["z", ...many.slice(0, 7)]);
});

test("every way in opens an agent as Open agents in says: a chat where one draws it, else a terminal", () => {
  assert.deepEqual([agentsOpen(undefined), agentsOpen("terminal"), agentsOpen("menu")], ["chat", "terminal", "chat"]);
  assert.equal(opensAs("claude", "chat"), "chat");
  assert.equal(opensAs("claude", "terminal"), "terminal");
  assert.equal(opensAs("codex", "chat"), "terminal");               // no adapter yet: always a terminal
  assert.equal(opensAs("claude", "chat", "lab"), "terminal");       // a chat runs on this Mac for now
  assert.equal(opensAs("constructor", "chat"), "terminal");         // not an adapter of the object's own
  // + and Issues' To agent: a chat with the latest agent a chat draws; in a terminal the latest of all
  assert.deepEqual(newAgent(["codex", "claude"], "chat"), { agent: "claude", as: "chat" });
  assert.deepEqual(newAgent(["codex", "claude"], "terminal"), { agent: "codex", as: "terminal" });
  assert.deepEqual(newAgent(["codex"], "chat"), { agent: "claude", as: "chat" });
  assert.deepEqual(newAgent(null, "terminal"), { agent: "claude", as: "terminal" });
  assert.deepEqual(newAgent(["claude"], "chat", "lab"), { agent: "claude", as: "terminal" });
  // Chats: a closed Claude chat reopens as a chat; Codex's, an id Claude does not take, or Terminal: as today
  const closed = { agent: "claude", id: SESSION };
  assert.equal(reopensAs(closed, "chat"), "chat");
  assert.equal(reopensAs(closed, "terminal"), "terminal");
  assert.equal(reopensAs({ agent: "codex", id: SESSION }, "chat"), "terminal");
  assert.equal(reopensAs({ agent: "claude", id: "../a1b2" }, "chat"), "terminal");
});

test("a space that holds shells alone, as the app makes one, is the one a chat opens first in", () => {
  const space = { id: "s1", tabs: [{ id: "t1" }, { id: "t2" }] };
  const shell = { pane: "p1", tab: "t1", terminal: "c1", program: { name: "zsh", agent: false } };
  assert.equal(shellsOnly(space, [shell, { ...shell, pane: "p2", tab: "t2", terminal: "c2" }]), true);
  assert.equal(shellsOnly(space, [shell, { pane: "p3", tab: "t2", terminal: null, mod: "herdr-fold" }]), false);
  assert.equal(shellsOnly(space, [{ ...shell, program: { name: "Claude", agent: true } }]), false);
  assert.equal(shellsOnly(space, [shell, { ...shell, tab: "elsewhere", terminal: null }]), true);   // its own panes
  assert.equal(shellsOnly({ id: "s2", tabs: [] }, []), false);                                       // nothing yet
});

test("an agent in a terminal tab: as the app starts it, in the space's folder, the prompt its first message", () => {
  const codex = agentChoices(KNOWN, DRAWABLE, [])[2];
  assert.deepEqual(terminalTab(codex, { space: "s1", folder: "/work/lumen-api", prompt: "Fix #42" }),
    { name: "Codex", space: "s1", folder: "/work/lumen-api", argv: ["codex", "--no-daemon"], task: "Fix #42" });
  assert.deepEqual(terminalTab(codex, { space: "s1" }), { name: "Codex", space: "s1", argv: ["codex", "--no-daemon"] });
  // a new space with Open agents in: Terminal: the agent its first tab, on the space's machine, in its folder
  assert.deepEqual(terminalSpace(codex, { machine: "", folder: "/work/lumen-api" }),
    { machine: "", folder: "/work/lumen-api", tab: "Codex", argv: ["codex", "--no-daemon"] });
  assert.deepEqual(terminalSpace(codex, { machine: "lab" }), { machine: "lab", tab: "Codex",
    argv: ["codex", "--no-daemon"] });
  // OpenCode as the app knows it: no adapter, so its own CLI, in a tab or as a new space's first
  const known = [...KNOWN, { key: "opencode", name: "OpenCode", icon: "icons/opencode.svg", tint: true,
    run: ["opencode"], installed: true }];
  const opencode = agentChoices(known, DRAWABLE, ["opencode"])[0];
  assert.deepEqual([opencode.key, opencode.terminal, opencode.icon], ["opencode", true, "icons/opencode.svg"]);
  assert.deepEqual(terminalTab(opencode, { space: "s1", folder: "/work/lumen-api" }),
    { name: "OpenCode", space: "s1", folder: "/work/lumen-api", argv: ["opencode"] });
  assert.deepEqual(terminalSpace(opencode, { machine: "" }), { machine: "", tab: "OpenCode", argv: ["opencode"] });
  // Copilot the same way, as the app's own programs list has it
  const copilot = agentChoices([...known, { key: "copilot", name: "Copilot", icon: "icons/copilot.svg", tint: true,
    run: ["copilot"], installed: true }], DRAWABLE, ["copilot"])[0];
  assert.deepEqual([copilot.key, copilot.terminal], ["copilot", true]);
  assert.deepEqual(terminalTab(copilot, { space: "s1", folder: "/work/lumen-api" }),
    { name: "Copilot", space: "s1", folder: "/work/lumen-api", argv: ["copilot"] });
  assert.deepEqual(terminalSpace(copilot, { machine: "lab" }), { machine: "lab", tab: "Copilot", argv: ["copilot"] });
});

test("the / menu follows what is typed after a \"/\" at the prompt's start, till a space or a new line", () => {
  assert.deepEqual(["/", "/rev", "/code-review:review", "/review 42", "/a\nb", "fix /rev", "", " /rev"]
    .map(slashQuery), ["", "rev", "code-review:review", null, null, null, null, null]);
});

/** A / menu row as chat.js makes them: PART, NAME, what it is TYPED as, its LINE. */
const item = (part, name, typed, line) => ({ part, name, typed, line });
const MENU = [item("This conversation", "Export the conversation…", null, ""),
  item("Skills", "api-routes", "/api-routes", "How lumen-api's routes are written and tested"),
  item("Skills", "frontend-design", "/frontend-design", "Distinctive, intentional visual design"),
  item("Skills", "code-review", "/code-review:code-review", "Review a pull request"),
  item("Skills", "security-review", "/code-review:security-review", "Review the changes for security problems"),
  item("Claude's commands", "/compact", "/compact", "Free the context, keep a summary"),
  item("Claude's commands", "/review", "/review", "Review a pull request")];

test("typed, the best match goes first: a name's start, a word's, the name, then its line; case aside", () => {
  assert.equal(slashRank(MENU[6], "rev"), 0);                                   // /review: its name starts so
  assert.equal(slashRank(MENU[3], "Rev"), 1);                                   // code-review: a word of it does
  assert.equal(slashRank(MENU[3], "ode"), 2);                                   // code-review holds it
  assert.equal(slashRank(MENU[1], "tested"), 3);                                // api-routes' line holds it
  assert.equal(slashRank(MENU[3], "code-review:co"), 0);                        // what a plugin's is typed as
  assert.equal(slashRank(MENU[0], "export"), 0);                                // Export, named so, typed as nothing
  assert.equal(slashRank(MENU[5], "zzz"), null);
  assert.deepEqual(slashMenu(MENU, "rev", 5).parts.map((p) => [p.name, p.items.map((i) => i.name)]),
    [[null, ["/review", "code-review", "security-review"]]]);
  assert.deepEqual(slashMenu(MENU, "zzz", 5), { parts: [], more: 0 });          // nothing found: no menu
});

test("before anything is typed, the menu's parts in their order, a few of each, and how many more there are", () => {
  const menu = slashMenu(MENU, "", 2);
  assert.deepEqual(menu.parts.map((p) => [p.name, p.items.map((i) => i.name)]),
    [["This conversation", ["Export the conversation…"]], ["Skills", ["api-routes", "frontend-design"]],
      ["Claude's commands", ["/compact", "/review"]]]);
  assert.equal(menu.more, 2);                                                   // two skills found by typing
  assert.equal(slashMenu(MENU, null, 5).more, 0);
  assert.deepEqual(slashMenu([], null, 5), { parts: [], more: 0 });
});

test("the / menu's skills: those the chat used first, the latest first, then the rest as listed", () => {
  const skills = [{ name: "api-routes", source: "Project", scope: "Project" },
    { name: "frontend-design", source: "Global", scope: "Global" },
    { name: "review", source: "code-review", scope: "Global" }];
  const rows = [{ kind: "skill", name: "api-routes", at: "t1" },
    { kind: "skill", name: "code-review:review", at: "t2" }, { kind: "skill", name: "gone", at: "t3" }];
  assert.deepEqual(menuSkills(claude, rows, skills).map((s) => s.name), ["review", "api-routes", "frontend-design"]);
  assert.deepEqual(menuSkills(claude, [], skills), skills);
});

test("a chat is exported under its title at first, with nothing in it macOS takes for a folder", () => {
  assert.equal(exportName("# Fix the page past the last one\n\n**You**\n"), "Fix the page past the last one.md");
  assert.equal(exportName("# a/b: c\\d\n"), "a-b- c-d.md");
  assert.equal(exportName("# " + "x".repeat(100)), `${"x".repeat(80)}.md`);
  assert.equal(exportName("#  \n"), "Chat.md");
  assert.equal(exportName(""), "Chat.md");
});

test("the files macOS's chooser answered: a path a line, absolute ones alone, each once, no control code", () => {
  assert.deepEqual(uploadPaths("/Users/dev/notes/paging spec.pdf\n/Users/dev/lumen-api/README.md\n"),
    ["/Users/dev/notes/paging spec.pdf", "/Users/dev/lumen-api/README.md"]);
  assert.deepEqual(uploadPaths(""), []);                                        // cancelled
  assert.deepEqual(uploadPaths("/Users/dev/a.txt\r\n/Users/dev/a.txt\nnotes.txt\n/Users/dev/b\x1b[2J.txt\n"),
    ["/Users/dev/a.txt"]);
});

test("a file is named to Claude as @ and its path: from the chat's folder when in it, quoted with a space", () => {
  assert.equal(claude.files, "@");
  assert.equal(mentions(["/Users/dev/lumen-api/src/lumen/routes/books.py", "/Users/dev/notes/paging spec.pdf",
    "/Users/dev/lumen-api/docs/error format.md"], "/Users/dev/lumen-api"),
  '@src/lumen/routes/books.py @"/Users/dev/notes/paging spec.pdf" @"docs/error format.md"');
  assert.equal(mentions(["/Users/dev/lumen-api-old/a.py"], "/Users/dev/lumen-api"), "@/Users/dev/lumen-api-old/a.py");
  assert.equal(mentions([], "/Users/dev/lumen-api"), "");
});

test("the files go after the message's words; with no words they are the message", () => {
  const files = ["/Users/dev/lumen-api/README.md"];
  assert.equal(withFiles("Check this against the spec", files, "/Users/dev/lumen-api"),
    "Check this against the spec @README.md");
  assert.equal(withFiles("", files, "/Users/dev/lumen-api"), "@README.md");
  assert.equal(withFiles("Check this", [], "/Users/dev/lumen-api"), "Check this");
});

test("@ at a word's start, at the text's end, opens Add context on what follows it", () => {
  assert.equal(mentionQuery("@"), "");
  assert.equal(mentionQuery("Check @boo"), "boo");
  assert.equal(mentionQuery("Check\n@src/lu"), "src/lu");
  assert.equal(mentionQuery("mail dev@example"), null);                        // not a word's start
  assert.equal(mentionQuery("Check @books.py now"), null);                     // a space after it: done
  assert.equal(mentionQuery("Check"), null);
});

test("Add context… types the @ at the text's end, a space before it where a word ends there", () => {
  assert.equal(atTyped(""), "@");
  assert.equal(atTyped("Check"), "Check @");
  assert.equal(atTyped("Check "), "Check @");
  assert.equal(atTyped("Check @bo"), "Check @bo");                             // one typed already: its list as it is
});

test("a file picked takes the place of the @ typed: its path, quoted with a space in it, a space after", () => {
  assert.equal(mentionPick("Check @boo", "src/lumen/routes/books.py"), "Check @src/lumen/routes/books.py ");
  assert.equal(mentionPick("@", "docs/error format.md"), '@"docs/error format.md" ');
  assert.equal(mentionPick("Check", "README.md"), "Check @README.md ");       // no @ typed: at the end
});

test("Add context lists the changed files first, then the folder's; typed, what it finds, the best first", () => {
  const changed = ["src/lumen/routes/books.py", "tests/test_books.py"];
  const files = ["README.md", "src/lumen/routes/books.py", "src/lumen/store.py", "docs/books.md",
    "tests/test_books.py"];
  const menu = mentionMenu(changed, files, "", 2);
  assert.deepEqual(menu.parts.map((p) => [p.name, p.items.map((i) => i.typed)]), [
    ["Changed", ["src/lumen/routes/books.py", "tests/test_books.py"]],
    ["Files", ["README.md", "src/lumen/store.py"]]]);                          // a changed one listed once
  assert.equal(menu.more, 1);
  assert.deepEqual(menu.parts[0].items[0], { part: "Changed", name: "books.py", typed: "src/lumen/routes/books.py",
    line: "src/lumen/routes", row: { kind: "mention", path: "src/lumen/routes/books.py" } });
  assert.equal(mentionMenu(changed, files, "", 2).parts[1].items[0].line, "");  // a file in the folder itself
  const found = mentionMenu(changed, files, "books", 2);
  assert.deepEqual(found.parts.map((p) => p.name), [null]);
  assert.deepEqual(found.parts[0].items.map((i) => i.typed), ["src/lumen/routes/books.py", "docs/books.md",
    "tests/test_books.py"]);                                                   // its name starts with it, then a word
  assert.deepEqual(mentionMenu(changed, files, "zzz", 2), { parts: [], more: 0 });
  assert.deepEqual(mentionMenu([], [], "", 2), { parts: [], more: 0 });
});

test("the budget's notice is core's, the first not closed here; an answer of another shape is none", () => {
  const said = { key: "codex:2026-11", agent: "codex",
    text: "Codex has spent $45.10 of $50 this month · on pace for $58 by Nov 30" };
  assert.deepEqual(budgetNotice({ notices: [said] }, new Set()), { key: said.key, text: said.text });
  assert.equal(budgetNotice({ notices: [said] }, new Set(["codex:2026-11"])), null);       // closed for the month
  assert.deepEqual(budgetNotice({ notices: [said, { key: "claude:2026-11", text: "Claude has spent…" }] },
    new Set(["codex:2026-11"]))?.key, "claude:2026-11");
  for (const odd of [null, {}, { notices: "x" }, { notices: [{ key: 1, text: "x" }, { key: "k" }] }]) {
    assert.equal(budgetNotice(odd, new Set()), null);
  }
});

test("the Context panel's cost block: the whole, a row a model, the subagents' beside theirs, each with a ~", () => {
  const model = (/** @type {string} */ name, /** @type {string} */ color) => ({ id: name, name, color });
  const costs = { session: "abc", kind: "API value", text: "~$4.12", tokens: "1.2M",
    line: "1.2M tokens · 82% from cache",
    agent: { cost: 3.7, text: "~$3.70", model: model("Opus 5.5", "#3987e5") },
    subs: { Explore: { cost: 0.42, text: "~$0.42", model: model("Haiku 5.5", "#199e70") } } };
  assert.deepEqual(costBlock(costs), { session: "abc", label: "This chat", figure: "~$4.12",
    unit: "API value", rows: [{ name: "Opus 5.5", color: "#3987e5", figure: "~$3.70" },
      { name: "Haiku 5.5 · 1 subagent", color: "#199e70", figure: "~$0.42" }], line: "1.2M tokens · 82% from cache" });
  const two = costBlock({ ...costs, subs: { ...costs.subs, Plan: { cost: 0.08, text: "~$0.08",
    model: model("Haiku 5.5", "#199e70") }, review: { cost: null, text: "no price",
    model: model("codex-auto-review", "#8b8b8b") } } });
  assert.deepEqual(two?.rows.slice(1), [{ name: "Haiku 5.5 · 2 subagents", color: "#199e70", figure: "~$0.50" },
    { name: "codex-auto-review · 1 subagent", color: "#8b8b8b", figure: "no price" }]);
  assert.equal(costBlock({ ...costs, kind: "spent" })?.unit, "spent");
  assert.equal(costBlock({ ...costs, text: "no price" })?.unit, "");          // tokens alone: no dollars' word
  assert.equal(costBlock(null), null);
  assert.equal(costBlock({ text: "~$1.00" }), null);                           // not costs.py's answer
});
