from __future__ import annotations

from pathlib import Path

from backend.parsers.javascript_parser import JavaScriptParser, TypeScriptParser


def test_parse_javascript_extracts_imports_classes_functions_and_exports(temp_repo: Path) -> None:
    source = temp_repo / "src" / "index.js"
    source.parent.mkdir()
    source.write_text(
        "/** Public API module. */\n"
        "import React from 'react';\n"
        "const fs = require('fs');\n\n"
        "export class Widget {}\n"
        "export function renderWidget() { return new Widget(); }\n"
        "export const createWidget = () => new Widget();\n"
        "export { createWidget as buildWidget };\n",
        encoding="utf-8",
    )

    parsed = JavaScriptParser().parse_file(temp_repo, source)

    assert parsed.path == "src/index.js"
    assert "import React from 'react';" in parsed.imports
    assert "require('fs')" in parsed.imports
    assert parsed.classes == ["Widget"]
    assert parsed.functions == ["renderWidget", "createWidget"]
    assert parsed.exported_symbols == ["Widget", "renderWidget", "createWidget", "buildWidget"]
    assert parsed.first_docstring == "Public API module."


def test_parse_typescript_extracts_typescript_exports(temp_repo: Path) -> None:
    source = temp_repo / "app" / "service.tsx"
    source.parent.mkdir()
    source.write_text(
        "// Service facade\n"
        "import type { Request } from './types';\n\n"
        "export interface ServiceRequest extends Request {}\n"
        "export type ServiceResult = { ok: boolean };\n"
        "export enum ServiceState { Ready }\n"
        "export default function ServiceView() { return null; }\n"
        "const internalHelper = function () { return true; };\n",
        encoding="utf-8",
    )

    parsed = TypeScriptParser().parse_file(temp_repo, source)

    assert parsed.path == "app/service.tsx"
    assert "import type { Request } from './types';" in parsed.imports
    assert parsed.functions == ["ServiceView", "internalHelper"]
    assert parsed.exported_symbols == ["ServiceRequest", "ServiceResult", "ServiceState", "ServiceView"]
    assert parsed.first_docstring == "Service facade"


def test_javascript_discovery_filters_supported_files_and_ignored_dirs(temp_repo: Path) -> None:
    kept = temp_repo / "src" / "index.jsx"
    ignored = temp_repo / "node_modules" / "pkg" / "index.js"
    unsupported = temp_repo / "README.md"
    kept.parent.mkdir(parents=True)
    ignored.parent.mkdir(parents=True)
    kept.write_text("export const app = () => null;\n", encoding="utf-8")
    ignored.write_text("module.exports = {}\n", encoding="utf-8")
    unsupported.write_text("# docs\n", encoding="utf-8")

    files, total, skipped = JavaScriptParser().discover_files(temp_repo, max_files=10, max_file_size_bytes=1000)

    assert files == [kept]
    assert total == 1
    assert skipped == 0


def test_typescript_discovery_respects_max_files_and_prioritizes_entrypoints(temp_repo: Path) -> None:
    for name in ["z.ts", "src/index.ts", "tests/component.test.tsx"]:
        path = temp_repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("export const value = 1;\n", encoding="utf-8")

    files, total, skipped = TypeScriptParser().discover_files(temp_repo, max_files=2, max_file_size_bytes=1000)

    assert [path.relative_to(temp_repo).as_posix() for path in files] == ["src/index.ts", "z.ts"]
    assert total == 3
    assert skipped == 1
