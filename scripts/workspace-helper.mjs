#!/usr/bin/env node

import { existsSync, readFileSync, realpathSync, statSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const CORE_ROOT = path.resolve(SCRIPT_DIR, "..");
const DEFAULT_MANIFEST = path.join(SCRIPT_DIR, "workspace-manifest.v1.json");
const ACTIONS = new Set([
  "list",
  "sync",
  "build",
  "refresh",
  "migrate",
  "deploy",
  "publish",
  "reset-data",
  "pipeline",
]);
const PIPELINE_ACTIONS = new Set(["sync", "build", "refresh", "deploy"]);
const ID_PATTERN = /^[a-z][a-z0-9-]*$/;

function fail(message) {
  throw new Error(message);
}

function asNonEmptyString(value, label) {
  if (typeof value !== "string" || value.trim() === "") {
    fail(`${label} must be a non-empty string.`);
  }
  return value.trim();
}

function validateId(value, label) {
  const id = asNonEmptyString(value, label);
  if (!ID_PATTERN.test(id)) {
    fail(`${label} must match ${ID_PATTERN}.`);
  }
  return id;
}

function validateRelativePath(value, label) {
  const candidate = asNonEmptyString(value, label);
  if (path.isAbsolute(candidate) || candidate.split(/[\\/]+/).includes("..")) {
    fail(`${label} must be a relative path without '..' segments.`);
  }
  return candidate;
}

function assertAllowedKeys(value, allowed, label) {
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) {
      fail(`${label} contains unsupported property '${key}'.`);
    }
  }
}

function assertUniqueIds(items, label) {
  const seen = new Set();
  for (const item of items) {
    const id = validateId(item?.id, `${label} id`);
    if (seen.has(id)) {
      fail(`Duplicate ${label} id: ${id}`);
    }
    seen.add(id);
  }
  return seen;
}

