#!/usr/bin/env node

import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { createConnection } from "node:net";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const CORE_ROOT = path.resolve(SCRIPT_DIR, "..");
const ACTIONS = new Set(["apply", "baseline", "dry-run", "status"]);

function fail(message) {
  throw new Error(message);
}

export function parseArguments(argv) {
  const options = {
    action: "apply",
    suitePath: path.join(CORE_ROOT, "myai-suite"),
    migrationsPath: path.join(CORE_ROOT, "migrations"),
    baselineThrough: "",
    baselineConfirmed: false,
    restoreTools: false,
    waitSeconds: 60,
    json: false,
  };
  const values = new Map([
    ["--action", "action"],
    ["--suite-path", "suitePath"],
    ["--migrations-path", "migrationsPath"],
    ["--baseline-through", "baselineThrough"],
    ["--wait-seconds", "waitSeconds"],
  ]);
  const switches = new Map([
    ["--restore-tools", "restoreTools"],
    ["--baseline-confirm-schema", "baselineConfirmed"],
    ["--json", "json"],
  ]);
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "-h" || argument === "--help") {
      options.help = true;
      continue;
    }
    if (switches.has(argument)) {
      options[switches.get(argument)] = true;
      continue;
    }
    const key = values.get(argument);
    if (!key) fail(`Unknown option: ${argument}`);
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) fail(`Missing value for ${argument}.`);
    options[key] = value;
    index += 1;
  }
  if (!ACTIONS.has(options.action)) {
    fail(`Action must be one of: ${[...ACTIONS].join(", ")}.`);
  }
  if (options.action === "baseline" && !/^\d{4}$/.test(options.baselineThrough)) {
    fail("Baseline requires --baseline-through with a reviewed four-digit migration cutoff.");
  }
  if (options.action === "baseline" && !options.baselineConfirmed) {
    fail("Baseline requires --baseline-confirm-schema after schema and backup verification.");
  }
  options.waitSeconds = Number.parseInt(String(options.waitSeconds), 10);
  if (!Number.isInteger(options.waitSeconds) || options.waitSeconds < 0 || options.waitSeconds > 600) {
    fail("--wait-seconds must be an integer from 0 to 600.");
  }
  options.suitePath = path.resolve(options.suitePath);
  options.migrationsPath = path.resolve(options.migrationsPath);
  return options;
}

function usage() {
  return `Usage: migration-helper.mjs [options]

  --action apply|baseline|dry-run|status
  --suite-path PATH
  --migrations-path PATH
  --baseline-through ID
  --baseline-confirm-schema
  --wait-seconds SECONDS
  --restore-tools
  --json`;
}

