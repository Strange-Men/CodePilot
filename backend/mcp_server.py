from __future__ import annotations

import argparse
import sys
from typing import Any

from backend.models.review_scope import ReviewScope
from backend.workflows import ReviewWorkflow, parse_changed_files, parse_unified_diff_paths


class CodePilotMCPTools:
    def __init__(self, workflow: ReviewWorkflow | None = None) -> None:
        self.workflow = workflow or ReviewWorkflow()

    def analyze_repository(
        self,
        repo_url: str,
        engine_mode: str = "v3_multi_agent",
        mock_llm: bool = True,
        changed_files: list[str] | None = None,
        diff_text: str | None = None,
    ) -> dict[str, Any]:
        review_scope = self._review_scope(changed_files or [], diff_text)
        result = self.workflow.run_review(
            repo_url,
            engine_mode=engine_mode,
            use_mock_llm=mock_llm,
            review_scope=review_scope,
        )
        return result.summary

    def get_review_status(self, task_id: str) -> dict[str, Any]:
        return self.workflow.get_review_status(task_id)

    def get_review_findings(self, task_id: str) -> list[dict]:
        return self.workflow.get_review_findings(task_id)

    def get_review_report(self, task_id: str) -> dict[str, Any]:
        return self.workflow.get_review_report(task_id)

    def get_review_evidence(self, task_id: str) -> list[dict]:
        return self.workflow.get_review_evidence(task_id)

    @staticmethod
    def _review_scope(changed_files: list[str], diff_text: str | None) -> ReviewScope | None:
        changed_paths = parse_changed_files(changed_files)
        if diff_text:
            changed_paths.update(parse_unified_diff_paths(diff_text))
        if not changed_paths:
            return None
        return ReviewScope.for_changed_paths(changed_paths, source="mcp_diff")


def create_server(tools: CodePilotMCPTools | None = None):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The optional MCP SDK is not installed. Install `mcp` to run `python -m backend.mcp_server`."
        ) from exc

    mcp = FastMCP("codepilot")
    tools = tools or CodePilotMCPTools()

    @mcp.tool()
    def analyze_repository(
        repo_url: str,
        engine_mode: str = "v3_multi_agent",
        mock_llm: bool = True,
        changed_files: list[str] | None = None,
        diff_text: str | None = None,
    ) -> dict[str, Any]:
        return tools.analyze_repository(repo_url, engine_mode, mock_llm, changed_files, diff_text)

    @mcp.tool()
    def get_review_status(task_id: str) -> dict[str, Any]:
        return tools.get_review_status(task_id)

    @mcp.tool()
    def get_review_findings(task_id: str) -> list[dict]:
        return tools.get_review_findings(task_id)

    @mcp.tool()
    def get_review_report(task_id: str) -> dict[str, Any]:
        return tools.get_review_report(task_id)

    @mcp.tool()
    def get_review_evidence(task_id: str) -> list[dict]:
        return tools.get_review_evidence(task_id)

    return mcp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the optional CodePilot MCP server.")
    parser.add_argument("--require-sdk", action="store_true", help="Fail fast if the MCP SDK is unavailable.")
    args = parser.parse_args(argv)
    try:
        server = create_server()
    except RuntimeError:
        if args.require_sdk:
            raise
        print("MCP SDK is not installed; install `mcp` to run the CodePilot MCP server.", file=sys.stderr)
        return 1
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
