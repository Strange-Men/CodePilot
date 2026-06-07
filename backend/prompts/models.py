from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PromptVersion(StrEnum):
    V2_6 = "2.6"


@dataclass(frozen=True)
class PromptSection:
    name: str
    lines: tuple[str, ...]

    def render(self) -> str:
        return "\n".join(self.lines)


@dataclass(frozen=True)
class PromptTemplate:
    version: PromptVersion
    sections: tuple[PromptSection, ...]

    def render(self) -> str:
        return "\n".join(section.render() for section in self.sections if section.lines)
