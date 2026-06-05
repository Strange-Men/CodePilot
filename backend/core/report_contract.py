from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

REPORT_CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "report_sections.json"


@dataclass(frozen=True)
class ReportSection:
    id: str
    title: str


@lru_cache(maxsize=1)
def load_report_sections(contract_path: Path = REPORT_CONTRACT_PATH) -> tuple[ReportSection, ...]:
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    raw_sections = data.get("sections", [])
    return tuple(_parse_report_section(section) for section in raw_sections)


def numbered_report_section_lines() -> list[str]:
    return [f"{index}. {section}" for index, section in enumerate(REPORT_SECTIONS, start=1)]


def report_section_heading_list() -> str:
    return ", ".join(REPORT_SECTIONS)


def _parse_report_section(section: Any) -> ReportSection:
    return ReportSection(id=str(section["id"]), title=str(section["title"]))


REPORT_SECTIONS = [section.title for section in load_report_sections()]
