from __future__ import annotations

from backend.parsers.base import ParsedSourceFile
from backend.services.dependency_graph import DependencyGraph


def parsed_file(path: str, *imports: str) -> ParsedSourceFile:
    return ParsedSourceFile(
        path=path,
        classes=[],
        functions=[],
        imports=[],
        first_docstring=None,
        dependency_imports=list(imports),
    )


def test_python_dependency_graph_resolves_imports_and_calculates_metrics() -> None:
    graph = DependencyGraph("python").build(
        [
            parsed_file("app.py", "services.runner"),
            parsed_file("services/runner.py", ".helpers", "models.data"),
            parsed_file("services/helpers.py", ".runner"),
            parsed_file("models/data.py"),
            parsed_file("orphan.py"),
        ]
    )

    assert graph.dependencies["app.py"] == ("services/runner.py",)
    assert graph.dependencies["services/runner.py"] == (
        "models/data.py",
        "services/helpers.py",
    )
    assert graph.fan_in["services/runner.py"] == 2
    assert graph.fan_out["services/runner.py"] == 2
    assert graph.fan_in["models/data.py"] == 1
    assert graph.cycles == (("services/helpers.py", "services/runner.py"),)
    assert graph.hub_files[0] == "services/runner.py"
    assert graph.orphan_files == ("app.py", "orphan.py")


def test_python_dependency_graph_accepts_raw_absolute_and_relative_import_statements() -> None:
    graph = DependencyGraph("python").build(
        [
            ParsedSourceFile(
                path="pkg/main.py",
                classes=[],
                functions=[],
                imports=["from pkg import service", "from . import helper"],
                first_docstring=None,
            ),
            parsed_file("pkg/service.py"),
            parsed_file("pkg/helper.py"),
        ]
    )

    assert graph.dependencies["pkg/main.py"] == ("pkg/helper.py", "pkg/service.py")


def test_typescript_dependency_graph_resolves_relative_files_and_index_modules() -> None:
    graph = DependencyGraph("typescript").build(
        [
            parsed_file("src/main.ts", "./service"),
            parsed_file("src/service.ts", "./utils"),
            parsed_file("src/utils/index.ts", "../service"),
            parsed_file("src/orphan.ts"),
        ]
    )

    assert graph.dependencies["src/main.ts"] == ("src/service.ts",)
    assert graph.dependencies["src/service.ts"] == ("src/utils/index.ts",)
    assert graph.dependencies["src/utils/index.ts"] == ("src/service.ts",)
    assert graph.cycles == (("src/service.ts", "src/utils/index.ts"),)
    assert graph.orphan_files == ("src/main.ts", "src/orphan.ts")


def test_orphans_are_files_with_no_incoming_dependencies() -> None:
    graph = DependencyGraph("python").build(
        [
            parsed_file("entry.py", "service"),
            parsed_file("service.py", "model"),
            parsed_file("model.py"),
        ]
    )

    assert graph.fan_out["entry.py"] == 1
    assert graph.orphan_files == ("entry.py",)
