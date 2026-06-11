from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelPricing:
    prompt_per_million_tokens: float
    completion_per_million_tokens: float


@dataclass(frozen=True)
class PricingConfig:
    version: str
    currency: str
    models: dict[str, ModelPricing]


@dataclass(frozen=True)
class AgentUsage:
    agent_id: str
    prompt_tokens: int
    completion_tokens: int
    llm_calls: int
    duration_seconds: float | None


@dataclass(frozen=True)
class RepoUsageSummary:
    model: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    llm_calls: int
    duration_seconds: float
    estimated_cost: float | None
    currency: str | None
    pricing_known: bool
    agents: list[AgentUsage]

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "llm_calls": self.llm_calls,
            "duration_seconds": round(self.duration_seconds, 6),
            "estimated_cost": self.estimated_cost,
            "currency": self.currency,
            "pricing_known": self.pricing_known,
            "agents": [asdict(agent) for agent in self.agents],
        }


def load_pricing_config(path: Path) -> PricingConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    models: dict[str, ModelPricing] = {}
    for model, raw in (data.get("models") or {}).items():
        prompt = float(raw["prompt_per_million_tokens"])
        completion = float(raw["completion_per_million_tokens"])
        if prompt < 0 or completion < 0:
            raise ValueError(f"Pricing values must be non-negative for model {model}.")
        models[str(model)] = ModelPricing(prompt, completion)
    return PricingConfig(
        version=str(data.get("version") or "1"),
        currency=str(data.get("currency") or "USD"),
        models=models,
    )


def summarize_repo_usage(
    agent_states: list[dict],
    *,
    runtime_seconds: float,
    model: str | None,
    pricing: PricingConfig | None = None,
) -> RepoUsageSummary:
    agents = [
        AgentUsage(
            agent_id=str(state.get("agent_id") or "unknown"),
            prompt_tokens=int(state.get("prompt_tokens") or 0),
            completion_tokens=int(state.get("completion_tokens") or 0),
            llm_calls=int(state.get("llm_calls") or 0),
            duration_seconds=_optional_float((state.get("metadata") or {}).get("duration_seconds")),
        )
        for state in agent_states
    ]
    prompt_tokens = sum(agent.prompt_tokens for agent in agents)
    completion_tokens = sum(agent.completion_tokens for agent in agents)
    llm_calls = sum(agent.llm_calls for agent in agents)
    rate = pricing.models.get(model) if pricing is not None and model is not None else None
    estimated_cost = None
    if rate is not None:
        estimated_cost = round(
            (
                prompt_tokens * rate.prompt_per_million_tokens
                + completion_tokens * rate.completion_per_million_tokens
            )
            / 1_000_000,
            8,
        )
    return RepoUsageSummary(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        llm_calls=llm_calls,
        duration_seconds=runtime_seconds,
        estimated_cost=estimated_cost,
        currency=pricing.currency if rate is not None and pricing is not None else None,
        pricing_known=rate is not None,
        agents=agents,
    )


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None