export function validateManifest(manifest) {
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    fail("Manifest must be a JSON object.");
  }
  assertAllowedKeys(manifest, new Set(["$schema", "schemaVersion", "workspaceRoot", "suite", "repositories", "components", "pipelines"]), "Manifest");
  if (manifest.schemaVersion !== "1.0") {
    fail("Manifest schemaVersion must be '1.0'.");
  }
  const workspaceRoot = asNonEmptyString(manifest.workspaceRoot, "workspaceRoot");
  if (path.isAbsolute(workspaceRoot)) {
    fail("workspaceRoot must be relative to the manifest file.");
  }
  if (!manifest.suite || typeof manifest.suite !== "object") {
    fail("Manifest suite configuration is required.");
  }
  assertAllowedKeys(manifest.suite, new Set(["profileOrder"]), "suite");
  if (!Array.isArray(manifest.suite.profileOrder) || manifest.suite.profileOrder.length === 0) {
    fail("suite.profileOrder must contain at least one profile.");
  }
  const profileIds = new Set();
  for (const value of manifest.suite.profileOrder) {
    const profile = validateId(value, "suite profile");
    if (profileIds.has(profile)) {
      fail(`Duplicate suite profile: ${profile}`);
    }
    profileIds.add(profile);
  }

  if (!Array.isArray(manifest.repositories) || manifest.repositories.length === 0) {
    fail("Manifest must contain at least one repository.");
  }
  const repositoryIds = assertUniqueIds(manifest.repositories, "repository");
  for (const repository of manifest.repositories) {
    assertAllowedKeys(repository, new Set(["id", "label", "path", "remoteName", "remoteUrl", "branch"]), `Repository ${repository.id}`);
    asNonEmptyString(repository.label, `Repository ${repository.id} label`);
    validateRelativePath(repository.path, `Repository ${repository.id} path`);
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(asNonEmptyString(repository.remoteName, `Repository ${repository.id} remoteName`))) {
      fail(`Repository ${repository.id} has an invalid remoteName.`);
    }
    const remoteUrl = asNonEmptyString(repository.remoteUrl, `Repository ${repository.id} remoteUrl`);
    if (!/^(https:\/\/|ssh:\/\/|git@)/.test(remoteUrl)) {
      fail(`Repository ${repository.id} remoteUrl must use HTTPS or SSH Git transport.`);
    }
    if (/^https?:\/\//.test(remoteUrl) || /^ssh:\/\//.test(remoteUrl)) {
      const parsedRemote = new URL(remoteUrl);
      const hasHttpUserInfo = parsedRemote.protocol.startsWith("http") && (parsedRemote.username || parsedRemote.password);
      if (hasHttpUserInfo || parsedRemote.password || parsedRemote.search || parsedRemote.hash) {
        fail(`Repository ${repository.id} remoteUrl cannot contain credentials, query parameters, or fragments.`);
      }
    } else if (/[?#]/.test(remoteUrl)) {
      fail(`Repository ${repository.id} remoteUrl cannot contain query parameters or fragments.`);
    }
    if (!/^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(asNonEmptyString(repository.branch, `Repository ${repository.id} branch`))) {
      fail(`Repository ${repository.id} has an invalid branch.`);
    }
  }

  if (!Array.isArray(manifest.components) || manifest.components.length === 0) {
    fail("Manifest must contain at least one component.");
  }
  const componentIds = assertUniqueIds(manifest.components, "component");
  const imageVariables = new Set();
  for (const component of manifest.components) {
    assertAllowedKeys(component, new Set(["id", "label", "repository", "path", "context", "dockerfile", "image", "imageVariable", "profile"]), `Component ${component.id}`);
    asNonEmptyString(component.label, `Component ${component.id} label`);
    if (!repositoryIds.has(component.repository)) {
      fail(`Component ${component.id} references unknown repository ${component.repository}.`);
    }
    for (const key of ["path", "context", "dockerfile"]) {
      validateRelativePath(component[key], `Component ${component.id} ${key}`);
    }
    if (!/^[A-Za-z0-9._/-]+$/.test(asNonEmptyString(component.image, `Component ${component.id} image`))) {
      fail(`Component ${component.id} has an invalid image name.`);
    }
    if (!/^[A-Z][A-Z0-9_]*$/.test(asNonEmptyString(component.imageVariable, `Component ${component.id} imageVariable`))) {
      fail(`Component ${component.id} has an invalid imageVariable.`);
    }
    if (imageVariables.has(component.imageVariable)) {
      fail(`Duplicate component imageVariable: ${component.imageVariable}`);
    }
    imageVariables.add(component.imageVariable);
    if (!profileIds.has(component.profile)) {
      fail(`Component ${component.id} references unknown profile ${component.profile}.`);
    }
  }

  const pipelines = manifest.pipelines ?? {};
  if (!pipelines || typeof pipelines !== "object" || Array.isArray(pipelines)) {
    fail("pipelines must be an object when provided.");
  }
  for (const [pipelineId, steps] of Object.entries(pipelines)) {
    validateId(pipelineId, "pipeline id");
    if (!Array.isArray(steps) || steps.length === 0) {
      fail(`Pipeline ${pipelineId} must contain at least one step.`);
    }
    for (const [index, step] of steps.entries()) {
      if (!step || typeof step !== "object" || !PIPELINE_ACTIONS.has(step.action)) {
        fail(`Pipeline ${pipelineId} step ${index + 1} has an unsupported action.`);
      }
      assertAllowedKeys(step, new Set(["action", "targets", "configuredImages", "refreshImages"]), `Pipeline ${pipelineId} step ${index + 1}`);
      const validIds = step.action === "sync" ? repositoryIds : componentIds;
      if (step.targets !== "all") {
        if (!Array.isArray(step.targets) || step.targets.length === 0) {
          fail(`Pipeline ${pipelineId} step ${index + 1} must define targets.`);
        }
        for (const target of step.targets) {
          if (!validIds.has(target)) {
            fail(`Pipeline ${pipelineId} step ${index + 1} references unknown target ${target}.`);
          }
        }
      }
      if (step.refreshImages !== undefined && typeof step.refreshImages !== "boolean") {
        fail(`Pipeline ${pipelineId} step ${index + 1} refreshImages must be boolean.`);
      }
      if (step.configuredImages !== undefined && (step.action !== "refresh" || typeof step.configuredImages !== "boolean")) {
        fail(`Pipeline ${pipelineId} step ${index + 1} configuredImages is valid only for refresh steps.`);
      }
    }
  }
  return manifest;
}

