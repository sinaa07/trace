"""Bounded investigation graph: four domain agents + meta ranking.

LangGraph-shaped state machine (simple async-capable Python orchestrator).
Max tool iterations per agent is capped (blueprint: 3–5).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.agents.llm import (
    HeuristicLLM,
    finding_from_llm_dict,
    get_llm_provider,
)
from app.core.agents.synthesizer import (
    AGENT_SPECS,
    synthesize_finding,
    synthesize_meta_narrative,
)
from app.core.investigation.ranking import score_hypothesis
from app.core.mcp.tools import EvidenceTools
from app.schemas.investigation import HypothesisFindingCreate, RankingDimensionScores


MAX_TOOL_ITERATIONS = 5


@dataclass
class AgentRunResult:
    agent_id: str
    finding: HypothesisFindingCreate
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    dimensions: RankingDimensionScores | None = None
    weighted_score: float = 0.0
    mode: str = "heuristic"


@dataclass
class InvestigationState:
    case_id: uuid.UUID
    run_id: uuid.UUID
    findings: list[AgentRunResult] = field(default_factory=list)
    meta_summary: str = ""
    provider: str = "heuristic"


class InvestigationOrchestrator:
    """Run domain agents over shared MCP tools, then evidence-weighted rank."""

    def __init__(
        self,
        db: Session,
        *,
        llm_provider: str | None = None,
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        self.db = db
        self.llm_provider_name = llm_provider
        self.max_iterations = max(1, min(max_iterations, 5))
        self.llm = get_llm_provider(llm_provider)

    def run(self, case_id: uuid.UUID) -> InvestigationState:
        run_id = uuid.uuid4()
        tools = EvidenceTools(self.db, case_id)
        state = InvestigationState(
            case_id=case_id,
            run_id=run_id,
            provider=type(self.llm).__name__,
        )

        for agent_id in AGENT_SPECS:
            result = self._run_domain_agent(agent_id, tools)
            dims, weighted = score_hypothesis(
                result.finding,
                source_reliability=self._source_reliability(agent_id, result.tool_trace),
                temporal_consistency=self._temporal_consistency(result.tool_trace),
                causal_support=0.0,  # Phase 4 Neo4j
            )
            result.dimensions = dims
            result.weighted_score = weighted
            state.findings.append(result)

        ranked = sorted(
            [(r.finding, r.weighted_score) for r in state.findings],
            key=lambda x: x[1],
            reverse=True,
        )
        state.meta_summary = synthesize_meta_narrative(
            [r.finding for r in state.findings],
            ranked=ranked,
        )
        # Optional short LLM narrative on top of deterministic ranking
        if not isinstance(self.llm, HeuristicLLM):
            try:
                narrative = self.llm.complete_json(
                    system=(
                        "You are TRACE meta-arbitrator. Ranking scores are already "
                        "computed in code. Write a short synthesis JSON with keys "
                        "hypothesis, reasoning, reasoning_summary, confidence, "
                        "supporting_evidence, contradicting_evidence, missing_evidence, "
                        "assumptions, uncertainty, relevant_events. "
                        "Do not invent evidence IDs."
                    ),
                    user=state.meta_summary
                    + "\n\nDomain findings:\n"
                    + "\n".join(
                        f"- {r.agent_id}: {r.finding.hypothesis} "
                        f"(conf={r.finding.confidence}, rank={r.weighted_score})"
                        for r in state.findings
                    ),
                    schema_hint="HypothesisFinding fields",
                )
                meta_finding = finding_from_llm_dict(
                    narrative, domain="meta", domain_features=None
                )
                dims, weighted = score_hypothesis(meta_finding, causal_support=0.0)
                state.findings.append(
                    AgentRunResult(
                        agent_id="meta",
                        finding=meta_finding,
                        dimensions=dims,
                        weighted_score=weighted,
                        mode="llm",
                    )
                )
                state.meta_summary = meta_finding.reasoning_summary or state.meta_summary
            except Exception:
                # Keep deterministic meta summary on LLM failure
                pass

        return state

    def _run_domain_agent(
        self, agent_id: str, tools: EvidenceTools
    ) -> AgentRunResult:
        spec = AGENT_SPECS[agent_id]
        tool_trace: list[dict[str, Any]] = []
        tool_results: dict[str, Any] = {}

        for name, args in list(spec["tool_plan"])[: self.max_iterations]:
            # Drop None-valued args for cleaner calls
            clean_args = {k: v for k, v in args.items() if v is not None}
            result = tools.call(name, clean_args)
            tool_trace.append({"tool": name, "arguments": clean_args, "result": result})
            tool_results[name] = result

        mode = "heuristic"
        if isinstance(self.llm, HeuristicLLM):
            finding = synthesize_finding(agent_id=agent_id, tool_results=tool_results)
        else:
            try:
                finding = self._llm_finding(agent_id, spec, tool_results)
                mode = "llm"
            except Exception:
                finding = synthesize_finding(
                    agent_id=agent_id, tool_results=tool_results
                )
                mode = "heuristic_fallback"

        return AgentRunResult(
            agent_id=agent_id,
            finding=finding,
            tool_trace=tool_trace,
            mode=mode,
        )

    def _llm_finding(
        self,
        agent_id: str,
        spec: dict[str, Any],
        tool_results: dict[str, Any],
    ) -> HypothesisFindingCreate:
        compact = {
            k: _compact_tool_result(v) for k, v in tool_results.items()
        }
        data = self.llm.complete_json(
            system=(
                f"You are the TRACE {agent_id} domain agent. "
                f"Primary questions: {spec['questions'][0]}. "
                "Put reasoning before conclusions. Cite only evidence/event IDs "
                "present in the tool results. Confidence is not a probability."
            ),
            user=f"Tool results JSON:\n{compact}",
            schema_hint=(
                "{hypothesis, reasoning, supporting_evidence[], contradicting_evidence[], "
                "relevant_events[], missing_evidence[], assumptions[], reasoning_summary, "
                "confidence, uncertainty}"
            ),
        )
        features_payload = tool_results.get("get_domain_features") or {}
        domains = {
            d.get("domain"): d
            for d in (features_payload.get("domains") or [])
            if isinstance(d, dict) and d.get("domain")
        }
        relevant = {
            name: domains[name]
            for name in spec["feature_domains"]
            if name in domains
        }
        return finding_from_llm_dict(
            data, domain=spec["domain"], domain_features=relevant or None
        )

    @staticmethod
    def _source_reliability(agent_id: str, tool_trace: list[dict[str, Any]]) -> float:
        evidence_call = next(
            (t for t in tool_trace if t["tool"] == "query_evidence"), None
        )
        if not evidence_call:
            return 0.4
        items = (evidence_call.get("result") or {}).get("items") or []
        if not items:
            return 0.45
        # Prefer completed, non-review sources
        return 0.75

    @staticmethod
    def _temporal_consistency(tool_trace: list[dict[str, Any]]) -> float:
        events_call = next(
            (t for t in tool_trace if t["tool"] in {"get_events", "get_timeline"}),
            None,
        )
        if not events_call:
            return 0.5
        items = (events_call.get("result") or {}).get("items") or []
        if not items:
            return 0.55
        with_corrected = sum(1 for e in items if e.get("corrected_timestamp"))
        return 0.6 + 0.3 * (with_corrected / max(len(items), 1))


def _compact_tool_result(value: Any, *, max_items: int = 15) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k == "items" and isinstance(v, list):
                out[k] = v[:max_items]
                out["truncated"] = len(v) > max_items
            else:
                out[k] = _compact_tool_result(v, max_items=max_items)
        return out
    if isinstance(value, list):
        return value[:max_items]
    return value
