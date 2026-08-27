"""Deterministic hypothesis synthesis from domain features + MCP tool results.

Used as the default agent path (no paid LLM) and as fallback when LLM fails.
"""

from __future__ import annotations

from typing import Any

from app.schemas.investigation import HypothesisFindingCreate


AGENT_SPECS: dict[str, dict[str, Any]] = {
    "train_driver": {
        "domain": "train_driver",
        "feature_domains": ("fatigue", "behavioral_telemetry"),
        "source_types": ("train_telemetry",),
        "tool_plan": (
            ("get_domain_features", {}),
            ("query_evidence", {"source_type": "train_telemetry", "limit": 20}),
            ("get_events", {"limit": 40}),
            ("get_anomalies", {}),
            ("get_evidence_gaps", {}),
        ),
        "questions": (
            "Speed, braking, driver actions, operational response, train-side anomalies",
        ),
    },
    "signalling": {
        "domain": "signalling",
        "feature_domains": ("signalling",),
        "source_types": ("signal_log",),
        "tool_plan": (
            ("get_domain_features", {}),
            ("query_evidence", {"source_type": "signal_log", "limit": 20}),
            ("get_anomalies", {}),
            ("get_conflicts", {}),
            ("get_events", {"event_type": None, "limit": 40}),
            ("get_evidence_gaps", {}),
        ),
        "questions": (
            "Signal state, interlocking, ATC/ETCS behaviour, warnings",
        ),
    },
    "track": {
        "domain": "track",
        "feature_domains": ("track",),
        "source_types": ("maintenance",),
        "tool_plan": (
            ("get_domain_features", {}),
            ("query_evidence", {"source_type": "maintenance", "limit": 20}),
            ("get_anomalies", {}),
            ("get_evidence_gaps", {}),
        ),
        "questions": (
            "Track condition, maintenance history, infrastructure anomalies",
        ),
    },
    "environment": {
        "domain": "environment",
        "feature_domains": ("weather",),
        "source_types": ("weather",),
        "tool_plan": (
            ("get_domain_features", {}),
            ("query_evidence", {"source_type": "weather", "limit": 20}),
            ("get_evidence_gaps", {}),
        ),
        "questions": (
            "Rainfall, visibility, temperature, weather-related conditions",
        ),
    },
}


