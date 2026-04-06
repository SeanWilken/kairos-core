import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const mode = process.argv[2] ?? "all";

const scriptFile = fileURLToPath(import.meta.url);
const scriptDir = path.dirname(scriptFile);
const repoRoot = path.resolve(scriptDir, "..");

function resolvePython() {
  const windowsVenvPython = path.join(repoRoot, "backend", ".venv", "Scripts", "python.exe");
  const unixVenvPython = path.join(repoRoot, "backend", ".venv", "bin", "python");

  if (existsSync(windowsVenvPython)) {
    return windowsVenvPython;
  }

  if (existsSync(unixVenvPython)) {
    return unixVenvPython;
  }

  console.error(
    "\nBackend virtual environment Python was not found.\n" +
      "Expected one of:\n" +
      `  - ${windowsVenvPython}\n` +
      `  - ${unixVenvPython}\n\n` +
      "Set up the backend environment first:\n" +
      "  python -m venv backend/.venv\n" +
      "  backend/.venv/Scripts/python.exe -m pip install -e ./backend[dev]"
  );
  process.exit(1);
}

function run(label, command, args) {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    shell: false,
    cwd: repoRoot
  });

  if (result.status !== 0) {
    console.error(`\n${label} failed.`);
    console.error(`Command: ${command} ${args.join(" ")}`);
    process.exit(result.status ?? 1);
  }
}

const python = resolvePython();

if (mode === "lint" || mode === "all") {
  run("Backend lint", python, ["-m", "ruff", "check", "backend"]);
}

if (mode === "test" || mode === "all") {
  run("Backend tests", python, ["-m", "pytest", "backend/tests", "-q"]);
}
