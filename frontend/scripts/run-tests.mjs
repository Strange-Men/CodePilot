import { spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const testsRoot = join(frontendRoot, "tests");
const testFilePattern = /\.(?:test|spec)\.[cm]?[jt]sx?$/;

function discoverTests(directory) {
  return readdirSync(directory, { withFileTypes: true })
    .flatMap((entry) => {
      const path = join(directory, entry.name);
      return entry.isDirectory() ? discoverTests(path) : [path];
    })
    .filter((path) => testFilePattern.test(path))
    .sort();
}

const testFiles = discoverTests(testsRoot).map((path) => relative(frontendRoot, path));
if (testFiles.length === 0) {
  console.error("No frontend test files were found.");
  process.exit(1);
}

const result = spawnSync(
  process.execPath,
  ["--import", "tsx", "--test", ...testFiles],
  {
    cwd: frontendRoot,
    stdio: "inherit"
  }
);

if (result.error) {
  throw result.error;
}
process.exit(result.status ?? 1);
