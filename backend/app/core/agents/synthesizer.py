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
            ("fetch_weather_at_location", {}),
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
    weather_fetch = tool_results.get("fetch_weather_at_location") or {}

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

    external_weather_summary: str | None = None
    external_weather_score = 0.0
    if agent_id == "environment":
        (
            relevant_features,
            missing,
            external_weather_score,
            external_weather_summary,
        ) = _apply_external_weather_context(
            relevant_features, weather_fetch, missing
        )

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

    if agent_id == "environment" and weather_fetch.get("observation"):
        obs = weather_fetch["observation"]
        provider = obs.get("provider") or "weather_provider"
        supporting.append(
            f"external_weather:{provider}:{obs.get('observed_at')}"
        )
        risk = weather_fetch.get("risk_assessment") or {}
        if risk.get("score") is not None and float(risk["score"]) >= 0.3:
            supporting.append(f"external_weather_risk:{risk.get('summary')}")
        coords = weather_fetch.get("coordinates") or {}
        if coords.get("source"):
            supporting.append(f"coordinates:{coords.get('source')}")
    elif agent_id == "environment" and weather_fetch.get("error"):
        missing.append(f"external_weather:{weather_fetch['error']}")

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

    max_score = external_weather_score
    summaries: list[str] = []
    for feat in relevant_features.values():
        summary = str(feat.get("summary") or "")
        if (
            agent_id == "environment"
            and external_weather_summary
            and "No weather measurements available" in summary
        ):
            continue
        if summary:
            summaries.append(summary)
        if feat.get("score") is not None:
            max_score = max(max_score, float(feat["score"]))
    if agent_id == "environment" and external_weather_summary:
        summaries.append(external_weather_summary)

    hypothesis = _hypothesis_text(
        agent_id, max_score, relevant_features, evidence_items, weather_fetch
    )
    reasoning_parts = [
        f"Agent focus: {spec['questions'][0]}.",
        *summaries,
        f"Retrieved {len(evidence_items)} evidence record(s), "
        f"{len(events)} event(s), {len(anomalies)} anomaly(ies).",
    ]
    if agent_id == "environment" and weather_fetch.get("observation"):
        obs = (weather_fetch.get("observation") or {})
        coords = weather_fetch.get("coordinates") or {}
        reasoning_parts.append(
            "External weather fetched via MCP at "
            f"({coords.get('latitude')}, {coords.get('longitude')}) "
            f"for {obs.get('observed_at')}."
        )
    if contradicting:
        reasoning_parts.append(
            f"Noted {len(contradicting)} contradicting observation(s)."
        )
    reasoning = " ".join(p for p in reasoning_parts if p)

    confidence = min(
        0.15
        + 0.25 * min(len(supporting) / 3.0, 1.0)
        + 0.35 * max_score
        + (0.1 if evidence_items else 0.0)
        + (0.12 if agent_id == "environment" and weather_fetch.get("observation") else 0.0),
        0.95,
    )
    if not evidence_items and max_score == 0.0:
        confidence = min(confidence, 0.25)

    assumptions = [
        "Domain preprocessor scores are features, not causal proof.",
        "Agent confidence is not a Bayesian probability.",
    ]
    if not evidence_items and agent_id == "environment" and weather_fetch.get("observation"):
        assumptions.append(
            "Weather assessment uses external Open-Meteo MCP fetch; "
            "uploaded weather evidence was not available."
        )
    elif not evidence_items:
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
    weather_fetch: dict[str, Any] | None = None,
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
        external = weather_fetch or {}
        external_risk = external.get("risk_assessment") or {}
        external_score = external_risk.get("score")
        if external_score is not None and float(external_score) >= 0.3:
            return (
                "External weather service reports adverse conditions at the "
                "accident coordinates (visibility/wind/rain/temperature thresholds)."
            )
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


def _apply_external_weather_context(
    relevant_features: dict[str, Any],
    weather_fetch: dict[str, Any],
    missing: list[str],
) -> tuple[dict[str, Any], list[str], float, str | None]:
    """Fold Open-Meteo MCP results into environment agent weather context."""
    if not weather_fetch.get("observation"):
        return relevant_features, missing, 0.0, None

    risk = weather_fetch.get("risk_assessment") or {}
    obs = weather_fetch["observation"]
    provenance = weather_fetch.get("provenance") or {}
    coords = weather_fetch.get("coordinates") or {}
    domain_weather = relevant_features.get("weather") or {}

    external_weather = {
        "domain": "weather",
        "score": risk.get("score"),
        "summary": risk.get("summary") or "External weather observations retrieved.",
        "features": {
            **(risk.get("features") or {}),
            "ambient_temp_c": obs.get("ambient_temp_c"),
            "rainfall_mm_hour": obs.get("rainfall_mm_hour"),
            "wind_speed_kmh": obs.get("wind_speed_kmh"),
            "visibility_m": obs.get("visibility_m"),
            "source": provenance.get("provider") or "open-meteo",
            "observed_at": obs.get("observed_at"),
            "latitude": coords.get("latitude"),
            "longitude": coords.get("longitude"),
            "coordinate_source": coords.get("source"),
        },
        "inputs_used": risk.get("inputs_used") or [],
        "missing_inputs": risk.get("missing_inputs") or [],
        "warnings": [
            *(domain_weather.get("warnings") or []),
            "External weather via MCP fetch_weather_at_location (not uploaded evidence).",
        ],
    }

    domain_summary = str(domain_weather.get("summary") or "")
    domain_has_measurements = domain_weather.get("score") is not None and (
        "No weather measurements available" not in domain_summary
    )
    if domain_has_measurements:
        merged = {**domain_weather, "features": {
            **(domain_weather.get("features") or {}),
            **(external_weather.get("features") or {}),
        }}
        if external_weather.get("score") is not None and (
            domain_weather.get("score") is None
            or float(external_weather["score"]) > float(domain_weather["score"])
        ):
            merged["score"] = external_weather["score"]
            merged["summary"] = (
                f"{domain_summary} External check: {external_weather['summary']}"
            )
        relevant_features = {**relevant_features, "weather": merged}
    else:
        relevant_features = {**relevant_features, "weather": external_weather}

    external_score = (
        float(risk["score"]) if risk.get("score") is not None else 0.0
    )
    inputs_used = set(risk.get("inputs_used") or [])
    filtered_missing: list[str] = []
    for item in missing:
        if item == "weather":
            continue
        if item.startswith("weather:"):
            field_name = item.split(":", 1)[1]
            if field_name in inputs_used:
                continue
        filtered_missing.append(item)

    summary_line = (
        f"Open-Meteo at ({coords.get('latitude')}, {coords.get('longitude')}): "
        f"{risk.get('summary') or 'observations retrieved'}."
    )
    return relevant_features, filtered_missing, external_score, summary_line


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out