def synthesize_finding(
    *,
    agent_id: str,
    tool_results: dict[str, Any],
) -> HypothesisFindingCreate:
    spec = AGENT_SPECS[agent_id]
    domain = spec["domain"]
    features_payload = tool_results.get("get_domain_features") or {}
    domains = {
        d.get("domain"): d
        for d in (features_payload.get("domains") or [])
        if isinstance(d, dict) and d.get("domain")
    }
    relevant_features = {
        name: domains[name]
        for name in spec["feature_domains"]
        if name in domains
    }

    evidence_items = (tool_results.get("query_evidence") or {}).get("items") or []
    events = (tool_results.get("get_events") or {}).get("items") or []
    anomalies = (tool_results.get("get_anomalies") or {}).get("items") or []
    conflicts = (tool_results.get("get_conflicts") or {}).get("items") or []
    gaps = tool_results.get("get_evidence_gaps") or {}

    supporting: list[str] = []
    contradicting: list[str] = []
    relevant_event_ids: list[str] = []
    missing: list[str] = list(gaps.get("missing_source_types") or [])
    for item in gaps.get("missing_domain_inputs") or []:
        # Keep only gaps for this agent's feature domains
        prefix = str(item).split(":", 1)[0]
        if prefix in spec["feature_domains"] or (
            agent_id == "train_driver"
            and prefix in {"fatigue", "behavioral_telemetry"}
        ):
            missing.append(str(item))

    for feat in relevant_features.values():
        for mid in feat.get("missing_inputs") or []:
            missing.append(f"{feat.get('domain')}:{mid}")
        score = feat.get("score")
        summary = feat.get("summary") or ""
        if score is not None and float(score) >= 0.35:
            supporting.append(f"domain_feature:{feat.get('domain')}:{summary}")
        elif score is not None and float(score) < 0.15 and summary:
            contradicting.append(
                f"low_risk_feature:{feat.get('domain')}:{summary}"
            )

    for rec in evidence_items[:8]:
        rid = rec.get("record_id")
        if rid:
            supporting.append(f"evidence_record:{rid}")

    # Domain-specific anomaly / conflict attachment
    if agent_id == "signalling":
        for a in anomalies:
            if "signal" in str(a.get("rule_id", "")).lower() or "signal" in str(
                a.get("title", "")
            ).lower():
                supporting.append(f"anomaly:{a.get('anomaly_id')}:{a.get('title')}")
                for eid in a.get("affected_event_ids") or []:
                    relevant_event_ids.append(str(eid))
        for c in conflicts:
            if "signal" in str(c.get("conflict_type", "")).lower():
                contradicting.append(
                    f"conflict:{c.get('conflict_id')}:{c.get('title')}"
                )
    elif agent_id == "train_driver":
        for a in anomalies:
            rule = str(a.get("rule_id", "")).lower()
            if any(k in rule for k in ("speed", "brake", "clock")):
                supporting.append(f"anomaly:{a.get('anomaly_id')}:{a.get('title')}")
                for eid in a.get("affected_event_ids") or []:
                    relevant_event_ids.append(str(eid))
    elif agent_id == "track":
        for a in anomalies:
            if "maintenance" in str(a.get("rule_id", "")).lower() or "track" in str(
                a.get("title", "")
            ).lower():
                supporting.append(f"anomaly:{a.get('anomaly_id')}:{a.get('title')}")
        for c in conflicts:
            if "maintenance" in str(c.get("conflict_type", "")).lower():
                contradicting.append(
                    f"conflict:{c.get('conflict_id')}:{c.get('title')}"
                )

    for ev in events[:12]:
        et = str(ev.get("event_type", "")).lower()
        if agent_id == "train_driver" and any(
            k in et for k in ("speed", "brake", "throttle", "telemetry", "train")
        ):
            relevant_event_ids.append(str(ev["event_id"]))
        elif agent_id == "signalling" and "signal" in et:
            relevant_event_ids.append(str(ev["event_id"]))
        elif agent_id == "environment" and any(
            k in et for k in ("weather", "rain", "visib", "temp")
        ):
            relevant_event_ids.append(str(ev["event_id"]))
        elif agent_id == "track" and any(
            k in et for k in ("maint", "track", "infra")
        ):
            relevant_event_ids.append(str(ev["event_id"]))

    # Deduplicate while preserving order
    supporting = _unique(supporting)
    contradicting = _unique(contradicting)
    relevant_event_ids = _unique(relevant_event_ids)
    missing = _unique(missing)

    max_score = 0.0
    summaries: list[str] = []
    for feat in relevant_features.values():
        summaries.append(str(feat.get("summary") or ""))
        if feat.get("score") is not None:
            max_score = max(max_score, float(feat["score"]))

    hypothesis = _hypothesis_text(agent_id, max_score, relevant_features, evidence_items)
    reasoning_parts = [
        f"Agent focus: {spec['questions'][0]}.",
        *summaries,
        f"Retrieved {len(evidence_items)} evidence record(s), "
        f"{len(events)} event(s), {len(anomalies)} anomaly(ies).",
    ]
    if contradicting:
        reasoning_parts.append(
            f"Noted {len(contradicting)} contradicting observation(s)."
        )
    reasoning = " ".join(p for p in reasoning_parts if p)

    confidence = min(
        0.15
        + 0.25 * min(len(supporting) / 3.0, 1.0)
        + 0.35 * max_score
        + (0.1 if evidence_items else 0.0),
        0.95,
    )
    if not evidence_items and max_score == 0.0:
        confidence = min(confidence, 0.25)

    assumptions = [
        "Domain preprocessor scores are features, not causal proof.",
        "Agent confidence is not a Bayesian probability.",
    ]
    if not evidence_items:
        assumptions.append("Limited direct evidence for this domain; hypothesis is provisional.")

    uncertainty = None
    if missing:
        uncertainty = f"Missing inputs/sources: {', '.join(missing[:8])}"
    elif contradicting:
        uncertainty = "Contradicting observations reduce certainty."

    return HypothesisFindingCreate(
        domain=domain,
        hypothesis=hypothesis,
        reasoning=reasoning,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        relevant_events=relevant_event_ids,
        missing_evidence=missing,
        assumptions=assumptions,
        reasoning_summary=reasoning[:500],
        confidence=round(confidence, 4),
        uncertainty=uncertainty,
        domain_features=relevant_features or None,
    )


