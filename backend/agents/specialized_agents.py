from __future__ import annotations

from backend.agents.evidence_agent import EvidenceGroundedAgent
from backend.core.report_contract import REPORT_SECTIONS


class CodeSmellAgent(EvidenceGroundedAgent):
    role = "CodeSmellAgent"
    section = REPORT_SECTIONS[1]
    category = "code_smell"
    evidence_query = "complexity duplicate long function too many calls code smell hotspot"
    evidence_limit = 8


class MaintainabilityAgent(EvidenceGroundedAgent):
    role = "MaintainabilityAgent"
    section = REPORT_SECTIONS[2]
    category = "maintainability"
    evidence_query = "maintainability dependency fan in fan out orphan hub tests boundary"
    evidence_limit = 8


class RefactorAgent(EvidenceGroundedAgent):
    role = "RefactorAgent"
    section = REPORT_SECTIONS[3]
    category = "refactor"
    evidence_query = "refactor extraction boundary interface split simplify dependency"
    evidence_limit = 8