export function parseEnv(content) {
  const values = {};
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const separator = line.indexOf("=");
    if (separator < 1) continue;
    const key = line.slice(0, separator).trim();
    let value = line.slice(separator + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

export function resolveConnection(options, environment = process.env) {
  const envPath = path.join(options.suitePath, ".env");
  if (!existsSync(envPath)) fail(`Suite environment file not found: ${envPath}`);
  const fileValues = parseEnv(readFileSync(envPath, "utf8"));
  const value = (key, fallback = "") => String(environment[key] || fileValues[key] || fallback).trim();
  const connection = {
    host: value("POSTGRES_HOST", "localhost"),
    port: value("POSTGRES_PORT", "5432"),
    database: value("POSTGRES_DB", "myai"),
    username: value("POSTGRES_USER", "myai"),
    password: value("POSTGRES_PASSWORD"),
  };
  if (!connection.password) fail("POSTGRES_PASSWORD is required through the process environment or suite .env file.");
  return connection;
}

function quoteConnectionValue(value) {
  return `"${String(value).replaceAll('"', '""')}"`;
}

function report(json, event, data) {
  const payload = { event, at: new Date().toISOString(), ...data };
  if (json) process.stdout.write(`${JSON.stringify(payload)}\n`);
  else if (payload.message) process.stdout.write(`${payload.message}\n`);
}

function run(command, args, options, { cwd = CORE_ROOT, password = "" } = {}) {
  const result = spawnSync(command, args, {
    cwd,
    env: process.env,
    encoding: "utf8",
    stdio: "pipe",
    shell: false,
    maxBuffer: 10 * 1024 * 1024,
  });
  if (result.error) fail(`Unable to run ${command}: ${result.error.message}`);
  const redact = (text) => String(text || "").split(password).join("[REDACTED]");
  if (result.status !== 0) {
    if (options.json) {
      report(true, "migration.command.failed", {
        status: result.status,
        stdout: redact(result.stdout),
        stderr: redact(result.stderr),
      });
    }
    fail(`Migration command failed with exit code ${result.status}.`);
  }
  if (!options.json) {
    if (result.stdout) process.stdout.write(redact(result.stdout));
    if (result.stderr) process.stderr.write(redact(result.stderr));
  }
  return { stdout: redact(result.stdout), stderr: redact(result.stderr) };
}

function runComposeQuery(sql, options) {
  const envValues = parseEnv(readFileSync(path.join(options.suitePath, ".env"), "utf8"));
  const engine = String(process.env.CONTAINER_ENGINE || envValues.CONTAINER_ENGINE || "podman");
  const command = 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$MIGRATION_QUERY"';
  const result = spawnSync(
    engine,
    ["compose", "exec", "-T", "-e", `MIGRATION_QUERY=${sql}`, "postgres", "sh", "-lc", command],
    {
      cwd: options.suitePath,
      env: process.env,
      encoding: "utf8",
      stdio: "pipe",
      shell: false,
      maxBuffer: 1024 * 1024,
    },
  );
  if (result.error || result.status !== 0) {
    fail("Unable to verify the legacy database before baseline.");
  }
  return String(result.stdout || "").trim();
}

function suiteDatabaseConnection(options) {
  const suiteEnvironment = parseEnv(readFileSync(path.join(options.suitePath, ".env"), "utf8"));
  return {
    host: suiteEnvironment.POSTGRES_HOST ?? "localhost",
    port: suiteEnvironment.POSTGRES_PORT ?? "5432",
    database: suiteEnvironment.POSTGRES_DB ?? "myai",
    username: suiteEnvironment.POSTGRES_USER ?? "myai",
    password: suiteEnvironment.POSTGRES_PASSWORD ?? "",
  };
}

function targetsSuiteDatabase(options, connection) {
  const expected = suiteDatabaseConnection(options);
  return Object.keys(expected).every((key) => connection[key] === expected[key]);
}

export function assertBaselineTargetsSuiteDatabase(options, connection) {
  const expected = suiteDatabaseConnection(options);
  if (Object.keys(expected).some((key) => connection[key] !== expected[key])) {
    fail("Baseline requires the resolved target to exactly match the trusted suite database; remove connection overrides.");
  }
}

export function escapePgPassValue(value) {
  const text = String(value);
  if (text.includes("\n") || text.includes("\r")) fail("Database credentials cannot contain line breaks.");
  return text.replaceAll("\\", "\\\\").replaceAll(":", "\\:");
}

async function waitForDatabase(connection, options) {
  if (options.waitSeconds === 0) return;
  const deadline = Date.now() + options.waitSeconds * 1000;
  report(options.json, "migration.database.waiting", {
    host: connection.host,
    port: connection.port,
    waitSeconds: options.waitSeconds,
    message: `[migration] waiting for ${connection.host}:${connection.port}`,
  });
  while (Date.now() < deadline) {
    const connected = await new Promise((resolve) => {
      const socket = createConnection({ host: connection.host, port: Number(connection.port) });
      socket.setTimeout(1000);
      socket.once("connect", () => {
        socket.destroy();
        resolve(true);
      });
      socket.once("error", () => resolve(false));
      socket.once("timeout", () => {
        socket.destroy();
        resolve(false);
      });
    });
    if (connected) {
      if (!targetsSuiteDatabase(options, connection)) return;
      try {
        if (runComposeQuery("SELECT 1;", options) === "1") return;
      } catch {
        // PostgreSQL may be listening before it accepts authenticated queries.
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  fail(`Database did not become reachable within ${options.waitSeconds} seconds.`);
}

export async function main(argv = process.argv.slice(2)) {
  const options = parseArguments(argv);
  if (options.help) {
    process.stdout.write(`${usage()}\n`);
    return 0;
  }
  if (!existsSync(options.migrationsPath) || !statSync(options.migrationsPath).isDirectory()) {
    fail(`Migrations directory not found: ${options.migrationsPath}`);
  }
  const connection = resolveConnection(options);
  await waitForDatabase(connection, options);
  if (options.restoreTools) {
    report(options.json, "migration.tools.restore.started", { message: "Restoring locked .NET tools..." });
    run("dotnet", ["tool", "restore"], options);
  }
  let temporaryBaselineRoot = "";
  let effectiveMigrationsPath = options.migrationsPath;
  if (options.action === "baseline") {
    assertBaselineTargetsSuiteDatabase(options, connection);
    temporaryBaselineRoot = mkdtempSync(path.join(tmpdir(), "myai-grate-baseline-"));
    effectiveMigrationsPath = path.join(temporaryBaselineRoot, "migrations");
    mkdirSync(effectiveMigrationsPath);
    const selected = readdirSync(options.migrationsPath)
      .filter((name) => name.toLowerCase().endsWith(".sql"))
      .filter((name) => /^\d{4}_/.test(name))
      .filter((name) => name.slice(0, 4) <= options.baselineThrough)
      .sort();
    const exactCutoff = selected.some((name) => name.startsWith(`${options.baselineThrough}_`));
    if (!exactCutoff) {
      rmSync(temporaryBaselineRoot, { recursive: true, force: true });
      fail(`No migration exactly matches baseline cutoff ${options.baselineThrough}.`);
    }
    if (selected.length === 0) {
      rmSync(temporaryBaselineRoot, { recursive: true, force: true });
      fail(`No migrations found through ${options.baselineThrough}.`);
    }
    for (const name of selected) {
      cpSync(path.join(options.migrationsPath, name), path.join(effectiveMigrationsPath, name), {
        recursive: false,
        force: false,
      });
    }
    const ledgerExists = runComposeQuery(
      "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'grate');",
      options,
    );
    if (ledgerExists === "t") {
      rmSync(temporaryBaselineRoot, { recursive: true, force: true });
      fail("Baseline is not allowed after the Grate ledger has been created.");
    }
    const applicationTableCount = Number.parseInt(
      runComposeQuery(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';",
        options,
      ),
      10,
    );
    if (!Number.isInteger(applicationTableCount) || applicationTableCount === 0) {
      rmSync(temporaryBaselineRoot, { recursive: true, force: true });
      fail("Baseline requires a verified non-empty legacy application schema.");
    }
  }
  const temporaryCredentialRoot = mkdtempSync(path.join(tmpdir(), "myai-grate-credentials-"));
  try {
    const passfile = path.join(temporaryCredentialRoot, "pgpass");
    writeFileSync(
      passfile,
      [connection.host, connection.port, connection.database, connection.username, connection.password]
        .map(escapePgPassValue)
        .join(":") + "\n",
      { encoding: "utf8", mode: 0o600 },
    );
    const connectionString = [
      `Host=${quoteConnectionValue(connection.host)}`,
      `Port=${quoteConnectionValue(connection.port)}`,
      `Database=${quoteConnectionValue(connection.database)}`,
      `Username=${quoteConnectionValue(connection.username)}`,
      `Passfile=${quoteConnectionValue(passfile)}`,
    ].join(";");
    const migrationsRoot = path.dirname(effectiveMigrationsPath);
    const migrationsFolder = path.basename(effectiveMigrationsPath);
    const args = [
      "grate",
      "--connstring", connectionString,
      "--dt", "PostgreSQL",
      "--sqlfilesdirectory", migrationsRoot,
      "--folders", `up=${migrationsFolder}`,
      "--schema", "grate",
      "--noninteractive",
      "--create", "false",
      "--transaction",
    ];
    if (options.action === "baseline") args.push("--baseline");
    if (options.action === "dry-run") args.push("--dryrun");
    if (options.action === "status") args.push("--isuptodate");
    report(options.json, "migration.started", {
      action: options.action,
      host: connection.host,
      port: connection.port,
      database: connection.database,
      migrationsPath: options.migrationsPath,
      message: `[migration] ${options.action} ${connection.database}@${connection.host}:${connection.port}`,
    });
    const result = run("dotnet", args, options, { cwd: CORE_ROOT, password: connection.password });
    report(options.json, "migration.completed", {
      action: options.action,
      baselineThrough: options.baselineThrough || undefined,
      stdout: options.json ? result.stdout : undefined,
      stderr: options.json ? result.stderr : undefined,
      message: `[migration] ${options.action} completed`,
    });
  } finally {
    if (temporaryBaselineRoot) rmSync(temporaryBaselineRoot, { recursive: true, force: true });
    rmSync(temporaryCredentialRoot, { recursive: true, force: true });
  }
  return 0;
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  main().then((code) => {
    process.exitCode = code;
  }).catch((error) => {
    const json = process.argv.includes("--json");
    const payload = { event: "migration.failed", at: new Date().toISOString(), message: error.message };
    process.stderr.write(json ? `${JSON.stringify(payload)}\n` : `migration-helper: ${error.message}\n`);
    process.exitCode = 1;
  });
}
