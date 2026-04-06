import { spawnSync } from "node:child_process";

const baseRef = process.env.GITHUB_BASE_REF;

if (!baseRef) {
  console.log("Skipping changelog CI check (not a pull request event).");
  process.exit(0);
}

const diffResult = spawnSync(
  "git",
  ["diff", "--name-only", `origin/${baseRef}...HEAD`],
  { encoding: "utf8", shell: false }
);

if (diffResult.status !== 0) {
  console.error("Unable to compute changed files for changelog CI check.");
  process.exit(diffResult.status ?? 1);
}

const files = diffResult.stdout
  .split("\n")
  .map((line) => line.trim())
  .filter(Boolean);

if (files.length === 0) {
  process.exit(0);
}

const docsOnly = files.every((file) =>
  file.startsWith("docs/") ||
  file.startsWith("lab/") ||
  file.startsWith(".github/") ||
  file === "README.md" ||
  file === "CHANGELOG.md"
);

if (docsOnly) {
  process.exit(0);
}

const includesChangelog = files.includes("CHANGELOG.md");
if (!includesChangelog) {
  console.error(
    "Changelog CI check failed: CHANGELOG.md must be updated for non-doc pull requests."
  );
  process.exit(1);
}
