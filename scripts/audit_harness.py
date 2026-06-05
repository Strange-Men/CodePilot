from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
CRITICAL = "critical"
MINOR = "minor"
INFO = "informational"


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    message: str
    documented: Any = None
    actual: Any = None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT_DIR, text=True, capture_output=True, check=False)


def parse_markdown_env_vars(markdown: str) -> set[str]:
    in_section = False
    variables: set[str] = set()
    for line in markdown.splitlines():
        if line.startswith("## Environment Variables"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            match = re.match(r"\|\s*`([A-Z0-9_]+)`\s*\|", line)
            if match:
                variables.add(match.group(1))
    return variables


def parse_settings_env_vars(config_path: Path) -> set[str]:
    tree = ast.parse(read_text(config_path))
    variables: set[str] = set()

    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "Settings":
            continue
        for item in node.body:
            if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
                continue
            field_name = item.target.id
            if field_name == "model_config":
                continue
            alias = None
            if isinstance(item.value, ast.Call):
                for keyword in item.value.keywords:
                    if keyword.arg == "alias" and isinstance(keyword.value, ast.Constant):
                        alias = keyword.value.value
                        break
            variables.add(str(alias or field_name.upper()))

    return variables


def parse_frontend_env_vars(frontend_root: Path) -> set[str]:
    variables: set[str] = set()
    for path in frontend_root.rglob("*"):
        if path.is_dir() or "node_modules" in path.parts or ".next" in path.parts:
            continue
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        variables.update(re.findall(r"process\.env\.([A-Z0-9_]+)", read_text(path)))
    return variables


def parse_env_example_vars(path: Path) -> set[str]:
    variables: set[str] = set()
    for line in read_text(path).splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            variables.add(line.split("=", 1)[0].strip())
    return variables


def parse_requirement_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-r "):
            continue
        if "==" not in stripped:
            continue
        package, version = stripped.split("==", 1)
        package = package.split("[", 1)[0].lower()
        versions[package] = version
    return versions


def parse_package_versions(path: Path) -> dict[str, str]:
    data = json.loads(read_text(path))
    versions: dict[str, str] = {}
    for section in ("dependencies", "devDependencies"):
        versions.update(data.get(section, {}))
    return versions


def parse_ci_run_commands(workflow_path: Path) -> set[str]:
    commands: set[str] = set()
    lines = read_text(workflow_path).splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("run:"):
            continue
        value = stripped.removeprefix("run:").strip()
        if value and value != "|":
            commands.add(value)
            continue
        next_index = index + 1
        while next_index < len(lines):
            next_line = lines[next_index]
            if next_line.startswith("      - name:") or next_line.startswith("      - uses:"):
                break
            command = next_line.strip()
            if command and not command.startswith("#"):
                commands.add(command)
            next_index += 1
    return commands


def parse_documented_ci_commands(release_rules: str) -> set[str]:
    for line in release_rules.splitlines():
        if line.startswith("CI currently enforces "):
            return set(re.findall(r"`([^`]+)`", line))
    return set()


def parse_documented_test_count(testing_md: str) -> int | None:
    match = re.search(r"collected\s+(\d+)\s+tests", testing_md)
    return int(match.group(1)) if match else None


def collect_pytest_count() -> tuple[int | None, str]:
    completed = run_command(["pytest", "--collect-only", "-q"])
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    match = re.search(r"(\d+)\s+tests?\s+collected", output)
    if not match:
        return None, output
    return int(match.group(1)), output


def parse_project_context_versions(project_context: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    in_section = False
    for line in project_context.splitlines():
        if line.startswith("## Technology Stack"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        if not line.startswith("| "):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        if len(cells) < 3 or cells[0] in {"Layer", "-------"}:
            continue
        versions[cells[1]] = cells[2]
    return versions


def parse_testing_tool_versions(testing_md: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    in_section = False
    for line in testing_md.splitlines():
        if line.startswith("## Tooling Configuration"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        if not line.startswith("| "):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"Tool", "------"}:
            continue
        versions[cells[0]] = cells[1]
    return versions


def parse_ci_python_version(workflow_path: Path) -> str | None:
    match = re.search(r'python-version:\s*"([^"]+)"', read_text(workflow_path))
    return match.group(1) if match else None


def parse_ci_node_version(workflow_path: Path) -> str | None:
    match = re.search(r'node-version:\s*"([^"]+)"', read_text(workflow_path))
    return match.group(1) if match else None


def normalize_python_runtime(runtime_text: str) -> str:
    return runtime_text.strip().removeprefix("python-")


def check_test_count() -> tuple[dict[str, Any], list[Finding]]:
    testing_md = read_text(ROOT_DIR / ".harness" / "TESTING.md")
    documented = parse_documented_test_count(testing_md)
    actual, raw_output = collect_pytest_count()
    findings: list[Finding] = []
    if documented is None:
        findings.append(Finding("test_count", CRITICAL, "TESTING.md does not document pytest collection count."))
    elif actual is None:
        findings.append(
            Finding("test_count", CRITICAL, "Could not determine pytest collection count.", documented, raw_output)
        )
    elif documented != actual:
        findings.append(
            Finding(
                "test_count",
                CRITICAL,
                "TESTING.md test count does not match pytest collection.",
                documented,
                actual,
            )
        )
    return {"documented": documented, "actual": actual}, findings


def check_env_vars() -> tuple[dict[str, Any], list[Finding]]:
    project_context = read_text(ROOT_DIR / ".harness" / "PROJECT_CONTEXT.md")
    documented = parse_markdown_env_vars(project_context)
    actual = parse_settings_env_vars(ROOT_DIR / "backend" / "core" / "config.py")
    actual |= parse_frontend_env_vars(ROOT_DIR / "frontend")
    env_example = parse_env_example_vars(ROOT_DIR / ".env.example")

    findings: list[Finding] = []
    missing_from_docs = sorted(actual - documented)
    if missing_from_docs:
        findings.append(
            Finding(
                "env_vars",
                CRITICAL,
                "Environment variables used by code are missing from PROJECT_CONTEXT.md.",
                sorted(documented),
                missing_from_docs,
            )
        )

    missing_from_example = sorted(actual - env_example)
    if missing_from_example:
        findings.append(
            Finding(
                "env_vars",
                CRITICAL,
                "Environment variables used by code are missing from .env.example.",
                sorted(env_example),
                missing_from_example,
            )
        )

    extra_documented = sorted(documented - actual - {"PYTHON_VERSION"})
    if extra_documented:
        findings.append(
            Finding(
                "env_vars",
                MINOR,
                "PROJECT_CONTEXT.md documents variables not detected in code usage.",
                extra_documented,
                sorted(actual),
            )
        )

    return {
        "documented": sorted(documented),
        "actual_code_usage": sorted(actual),
        "env_example": sorted(env_example),
    }, findings


def check_ci_gates() -> tuple[dict[str, Any], list[Finding]]:
    workflow_path = ROOT_DIR / ".github" / "workflows" / "ci.yml"
    release_rules = read_text(ROOT_DIR / ".harness" / "RELEASE_RULES.md")
    documented = parse_documented_ci_commands(release_rules)
    actual = parse_ci_run_commands(workflow_path)

    required_documented = {
        "ruff check .",
        "pytest",
        "npm run build",
        "python scripts/audit_harness.py --output harness-audit.json",
    }
    findings: list[Finding] = []
    missing_doc = sorted(required_documented - documented)
    if missing_doc:
        findings.append(
            Finding(
                "ci_gates",
                CRITICAL,
                "RELEASE_RULES.md is missing documented CI gates.",
                sorted(documented),
                missing_doc,
            )
        )

    missing_actual = sorted(required_documented - actual)
    if missing_actual:
        findings.append(
            Finding(
                "ci_gates",
                CRITICAL,
                "GitHub CI workflow is missing required gates.",
                sorted(actual),
                missing_actual,
            )
        )

    return {"documented": sorted(documented), "actual": sorted(actual)}, findings


def check_versions() -> tuple[dict[str, Any], list[Finding]]:
    project_context = read_text(ROOT_DIR / ".harness" / "PROJECT_CONTEXT.md")
    testing_md = read_text(ROOT_DIR / ".harness" / "TESTING.md")
    documented = parse_project_context_versions(project_context) | parse_testing_tool_versions(testing_md)

    backend_versions = parse_requirement_versions(ROOT_DIR / "backend" / "requirements.txt")
    dev_versions = parse_requirement_versions(ROOT_DIR / "backend" / "requirements-dev.txt")
    frontend_versions = parse_package_versions(ROOT_DIR / "frontend" / "package.json")

    actual = {
        "Next.js": frontend_versions.get("next"),
        "React / React DOM": frontend_versions.get("react"),
        "TypeScript": frontend_versions.get("typescript"),
        "Tailwind CSS": frontend_versions.get("tailwindcss"),
        "FastAPI": backend_versions.get("fastapi"),
        "Uvicorn": backend_versions.get("uvicorn"),
        "Pydantic": backend_versions.get("pydantic"),
        "pydantic-settings": backend_versions.get("pydantic-settings"),
        "httpx": backend_versions.get("httpx"),
        "tree-sitter": backend_versions.get("tree-sitter"),
        "tree-sitter-language-pack": backend_versions.get("tree-sitter-language-pack"),
        "pytest": dev_versions.get("pytest"),
        "ruff": dev_versions.get("ruff"),
        "Python runtime": normalize_python_runtime(read_text(ROOT_DIR / ".python-version")),
        "runtime.txt": normalize_python_runtime(read_text(ROOT_DIR / "runtime.txt")),
        "CI Python": parse_ci_python_version(ROOT_DIR / ".github" / "workflows" / "ci.yml"),
        "Node runtime": parse_ci_node_version(ROOT_DIR / ".github" / "workflows" / "ci.yml"),
    }

    findings: list[Finding] = []
    comparisons = {
        "Next.js": ("Next.js",),
        "React / React DOM": ("React / React DOM",),
        "TypeScript": ("TypeScript",),
        "Tailwind CSS": ("Tailwind CSS",),
        "FastAPI": ("FastAPI",),
        "Uvicorn": ("Uvicorn",),
        "httpx": ("HTTP client", "httpx"),
        "pytest": ("pytest",),
        "ruff": ("ruff",),
        "Python runtime": ("Python runtime", "CPython"),
        "Node runtime": ("Node runtime", "Node.js"),
    }
    for actual_key, documented_keys in comparisons.items():
        documented_value = next((documented[key] for key in documented_keys if key in documented), None)
        actual_value = actual.get(actual_key)
        if documented_value and actual_value and documented_value != actual_value:
            findings.append(
                Finding(
                    "versions",
                    CRITICAL,
                    f"Documented version for {actual_key} does not match repository reality.",
                    documented_value,
                    actual_value,
                )
            )

    documented_validation = documented.get("Pydantic / pydantic-settings")
    if documented_validation:
        expected = f"{actual['Pydantic']} / {actual['pydantic-settings']}"
        if documented_validation != expected:
            findings.append(
                Finding(
                    "versions",
                    CRITICAL,
                    "Documented Pydantic versions do not match requirements.",
                    documented_validation,
                    expected,
                )
            )

    documented_parser = documented.get("tree-sitter / tree-sitter-language-pack")
    if documented_parser:
        expected = f"{actual['tree-sitter']} / {actual['tree-sitter-language-pack']}"
        if documented_parser != expected:
            findings.append(
                Finding(
                    "versions",
                    CRITICAL,
                    "Documented parser versions do not match requirements.",
                    documented_parser,
                    expected,
                )
            )

    python_runtime = actual["Python runtime"]
    runtime_txt = actual["runtime.txt"]
    if python_runtime != runtime_txt:
        findings.append(Finding("versions", CRITICAL, "Python runtime files disagree.", python_runtime, runtime_txt))

    return {"documented": documented, "actual": actual}, findings


def build_report() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    findings: list[Finding] = []

    for name, check in (
        ("test_count", check_test_count),
        ("env_vars", check_env_vars),
        ("ci_gates", check_ci_gates),
        ("versions", check_versions),
    ):
        details, check_findings = check()
        checks[name] = details
        findings.extend(check_findings)

    counts = {
        CRITICAL: sum(1 for finding in findings if finding.severity == CRITICAL),
        MINOR: sum(1 for finding in findings if finding.severity == MINOR),
        INFO: sum(1 for finding in findings if finding.severity == INFO),
    }
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "fail" if counts[CRITICAL] else "pass",
        "summary": {
            "findings": len(findings),
            "critical": counts[CRITICAL],
            "minor": counts[MINOR],
            "informational": counts[INFO],
        },
        "checks": checks,
        "findings": [asdict(finding) for finding in findings],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Harness documentation against repository reality.")
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    output = json.dumps(report, indent=2, sort_keys=True)
    print(output)
    if args.output:
        output_path = args.output if args.output.is_absolute() else ROOT_DIR / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
