import assert from "node:assert/strict";
import { mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  assertBaselineTargetsSuiteDatabase,
  escapePgPassValue,
  parseArguments,
  parseEnv,
} from "./migration-helper.mjs";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));

test("migration CLI parses canonical actions and paths", () => {
  const options = parseArguments([
    "--action", "dry-run",
    "--suite-path", "myai-suite",
    "--migrations-path", "migrations",
    "--wait-seconds", "30",
    "--restore-tools",
    "--json",
  ]);
  assert.equal(options.action, "dry-run");
  assert.equal(options.restoreTools, true);
  assert.equal(options.json, true);
  assert.equal(options.waitSeconds, 30);
  assert.match(options.suitePath, /myai-suite$/);
  assert.match(options.migrationsPath, /migrations$/);
});

test("migration CLI rejects unsupported actions", () => {
  assert.throws(() => parseArguments(["--action", "reset"]), /Action must be one of/);
  assert.throws(() => parseArguments(["--action", "baseline"]), /Baseline requires --baseline-through/);
  assert.throws(
    () => parseArguments(["--action", "baseline", "--baseline-through", "0026"]),
    /Baseline requires --baseline-confirm-schema/,
  );
  assert.equal(
    parseArguments([
      "--action", "baseline",
      "--baseline-through", "0026",
      "--baseline-confirm-schema",
    ]).baselineThrough,
    "0026",
  );
});

test("suite environment parsing handles comments and quoted values", () => {
  const values = parseEnv(`
# local database
POSTGRES_DB=myai
POSTGRES_USER="operator"
POSTGRES_PASSWORD='not-logged'
`);
  assert.deepEqual(values, {
    POSTGRES_DB: "myai",
    POSTGRES_USER: "operator",
    POSTGRES_PASSWORD: "not-logged",
  });
});

test("numbered migrations have unique sequential identifiers", () => {
  const names = readdirSync(path.resolve(SCRIPT_DIR, "../migrations"))
    .filter((name) => /^\d{4}_.+\.sql$/.test(name))
    .sort();
  const identifiers = names.map((name) => Number.parseInt(name.slice(0, 4), 10));

  assert.equal(new Set(identifiers).size, identifiers.length);
  assert.deepEqual(identifiers, Array.from({ length: identifiers.length }, (_, index) => index + 1));
});

test("baseline target must exactly match the trusted suite database", () => {
  const suitePath = mkdtempSync(path.join(tmpdir(), "myai-migration-test-"));
  try {
    writeFileSync(
      path.join(suitePath, ".env"),
      "POSTGRES_HOST=localhost\nPOSTGRES_PORT=5432\nPOSTGRES_DB=myai\nPOSTGRES_USER=myai\nPOSTGRES_PASSWORD=secret\n",
    );
    const connection = {
      host: "localhost",
      port: "5432",
      database: "myai",
      username: "myai",
      password: "secret",
    };
    assert.doesNotThrow(() => assertBaselineTargetsSuiteDatabase({ suitePath }, connection));
    assert.throws(
      () => assertBaselineTargetsSuiteDatabase({ suitePath }, { ...connection, host: "remote.example" }),
      /exactly match the trusted suite database/,
    );
  } finally {
    rmSync(suitePath, { recursive: true, force: true });
  }
});

test("PostgreSQL passfile values are escaped without exposing a connection-string password", () => {
  assert.equal(escapePgPassValue(String.raw`p:a\\ss`), String.raw`p\:a\\\\ss`);
  assert.throws(() => escapePgPassValue("line\nbreak"), /cannot contain line breaks/);
});
