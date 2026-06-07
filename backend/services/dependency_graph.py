from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from backend.parsers.base import ParsedSourceFile

SCRIPT_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx")


@dataclass(frozen=True)
class DependencyGraphResult:
    dependencies: dict[str, tuple[str, ...]]
    fan_in: dict[str, int]
    fan_out: dict[str, int]
    cycles: tuple[tuple[str, ...], ...]
    hub_files: tuple[str, ...]
    orphan_files: tuple[str, ...]


class DependencyGraph:
    def __init__(self, language: str) -> None:
        self.language = language

    def build(self, parsed_files: list[ParsedSourceFile]) -> DependencyGraphResult:
        paths = {file.path.replace("\\", "/") for file in parsed_files}
        python_modules = self._python_module_map(paths)
        dependencies: dict[str, set[str]] = {path: set() for path in paths}

        for parsed in parsed_files:
            source_path = parsed.path.replace("\\", "/")
            import_specs = parsed.dependency_imports or parsed.imports
            for import_spec in import_specs:
                targets = self._resolve_imports(
                    source_path,
                    import_spec,
                    paths,
                    python_modules,
                )
                dependencies[source_path].update(
                    target for target in targets if target != source_path
                )

        ordered_dependencies = {
            path: tuple(sorted(targets))
            for path, targets in sorted(dependencies.items())
        }
        fan_out = {path: len(targets) for path, targets in ordered_dependencies.items()}
        fan_in = {path: 0 for path in ordered_dependencies}
        for targets in ordered_dependencies.values():
            for target in targets:
                fan_in[target] += 1

        cycles = self._find_cycles(ordered_dependencies)
        hub_files = tuple(
            path
            for path in sorted(fan_in, key=lambda item: (-fan_in[item], item))
            if fan_in[path] > 0
        )[:5]
        orphan_files = tuple(
            path
            for path in sorted(ordered_dependencies)
            if fan_in[path] == 0
        )
        return DependencyGraphResult(
            dependencies=ordered_dependencies,
            fan_in=fan_in,
            fan_out=fan_out,
            cycles=cycles,
            hub_files=hub_files,
            orphan_files=orphan_files,
        )

    def _resolve_imports(
        self,
        source_path: str,
        import_spec: str,
        paths: set[str],
        python_modules: dict[str, str],
    ) -> set[str]:
        source_language = self._source_language(source_path) if self.language == "mixed" else self.language
        if source_language == "python":
            resolved_targets: set[str] = set()
            for module in self._python_import_candidates(import_spec):
                resolved = self._resolve_python_module(source_path, module, python_modules)
                if resolved:
                    resolved_targets.add(resolved)
            return resolved_targets
        if source_language in {"javascript", "typescript"}:
            specifier = self._script_import_specifier(import_spec)
            if specifier and specifier.startswith("."):
                resolved = self._resolve_script_path(source_path, specifier, paths)
                return {resolved} if resolved else set()
        return set()

    @staticmethod
    def _source_language(source_path: str) -> str:
        suffix = PurePosixPath(source_path).suffix.lower()
        if suffix == ".py":
            return "python"
        if suffix in {".js", ".jsx"}:
            return "javascript"
        if suffix in {".ts", ".tsx"}:
            return "typescript"
        return ""

    @staticmethod
    def _python_module_map(paths: set[str]) -> dict[str, str]:
        modules: dict[str, str] = {}
        for path in paths:
            pure_path = PurePosixPath(path)
            if pure_path.suffix != ".py":
                continue
            parts = list(pure_path.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            if parts:
                modules[".".join(parts)] = path
        return modules

    @staticmethod
    def _python_import_candidates(import_spec: str) -> list[str]:
        stripped = import_spec.strip()
        if stripped.startswith("import "):
            return [
                item.strip().split(" as ", 1)[0]
                for item in stripped.removeprefix("import ").split(",")
                if item.strip()
            ]
        match = re.match(r"from\s+(?P<module>[\w.]+)\s+import\s+(?P<names>.+)", stripped)
        if match:
            module = match.group("module")
            names = [
                item.strip().split(" as ", 1)[0]
                for item in match.group("names").split(",")
                if item.strip() and item.strip() != "*"
            ]
            separator = "" if module.endswith(".") else "."
            return [f"{module}{separator}{name}" for name in names] + [module]
        return [stripped] if stripped else []

    @staticmethod
    def _resolve_python_module(
        source_path: str,
        module: str,
        python_modules: dict[str, str],
    ) -> str | None:
        if module.startswith("."):
            level = len(module) - len(module.lstrip("."))
            suffix = module[level:]
            source = PurePosixPath(source_path)
            package_parts = list(source.parent.parts)
            if source.name == "__init__.py":
                package_parts = list(source.parent.parts)
            parent_levels = max(0, level - 1)
            if parent_levels > len(package_parts):
                return None
            base_parts = package_parts[: len(package_parts) - parent_levels]
            module_parts = [part for part in suffix.split(".") if part]
            resolved_module = ".".join([*base_parts, *module_parts])
        else:
            resolved_module = module

        parts = resolved_module.split(".")
        while parts:
            candidate = ".".join(parts)
            if candidate in python_modules:
                return python_modules[candidate]
            parts.pop()
        return None

    @staticmethod
    def _script_import_specifier(import_spec: str) -> str | None:
        stripped = import_spec.strip()
        if stripped.startswith("."):
            return stripped
        match = re.search(
            r"(?:from\s+|import\s*\(|require\s*\()\s*['\"](?P<specifier>[^'\"]+)['\"]",
            stripped,
        )
        if match:
            return match.group("specifier")
        side_effect = re.match(r"import\s+['\"](?P<specifier>[^'\"]+)['\"]", stripped)
        return side_effect.group("specifier") if side_effect else None

    @staticmethod
    def _resolve_script_path(source_path: str, specifier: str, paths: set[str]) -> str | None:
        source_dir = PurePosixPath(source_path).parent.as_posix()
        base = posixpath.normpath(posixpath.join(source_dir, specifier))
        candidates = [base]
        if PurePosixPath(base).suffix not in SCRIPT_EXTENSIONS:
            candidates.extend(f"{base}{extension}" for extension in SCRIPT_EXTENSIONS)
            candidates.extend(f"{base}/index{extension}" for extension in SCRIPT_EXTENSIONS)
        return next((candidate for candidate in candidates if candidate in paths), None)

    @staticmethod
    def _find_cycles(
        dependencies: dict[str, tuple[str, ...]],
    ) -> tuple[tuple[str, ...], ...]:
        index = 0
        indices: dict[str, int] = {}
        low_links: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        cycles: list[tuple[str, ...]] = []

        def visit(node: str) -> None:
            nonlocal index
            indices[node] = index
            low_links[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)

            for target in dependencies[node]:
                if target not in indices:
                    visit(target)
                    low_links[node] = min(low_links[node], low_links[target])
                elif target in on_stack:
                    low_links[node] = min(low_links[node], indices[target])

            if low_links[node] != indices[node]:
                return
            component: list[str] = []
            while stack:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1:
                cycles.append(tuple(sorted(component)))

        for node in sorted(dependencies):
            if node not in indices:
                visit(node)
        return tuple(sorted(cycles))