def synthesize_meta_narrative(
    findings: list[HypothesisFindingCreate],
    *,
    ranked: list[tuple[HypothesisFindingCreate, float]],
) -> str:
    if not findings:
        return "No domain findings produced."
    lines = [
        f"Investigated {len(findings)} domain(s).",
        "Evidence-weighted ranking (not Bayesian):",
    ]
    for finding, score in ranked[:5]:
        lines.append(
            f"- [{finding.domain}] score={score:.3f} · {finding.hypothesis}"
        )
    conflicts = [
        f
        for f in findings
        if f.contradicting_evidence
    ]
    if conflicts:
        lines.append(
            f"{len(conflicts)} domain finding(s) cite contradicting evidence — "
            "investigator review recommended before causal graph promotion."
        )
    return "\n".join(lines)


def _hypothesis_text(
    agent_id: str,
    max_score: float,
    features: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> str:
    if agent_id == "train_driver":
        fatigue = features.get("fatigue") or {}
        behavioral = features.get("behavioral_telemetry") or {}
        if fatigue.get("score") is not None and float(fatigue["score"]) >= 0.4:
            return (
                "Driver alertness / hours-of-service factors may have contributed "
                "to degraded operational response."
            )
        if behavioral.get("features", {}).get("max_excess_over_permitted"):
            return (
                "Train speed behaviour relative to permitted limits warrants "
                "investigation as a contributing factor."
            )
        if evidence_items:
            return (
                "Train/driver telemetry shows operational activity near the incident; "
                "contribution remains provisional pending fuller duty/sleep data."
            )
        return (
            "Insufficient train/driver evidence to assert a strong operational hypothesis."
        )
    if agent_id == "signalling":
        sig = features.get("signalling") or {}
        if sig.get("score") is not None and float(sig["score"]) >= 0.3:
            return (
                "Invalid or anomalous signal transitions may have contributed "
                "to the incident sequence."
            )
        if evidence_items:
            return (
                "Signal-log evidence is present; no strong FSM violation score, "
                "but signalling context should remain under review."
            )
        return "Limited signalling evidence; cannot assert interlocking failure."
    if agent_id == "track":
        track = features.get("track") or {}
        feats = track.get("features") or {}
        if feats.get("maintenance_overdue") or feats.get("below_threshold"):
            return (
                "Track/infrastructure condition (overdue maintenance or low QI) "
                "may have contributed."
            )
        if evidence_items:
            return (
                "Maintenance evidence present without clear overdue/QI breach; "
                "infrastructure contribution is weak but not excluded."
            )
        return "Insufficient track/maintenance evidence for a strong infrastructure hypothesis."
    if agent_id == "environment":
        weather = features.get("weather") or {}
        if weather.get("score") is not None and float(weather["score"]) >= 0.3:
            return (
                "Adverse weather thresholds (visibility/wind/rain/rail temp) "
                "may have contributed to operating risk."
            )
        if evidence_items:
            return (
                "Weather observations exist; threshold composite does not indicate "
                "severe exceedance."
            )
        return "No weather evidence available; environmental contribution unknown."
    if max_score >= 0.4:
        return f"Elevated {agent_id} risk indicators suggest possible contribution."
    return f"No strong {agent_id} contribution indicated by available evidence."


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out
