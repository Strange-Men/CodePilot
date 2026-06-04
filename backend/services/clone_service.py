from __future__ import annotations

import shutil
import subprocess
import sys
import logging
from pathlib import Path
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


class CloneError(RuntimeError):
    pass


class CloneService:
    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path

    def clone(self, repo_url: str, task_id: str) -> Path:
        parsed = urlparse(repo_url)
        if parsed.scheme not in {"https", "http"} or "github.com" not in parsed.netloc.lower():
            raise CloneError("Only public GitHub HTTP(S) repository URLs are supported in this MVP.")

        task_dir = self.workspace_path / task_id
        repo_dir = task_dir / "repo"
        if task_dir.exists():
            shutil.rmtree(task_dir)
        task_dir.mkdir(parents=True, exist_ok=True)

        last_error = ""
        for attempt in range(3):
            command = ["git", "clone", "--depth", "1", repo_url, str(repo_dir)]
            completed = self._run_git(command, timeout_seconds=180)
            if completed.returncode == 0:
                return repo_dir
            last_error = completed.stderr.strip() or completed.stdout.strip() or "git clone failed"
            # If shallow clone not supported, fall back to full clone (no retry needed)
            if "dumb http transport does not support shallow" in last_error.lower():
                completed = self._run_git(["git", "clone", repo_url, str(repo_dir)], timeout_seconds=180)
                if completed.returncode == 0:
                    return repo_dir
                last_error = completed.stderr.strip() or completed.stdout.strip() or "git clone failed"
                break

            if not self._is_transient_network_error(last_error) or attempt == 2:
                break

            logger.warning("Retrying git clone for task %s after transient failure (%s/3): %s", task_id, attempt + 2, last_error)
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
            task_dir.mkdir(parents=True, exist_ok=True)

        raise CloneError(last_error)

    @staticmethod
    def _run_git(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            if sys.platform.startswith("win"):
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, text=True)
            else:
                process.kill()
            stdout, stderr = process.communicate()
            return subprocess.CompletedProcess(
                command,
                124,
                stdout,
                (stderr or "") + f"\ngit clone timed out after {timeout_seconds} seconds.",
            )
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)

    @staticmethod
    def _is_transient_network_error(message: str) -> bool:
        lower_message = message.lower()
        non_retryable_markers = [
            "authentication failed",
            "could not read username",
            "repository not found",
            "not found",
            "permission denied",
            "repository does not exist",
        ]
        if any(marker in lower_message for marker in non_retryable_markers):
            return False

        transient_markers = [
            "connection reset",
            "connection was reset",
            "recv failure",
            "timed out",
            "timeout",
            "temporary failure",
            "failed to connect",
            "couldn't connect",
            "connection refused",
            "connection aborted",
            "remote end hung up unexpectedly",
            "early eof",
            "network is unreachable",
        ]
        return any(marker in lower_message for marker in transient_markers)
