from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from backend.services.clone_service import CloneError, CloneService


def completed(
    command: list[str],
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


def test_successful_clone_uses_git_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloneService(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return completed(command)

    monkeypatch.setattr(service, "_run_git", fake_run)

    repo_dir = service.clone("https://github.com/pallets/flask", "task-1")

    assert repo_dir == tmp_path / "task-1" / "repo"
    assert calls == [["git", "clone", "--depth", "1", "https://github.com/pallets/flask", str(repo_dir)]]
    assert "-c" not in calls[0]
    assert "http.version=HTTP/1.1" not in calls[0]


@pytest.mark.parametrize(
    "repo_url",
    [
        "https://gitlab.com/example/project",
        "ssh://github.com/example/project",
        "file:///tmp/project",
    ],
)
def test_invalid_repository_is_rejected(tmp_path: Path, repo_url: str) -> None:
    with pytest.raises(CloneError, match="public GitHub"):
        CloneService(tmp_path).clone(repo_url, "task-1")


def test_retry_path_retries_transient_network_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloneService(tmp_path)
    calls = 0

    def fake_run(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            repo_dir = tmp_path / "task-1" / "repo"
            repo_dir.mkdir(parents=True)
            (repo_dir / "partial.txt").write_text("partial", encoding="utf-8")
            return completed(command, returncode=128, stderr="Recv failure: Connection was reset")
        return completed(command)

    monkeypatch.setattr(service, "_run_git", fake_run)

    assert service.clone("https://github.com/pallets/flask", "task-1") == tmp_path / "task-1" / "repo"
    assert calls == 2
    assert not (tmp_path / "task-1" / "repo" / "partial.txt").exists()


def test_clone_retries_at_most_three_times(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloneService(tmp_path)
    calls = 0

    def fake_run(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return completed(command, returncode=128, stderr="Failed to connect to github.com")

    monkeypatch.setattr(service, "_run_git", fake_run)

    with pytest.raises(CloneError, match="Failed to connect"):
        service.clone("https://github.com/pallets/flask", "task-1")

    assert calls == 3


def test_clone_does_not_retry_authentication_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloneService(tmp_path)
    calls = 0

    def fake_run(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return completed(command, returncode=128, stderr="Authentication failed")

    monkeypatch.setattr(service, "_run_git", fake_run)

    with pytest.raises(CloneError, match="Authentication failed"):
        service.clone("https://github.com/private/repo", "task-1")

    assert calls == 1


def test_dumb_http_fallback_runs_full_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloneService(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if "--depth" in command:
            return completed(command, returncode=128, stderr="dumb http transport does not support shallow")
        return completed(command)

    monkeypatch.setattr(service, "_run_git", fake_run)

    repo_dir = service.clone("https://github.com/pallets/flask", "task-1")

    assert repo_dir == tmp_path / "task-1" / "repo"
    assert calls[1] == ["git", "clone", "https://github.com/pallets/flask", str(repo_dir)]


def test_cleanup_path_removes_task_workspace(tmp_path: Path) -> None:
    task_dir = tmp_path / "task-1"
    (task_dir / "repo").mkdir(parents=True)
    (task_dir / "repo" / "file.py").write_text("print('ok')", encoding="utf-8")

    CloneService(tmp_path).cleanup("task-1")

    assert not task_dir.exists()


def test_cleanup_handles_readonly_git_files(tmp_path: Path) -> None:
    task_dir = tmp_path / "task-1"
    locked_file = task_dir / "repo" / ".git" / "objects" / "pack" / "pack.idx"
    locked_file.parent.mkdir(parents=True)
    locked_file.write_text("pack", encoding="utf-8")
    locked_file.chmod(stat.S_IREAD)

    try:
        CloneService(tmp_path).cleanup("task-1")
        assert not task_dir.exists()
    finally:
        if locked_file.exists():
            os.chmod(locked_file, stat.S_IWRITE)
