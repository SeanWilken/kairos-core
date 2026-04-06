import { spawnSync } from "node:child_process";

const stagedResult = spawnSync("git", ["diff", "--cached", "--name-only"], {
  encoding: "utf8",
  shell: false
});

if (stagedResult.status !== 0) {
  console.log("Skipping changelog check (not a git repository yet).");
  process.exit(0);
}

const files = stagedResult.stdout
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
    "\nChangelog check failed: include an update in CHANGELOG.md for non-doc changes."
  );
  process.exit(1);
}
