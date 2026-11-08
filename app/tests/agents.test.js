// @ts-check
// Tests for the chat's agents (agents.js): how Claude is started and resumed, the settings that bring the chat's hook
// and status line, and the modes, efforts and commands it names in its own words.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ADAPTERS, claudeArgv, claudeSettings, modeOf, shellQuote } from "../mods/herdr-fold/agents.js";
import { CHAT_HOOK } from "../mods/herdr-fold/helper.js";

const SESSION = "5f0c6d9e-1b2a-4c3d-8e9f-0a1b2c3d4e5f";
const PYTHON = "/usr/bin/python3";
const claude = ADAPTERS.claude;

test("a new chat starts Claude with its session id, the settings, the mode and the effort chosen", () => {
  const argv = claudeArgv({ python: PYTHON, session: SESSION, mode: "plan", effort: "high" });
  assert.deepEqual(argv, ["claude", "--session-id", SESSION, "--settings", claudeSettings(PYTHON),
    "--permission-mode", "plan", "--effort", "high"]);
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
  for (const name of ["/compact", "/context", "/review", "/usage"]) {
    assert.ok(claude.commands.find((c) => c.name === name)?.description, name);
  }
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
