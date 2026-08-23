import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  loadManifest,
  parseArguments,
  resolveTargets,
  resolveWithin,
  validateManifest,
} from "./workspace-helper.mjs";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const MANIFEST_PATH = path.join(SCRIPT_DIR, "workspace-manifest.v1.json");

test("default workspace manifest is valid and resolves the expected topology", () => {
  const loaded = loadManifest(MANIFEST_PATH);

  assert.equal(loaded.manifest.schemaVersion, "1.0");
  assert.equal(loaded.manifest.repositories.length, 5);
  assert.equal(loaded.manifest.components.length, 7);
  assert.deepEqual(Object.keys(loaded.manifest.pipelines), [
    "development-redeploy",
    "images-redeploy",
  ]);
  assert.equal(loaded.manifest.pipelines["images-redeploy"][0].configuredImages, true);
  assert.equal(
    resolveWithin(loaded.workspaceRoot, "kairos-core", "Core path"),
    path.resolve(SCRIPT_DIR, ".."),
  );
});

test("target resolution preserves manifest order for all and explicit order otherwise", () => {
  const items = [{ id: "alpha" }, { id: "beta" }, { id: "gamma" }];

  assert.deepEqual(resolveTargets(["all"], items, "component"), items);
  assert.deepEqual(resolveTargets(["gamma,alpha"], items, "component"), [items[2], items[0]]);
  assert.throws(() => resolveTargets(["missing"], items, "component"), /Unknown component id/);
});

test("manifest validation rejects duplicate IDs and arbitrary pipeline actions", () => {
  const loaded = loadManifest(MANIFEST_PATH);
  const duplicate = structuredClone(loaded.manifest);
  duplicate.repositories.push(structuredClone(duplicate.repositories[0]));
  assert.throws(() => validateManifest(duplicate), /Duplicate repository id/);

  const arbitraryCommand = structuredClone(loaded.manifest);
  arbitraryCommand.pipelines.unsafe = [{ action: "command", targets: "all" }];
  assert.throws(() => validateManifest(arbitraryCommand), /unsupported action/);
});

test("manifest validation rejects traversal and unknown component repositories", () => {
  const loaded = loadManifest(MANIFEST_PATH);
  const traversal = structuredClone(loaded.manifest);
  traversal.repositories[0].path = "../outside";
  assert.throws(() => validateManifest(traversal), /without '..' segments/);

  const unknownRepository = structuredClone(loaded.manifest);
  unknownRepository.components[0].repository = "missing";
  assert.throws(() => validateManifest(unknownRepository), /unknown repository/);

  const absoluteRoot = structuredClone(loaded.manifest);
  absoluteRoot.workspaceRoot = path.resolve(SCRIPT_DIR, "../..");
  assert.throws(() => validateManifest(absoluteRoot), /relative to the manifest/);
});

test("manifest validation rejects URL credentials and unknown properties", () => {
  const loaded = loadManifest(MANIFEST_PATH);
  const credentialUrl = structuredClone(loaded.manifest);
  credentialUrl.repositories[0].remoteUrl = "https://token@github.com/myAI-Tech/core.git";
  assert.throws(() => validateManifest(credentialUrl), /cannot contain credentials/);

  const extraProperty = structuredClone(loaded.manifest);
  extraProperty.components[0].command = "echo unsafe";
  assert.throws(() => validateManifest(extraProperty), /unsupported property 'command'/);

  const redirectedSuite = structuredClone(loaded.manifest);
  redirectedSuite.suite.path = "untrusted/scripts";
  assert.throws(() => validateManifest(redirectedSuite), /unsupported property 'path'/);
});

test("CLI parsing supports pipeline, dry-run, JSON, and custom manifests", () => {
  const options = parseArguments([
    "--action", "pipeline",
    "--pipeline", "development-redeploy",
    "--migration-action", "status",
    "--manifest", "custom.json",
    "--engine", "docker",
    "--targets", "core-api,core-frontend",
    "--source-tag", "dev",
    "--release-tag", "0.2.0",
    "--dry-run",
    "--skip-migrations",
    "--json",
  ]);

  assert.equal(options.action, "pipeline");
  assert.equal(options.pipeline, "development-redeploy");
  assert.equal(options.migrationAction, "status");
  assert.equal(options.manifest, "custom.json");
  assert.equal(options.engine, "docker");
  assert.deepEqual(options.targets, ["core-api,core-frontend"]);
  assert.equal(options.sourceTag, "dev");
  assert.equal(options.releaseTag, "0.2.0");
  assert.throws(
    () => parseArguments(["--action", "migrate", "--migration-action", "baseline"]),
    /Baseline requires --migration-baseline-through/,
  );
  assert.equal(options.dryRun, true);
  assert.equal(options.skipMigrations, true);
  assert.equal(options.json, true);
  const compatibility = parseArguments([
    "--action", "publish",
    "--repos", "core-api",
    "--local-tag", "local",
    "--publish-tag", "0.2.0",
  ]);
  assert.deepEqual(compatibility.targets, ["core-api"]);
  assert.equal(compatibility.sourceTag, "local");
  assert.equal(compatibility.releaseTag, "0.2.0");
  assert.throws(
    () => parseArguments(["--action", "pipeline", "--pipeline", "images-redeploy", "--destroy-data"]),
    /cannot be used with manifest pipelines/,
  );
});
