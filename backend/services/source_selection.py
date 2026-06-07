from pathlib import Path

TEST_PATH_PARTS = {"test", "tests", "__tests__"}


def source_file_priority(
    path: Path,
    *,
    entry_names: set[str],
    core_path_parts: set[str],
    test_name_prefixes: tuple[str, ...] = ("test",),
) -> tuple[int, int, str]:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    score = 50
    if name in entry_names:
        score -= 20
    if any(part in core_path_parts for part in parts):
        score -= 10
    if any(
        part in TEST_PATH_PARTS or part.startswith(test_name_prefixes)
        for part in parts
    ):
        score += 8
    return score, len(parts), path.as_posix()