export function loadManifest(manifestPath = DEFAULT_MANIFEST) {
  const absolutePath = path.resolve(manifestPath);
  let manifest;
  try {
    manifest = JSON.parse(readFileSync(absolutePath, "utf8"));
  } catch (error) {
    fail(`Unable to read manifest ${absolutePath}: ${error.message}`);
  }
  validateManifest(manifest);
  const workspaceRoot = path.resolve(path.dirname(absolutePath), manifest.workspaceRoot);
  if (!existsSync(workspaceRoot) || !statSync(workspaceRoot).isDirectory()) {
    fail(`Workspace root not found: ${workspaceRoot}`);
  }
  return { manifest, manifestPath: absolutePath, workspaceRoot };
}

function isWithin(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

export function resolveWithin(workspaceRoot, relativePath, label) {
  const candidate = path.resolve(workspaceRoot, validateRelativePath(relativePath, label));
  if (!isWithin(workspaceRoot, candidate)) {
    fail(`${label} resolves outside the workspace root.`);
  }
  if (existsSync(candidate)) {
    const realRoot = realpathSync(workspaceRoot);
    const realCandidate = realpathSync(candidate);
    if (!isWithin(realRoot, realCandidate)) {
      fail(`${label} resolves through a link outside the workspace root.`);
    }
  }
  return candidate;
}

export function resolveTargets(requested, items, label) {
  const values = Array.isArray(requested) ? requested : [requested ?? "all"];
  const normalized = values
    .flatMap((value) => String(value).split(","))
    .map((value) => value.trim())
    .filter(Boolean);
  if (normalized.length === 0 || (normalized.length === 1 && normalized[0] === "all")) {
    return [...items];
  }
  const byId = new Map(items.map((item) => [item.id, item]));
  return normalized.map((id) => {
    const item = byId.get(id);
    if (!item) {
      fail(`Unknown ${label} id: ${id}`);
    }
    return item;
  });
}

export function parseArguments(argv) {
  const options = {
    action: "list",
    targets: ["all"],
    engine: process.env.CONTAINER_ENGINE || "podman",
    sourceTag: "local",
    releaseTag: "",
    manifest: DEFAULT_MANIFEST,
    pipeline: "",
    migrationAction: "apply",
    migrationBaselineThrough: "",
    migrationBaselineConfirmed: false,
    refreshImages: false,
    destroyData: false,
    skipMigrations: false,
    dryRun: false,
    json: false,
  };
  const valueFlags = new Map([
    ["--action", "action"],
    ["--targets", "targets"],
    ["--repos", "targets"],
    ["--engine", "engine"],
    ["--source-tag", "sourceTag"],
    ["--local-tag", "sourceTag"],
    ["--release-tag", "releaseTag"],
    ["--publish-tag", "releaseTag"],
    ["--manifest", "manifest"],
    ["--pipeline", "pipeline"],
    ["--migration-action", "migrationAction"],
    ["--migration-baseline-through", "migrationBaselineThrough"],
  ]);
  const booleanFlags = new Map([
    ["--refresh-images", "refreshImages"],
    ["--destroy-data", "destroyData"],
    ["--skip-migrations", "skipMigrations"],
    ["--migration-baseline-confirm-schema", "migrationBaselineConfirmed"],
    ["--dry-run", "dryRun"],
    ["--json", "json"],
  ]);
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "-h" || argument === "--help") {
      options.help = true;
      continue;
    }
    if (booleanFlags.has(argument)) {
      options[booleanFlags.get(argument)] = true;
      continue;
    }
    const key = valueFlags.get(argument);
    if (!key) {
      fail(`Unknown option: ${argument}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) {
      fail(`Missing value for ${argument}.`);
    }
    options[key] = key === "targets" ? [value] : value;
    index += 1;
  }
  if (!ACTIONS.has(options.action)) {
    fail(`Unknown action: ${options.action}`);
  }
  if (!new Set(["podman", "docker"]).has(options.engine)) {
    fail("Engine must be podman or docker.");
  }
  if (options.action === "pipeline" && !options.pipeline) {
    fail("--pipeline is required for the pipeline action.");
  }
  if (options.action === "pipeline" && options.destroyData) {
    fail("--destroy-data cannot be used with manifest pipelines.");
  }
  if (!new Set(["apply", "baseline", "dry-run", "status"]).has(options.migrationAction)) {
    fail("Migration action must be apply, baseline, dry-run, or status.");
  }
  if (options.migrationAction === "baseline" && !/^\d{4}$/.test(options.migrationBaselineThrough)) {
    fail("Baseline requires --migration-baseline-through with a reviewed four-digit cutoff.");
  }
  if (options.migrationAction === "baseline" && !options.migrationBaselineConfirmed) {
    fail("Baseline requires --migration-baseline-confirm-schema after schema and backup verification.");
  }
  return options;
}

function usage() {
  return `Usage: workspace-helper.mjs [options]

  --action list|sync|build|refresh|migrate|deploy|publish|reset-data|pipeline
  --targets all|id,id,...
  --engine podman|docker
  --source-tag TAG
  --release-tag TAG
  --manifest PATH
  --pipeline NAME
  --migration-action apply|baseline|dry-run|status
  --migration-baseline-through ID
  --migration-baseline-confirm-schema
  --refresh-images
  --destroy-data
  --skip-migrations
  --dry-run
  --json`;
}

function redact(value) {
  return String(value ?? "")
    .replace(/\b(sk-[A-Za-z0-9_-]{16,})\b/g, "[REDACTED]")
    .replace(/((?:API_KEY|TOKEN|PASSWORD|SECRET)\s*[=:]\s*)\S+/gi, "$1[REDACTED]");
}

function redactPayload(value) {
  if (typeof value === "string") return redact(value);
  if (Array.isArray(value)) return value.map(redactPayload);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, redactPayload(item)]));
  }
  return value;
}

function createReporter(json) {
  return (event, data = {}) => {
    const payload = redactPayload({ event, at: new Date().toISOString(), ...data });
    if (json) {
      process.stdout.write(`${JSON.stringify(payload)}\n`);
      return;
    }
    if (payload.message) {
      process.stdout.write(`${payload.message}\n`);
    }
  };
}

function displayCommand(command, args) {
  return [command, ...args].map((value) => JSON.stringify(String(value))).join(" ");
}

function runCommand(command, args, context, { cwd = context.workspaceRoot, env = {}, capture = false, executeDuringDryRun = false } = {}) {
  const rendered = displayCommand(command, args);
  context.report("command.planned", { command, args, cwd, message: `[plan] ${rendered}` });
  if (context.options.dryRun && !executeDuringDryRun) {
    return { stdout: "", stderr: "", status: 0 };
  }
  const shouldCapture = capture || context.options.json;
  const result = spawnSync(command, args, {
    cwd,
    env: { ...process.env, ...env },
    encoding: "utf8",
    stdio: shouldCapture ? "pipe" : "inherit",
    maxBuffer: 10 * 1024 * 1024,
    shell: false,
  });
  if (result.error) {
    fail(`Unable to run ${command}: ${result.error.message}`);
  }
  const stdout = redact(result.stdout || "");
  const stderr = redact(result.stderr || "");
  if (result.status !== 0) {
    context.report("command.failed", {
      command,
      args,
      cwd,
      status: result.status,
      stdout,
      stderr,
      message: `[failed:${result.status}] ${rendered}`,
    });
    fail(`Command failed with exit code ${result.status}: ${rendered}`);
  }
  context.report("command.completed", {
    command,
    args,
    cwd,
    status: result.status,
    ...(context.options.json ? { stdout, stderr } : {}),
    message: `[completed] ${rendered}`,
  });
  return { stdout, stderr, status: result.status };
}

function repositoryPath(repository, context) {
  return resolveWithin(context.workspaceRoot, repository.path, `Repository ${repository.id} path`);
}

function componentPaths(component, context) {
  const repository = context.repositoriesById.get(component.repository);
  const root = repositoryPath(repository, context);
  const resolveComponentPath = (value, label) => {
    const candidate = path.resolve(root, validateRelativePath(value, label));
    if (!isWithin(root, candidate)) {
      fail(`${label} resolves outside repository ${repository.id}.`);
    }
    if (existsSync(candidate)) {
      const realRoot = realpathSync(root);
      const realCandidate = realpathSync(candidate);
      if (!isWithin(realRoot, realCandidate)) {
        fail(`${label} resolves through a link outside repository ${repository.id}.`);
      }
    }
    return candidate;
  };
  return {
    root,
    path: resolveComponentPath(component.path, `Component ${component.id} path`),
    context: resolveComponentPath(component.context, `Component ${component.id} context`),
    dockerfile: resolveComponentPath(component.dockerfile, `Component ${component.id} dockerfile`),
  };
}

function assertExistingPath(candidate, label, kind = "any") {
  if (!existsSync(candidate)) {
    fail(`${label} not found: ${candidate}`);
  }
  const stats = statSync(candidate);
  if (kind === "directory" && !stats.isDirectory()) {
    fail(`${label} is not a directory: ${candidate}`);
  }
  if (kind === "file" && !stats.isFile()) {
    fail(`${label} is not a file: ${candidate}`);
  }
}

function normalizeRemoteUrl(value) {
  const remote = String(value).trim().replace(/[\\/]+$/, "").replace(/\.git$/i, "");
  if (remote.startsWith("git@")) return remote;
  const parsed = new URL(remote);
  const username = parsed.username ? `${parsed.username}@` : "";
  return `${parsed.protocol.toLowerCase()}//${username}${parsed.host.toLowerCase()}${parsed.pathname.replace(/\/$/, "")}`;
}

function syncRepository(repository, context) {
  const target = repositoryPath(repository, context);
  context.report("repository.started", {
    repositoryId: repository.id,
    path: target,
    message: `[${repository.id}] synchronizing ${target}`,
  });
  if (!existsSync(target)) {
    const parent = path.dirname(target);
    assertExistingPath(parent, `Repository ${repository.id} parent`, "directory");
    const realRoot = realpathSync(context.workspaceRoot);
    const realParent = realpathSync(parent);
    if (!isWithin(realRoot, realParent)) {
      fail(`Repository ${repository.id} parent resolves outside the workspace root.`);
    }
    runCommand(
      "git",
      ["clone", "--origin", repository.remoteName, "--branch", repository.branch, "--single-branch", repository.remoteUrl, target],
      context,
    );
    context.plannedRepositories.add(repository.id);
    context.report("repository.completed", {
      repositoryId: repository.id,
      path: target,
      operation: "clone",
      message: `[${repository.id}] cloned ${repository.branch}`,
    });
    return;
  }
  assertExistingPath(path.join(target, ".git"), `Repository ${repository.id} Git metadata`);
  const inspection = { cwd: target, capture: true, executeDuringDryRun: true };
  const dirty = runCommand("git", ["status", "--porcelain=v1"], context, inspection).stdout.trim();
  if (dirty) {
    fail(`Repository ${repository.id} has local changes; sync requires a clean worktree.`);
  }
  const actualRemote = runCommand("git", ["remote", "get-url", repository.remoteName], context, inspection).stdout.trim();
  if (normalizeRemoteUrl(actualRemote) !== normalizeRemoteUrl(repository.remoteUrl)) {
    fail(`Repository ${repository.id} remote ${repository.remoteName} does not match the manifest allowlist.`);
  }
  const branch = runCommand("git", ["branch", "--show-current"], context, inspection).stdout.trim();
  if (branch !== repository.branch) {
    fail(`Repository ${repository.id} is on branch '${branch || "detached"}', expected '${repository.branch}'.`);
  }
  const before = runCommand("git", ["rev-parse", "HEAD"], context, inspection).stdout.trim();
  runCommand("git", ["fetch", "--prune", repository.remoteName, repository.branch], context, { cwd: target });
  runCommand("git", ["merge", "--ff-only", "FETCH_HEAD"], context, { cwd: target });
  if (context.options.dryRun) return;
  const after = runCommand("git", ["rev-parse", "HEAD"], context, { cwd: target, capture: true }).stdout.trim();
  context.report("repository.completed", {
    repositoryId: repository.id,
    path: target,
    operation: before === after ? "unchanged" : "fast-forward",
    before,
    after,
    message: `[${repository.id}] ${before === after ? "already current" : `updated ${before.slice(0, 12)} -> ${after.slice(0, 12)}`}`,
  });
}

function buildComponents(components, context) {
  for (const component of components) {
    const paths = componentPaths(component, context);
    const repositoryIsPlanned = context.plannedRepositories.has(component.repository);
    if (!context.options.dryRun || !repositoryIsPlanned) {
      assertExistingPath(paths.context, `Component ${component.id} context`, "directory");
      assertExistingPath(paths.dockerfile, `Component ${component.id} Dockerfile`, "file");
    }
    const tag = `${component.image}:${context.options.sourceTag}`;
    context.report("component.started", {
      componentId: component.id,
      action: "build",
      image: tag,
      message: `[${component.id}] building ${tag}`,
    });
    runCommand(context.options.engine, ["build", "-f", paths.dockerfile, "-t", tag, paths.context], context);
  }
}

function suitePath() {
  const target = resolveWithin(CORE_ROOT, "myai-suite", "Trusted suite path");
  assertExistingPath(target, "Trusted suite path", "directory");
  return target;
}

function invokeSuiteScript(scriptName, arguments_, context, imageEnvironment = {}) {
  const cwd = suitePath();
  const environment = { CONTAINER_ENGINE: context.options.engine, ...imageEnvironment };
  if (process.platform === "win32") {
    const script = path.join(cwd, `${scriptName}.ps1`);
    assertExistingPath(script, `${scriptName}.ps1`, "file");
    runCommand("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, ...arguments_], context, { cwd, env: environment });
    return;
  }
  const script = path.join(cwd, `${scriptName}.sh`);
  assertExistingPath(script, `${scriptName}.sh`, "file");
  runCommand("bash", [script, ...arguments_], context, { cwd, env: environment });
}

function applyMigrations(context, action = "apply") {
  context.report("migration.started", {
    action,
    message: `[migration] ${action} versioned migrations`,
  });
  const args = process.platform === "win32" ? ["-Action", action] : [action];
  if (action === "baseline") {
    if (process.platform === "win32") args.push("-BaselineThrough", context.options.migrationBaselineThrough);
    else args.push("--baseline-through", context.options.migrationBaselineThrough);
    if (process.platform === "win32") args.push("-BaselineConfirmSchema");
    else args.push("--baseline-confirm-schema");
  }
  invokeSuiteScript("migrate-db", args, context);
  context.report("migration.completed", {
    action,
    message: `[migration] ${action} completed`,
  });
}

function prepareDatabaseAndApplyMigrations(context, profile) {
  const cwd = suitePath();
  context.report("migration.database.started", {
    profile,
    message: `[migration] ensuring PostgreSQL is available for profile ${profile}`,
  });
  runCommand(
    context.options.engine,
    ["compose", "--profile", profile, "up", "-d", "postgres"],
    context,
    { cwd },
  );
  applyMigrations(context);
}

function groupByProfile(components, context) {
  const grouped = new Map();
  for (const component of components) {
    const group = grouped.get(component.profile) ?? [];
    group.push(component);
    grouped.set(component.profile, group);
  }
  return context.manifest.suite.profileOrder
    .filter((profile) => grouped.has(profile))
    .map((profile) => [profile, grouped.get(profile)]);
}

function componentImageEnvironment(components, tag) {
  return Object.fromEntries(
    components.map((component) => [component.imageVariable, `${component.image}:${tag}`]),
  );
}

function refreshComponents(components, context, configuredImages = false) {
  if (configuredImages) {
    const profile = selectedProfile(components);
    context.report("suite.started", {
      action: "refresh",
      profile,
      images: [],
      imageSource: "compose",
      message: `[suite:${profile}] refreshing images resolved by Compose`,
    });
    if (!context.options.skipMigrations) prepareDatabaseAndApplyMigrations(context, profile);
    const args = process.platform === "win32"
      ? ["-ProfileSet", profile, "-SkipMigrations"]
      : ["", profile, "false"];
    invokeSuiteScript("refresh-images", args, context);
    return;
  }
  if (!context.options.skipMigrations) {
    prepareDatabaseAndApplyMigrations(context, selectedProfile(components));
  }
  for (const [profile, group] of groupByProfile(components, context)) {
    const images = group.map((component) => `${component.image}:${context.options.sourceTag}`).join(",");
    const imageEnvironment = componentImageEnvironment(group, context.options.sourceTag);
    context.report("suite.started", {
      action: "refresh",
      profile,
      images: images.split(","),
      imageSource: "selected-components",
      imageOverrides: imageEnvironment,
      message: `[suite:${profile}] refreshing ${images}`,
    });
    const args = process.platform === "win32"
      ? ["-ImagesCsv", images, "-ProfileSet", profile, "-SkipMigrations"]
      : [images, profile, "false"];
    invokeSuiteScript(
      "refresh-images",
      args,
      context,
      imageEnvironment,
    );
  }
}

function selectedProfile(components) {
  const profiles = [...new Set(components.map((component) => component.profile))];
  return profiles.length > 1 ? "all" : profiles[0];
}

function deployComponents(components, context, refreshImages = context.options.refreshImages) {
  const profile = selectedProfile(components);
  const cwd = suitePath();
  context.report("suite.scope", {
    action: "deploy",
    requestedComponents: components.map((component) => component.id),
    effectiveProfile: profile,
    imageOverrides: componentImageEnvironment(components, context.options.sourceTag),
    message: `[suite:${profile}] deploy is profile-scoped`,
  });
  if (context.options.destroyData || context.options.action === "reset-data") {
    context.report("suite.destructive", {
      action: "reset-data",
      profile,
      message: `[suite:${profile}] destroying containers and volumes`,
    });
    runCommand(context.options.engine, ["compose", "--profile", profile, "down", "-v"], context, { cwd });
  }
  if (!context.options.skipMigrations) prepareDatabaseAndApplyMigrations(context, profile);
  const args = process.platform === "win32"
    ? ["-ProfileSet", profile, ...(refreshImages ? ["-RefreshImages"] : []), "-SkipMigrations"]
    : [profile, refreshImages ? "true" : "false", "false"];
  invokeSuiteScript(
    "deploy",
    args,
    context,
    componentImageEnvironment(components, context.options.sourceTag),
  );
}

function publishComponents(components, context) {
  if (!context.options.releaseTag) {
    fail("--release-tag is required for publish.");
  }
  for (const component of components) {
    const source = `${component.image}:${context.options.sourceTag}`;
    const destination = `${component.image}:${context.options.releaseTag}`;
    runCommand(context.options.engine, ["tag", source, destination], context);
    runCommand(context.options.engine, ["push", destination], context);
  }
}

function listManifest(context) {
  const data = {
    manifest: context.manifestPath,
    workspaceRoot: context.workspaceRoot,
    repositories: context.manifest.repositories.map((repository) => ({
      id: repository.id,
      label: repository.label,
      path: repositoryPath(repository, context),
      branch: repository.branch,
      remote: repository.remoteUrl,
    })),
    components: context.manifest.components.map((component) => ({
      id: component.id,
      label: component.label,
      repository: component.repository,
      path: componentPaths(component, context).path,
      image: component.image,
      profile: component.profile,
    })),
    pipelines: Object.keys(context.manifest.pipelines ?? {}),
  };
  if (context.options.json) {
    context.report("manifest.listed", data);
    return;
  }
  process.stdout.write(`Manifest: ${data.manifest}\nWorkspace: ${data.workspaceRoot}\n\nRepositories\n`);
  for (const item of data.repositories) {
    process.stdout.write(`  ${item.id.padEnd(12)} ${item.branch.padEnd(10)} ${item.path}\n`);
  }
  process.stdout.write("\nComponents\n");
  for (const item of data.components) {
    process.stdout.write(`  ${item.id.padEnd(22)} ${item.profile.padEnd(12)} ${item.image}\n`);
  }
  process.stdout.write(`\nPipelines\n  ${data.pipelines.join("\n  ") || "(none)"}\n`);
}

function executeAction(action, targets, context, step = {}) {
  context.report("action.started", { action, targets, message: `[action] ${action}` });
  if (action === "migrate") {
    applyMigrations(context, context.options.migrationAction);
  } else if (action === "sync") {
    for (const repository of resolveTargets(targets, context.manifest.repositories, "repository")) {
      syncRepository(repository, context);
    }
  } else {
    const components = resolveTargets(targets, context.manifest.components, "component");
    if (action === "build") buildComponents(components, context);
    else if (action === "refresh") refreshComponents(components, context, step.configuredImages === true);
    else if (action === "deploy" || action === "reset-data") deployComponents(components, context, step.refreshImages);
    else if (action === "publish") publishComponents(components, context);
    else fail(`Unsupported executable action: ${action}`);
  }
  context.report("action.completed", { action, message: `[action] ${action} completed` });
}

function executePipeline(pipelineId, context) {
  const steps = context.manifest.pipelines?.[pipelineId];
  if (!steps) {
    fail(`Unknown pipeline: ${pipelineId}`);
  }
  context.report("pipeline.started", {
    pipeline: pipelineId,
    steps: steps.length,
    message: `[pipeline:${pipelineId}] starting ${steps.length} steps`,
  });
  for (const [index, step] of steps.entries()) {
    context.report("pipeline.step", {
      pipeline: pipelineId,
      index: index + 1,
      action: step.action,
      message: `[pipeline:${pipelineId}] step ${index + 1}/${steps.length}: ${step.action}`,
    });
    executeAction(step.action, step.targets, context, step);
  }
  context.report("pipeline.completed", {
    pipeline: pipelineId,
    message: `[pipeline:${pipelineId}] completed`,
  });
}

export function createContext(options, loaded) {
  return {
    options,
    ...loaded,
    repositoriesById: new Map(loaded.manifest.repositories.map((repository) => [repository.id, repository])),
    plannedRepositories: new Set(),
    report: createReporter(options.json),
  };
}

export function main(argv = process.argv.slice(2)) {
  const options = parseArguments(argv);
  if (options.help) {
    process.stdout.write(`${usage()}\n`);
    return 0;
  }
  const context = createContext(options, loadManifest(options.manifest));
  if (options.action === "list") {
    listManifest(context);
  } else if (options.action === "pipeline") {
    executePipeline(options.pipeline, context);
  } else {
    executeAction(options.action, options.targets, context);
  }
  return 0;
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  try {
    process.exitCode = main();
  } catch (error) {
    const json = process.argv.includes("--json");
    if (json) {
      process.stderr.write(`${JSON.stringify({ event: "helper.failed", at: new Date().toISOString(), message: redact(error.message) })}\n`);
    } else {
      process.stderr.write(`workspace-helper: ${redact(error.message)}\n`);
    }
    process.exitCode = 1;
  }
}
