from __future__ import annotations

from backend.agents.evidence_agent import EvidenceGroundedAgent
from backend.core.report_contract import REPORT_SECTIONS


class ArchitectureAgent(EvidenceGroundedAgent):
    role = "ArchitectureAgent"
    section = REPORT_SECTIONS[0]
    category = "architecture"
    evidence_query = "architecture entry point core module dependency route class function"
    evidence_limit = 10
