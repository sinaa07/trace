"""MCP-shaped evidence read tools (in-process adapter).

Agents call these tools; the FastAPI surface remains the system of record.
Read-only by design — mutations go through controlled backend services.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.enums import SourceType
from app.services.event_service import EventService
from app.services.quality_service import QualityAnalysisService
from app.services.storage.repositories.case_repo import CaseRepository
from app.services.storage.repositories.evidence_repo import EvidenceRepository
from app.services.storage.repositories.event_repo import EventRepository


TOOL_NAMES = (
    "query_evidence",
    "get_event",
    "get_events",
    "get_timeline",
    "get_source_metadata",
    "get_evidence_provenance",
    "get_evidence_gaps",
    "get_domain_features",
    "get_anomalies",
    "get_conflicts",
)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class EvidenceTools:
    """Blueprint MCP evidence tools for a single case context."""

    def __init__(self, db: Session, case_id: uuid.UUID) -> None:
        self.db = db
        self.case_id = case_id
        self.cases = CaseRepository(db)
        self.evidence = EvidenceRepository(db)
        self.events = EventRepository(db)
        self.event_service = EventService(db)
        self.quality = QualityAnalysisService(db)

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {"name": "query_evidence", "purpose": "Retrieve evidence records with filters"},
            {"name": "get_event", "purpose": "Retrieve one event and provenance"},
            {"name": "get_events", "purpose": "Retrieve related events"},
            {"name": "get_timeline", "purpose": "Retrieve timeline window"},
            {"name": "get_source_metadata", "purpose": "Source integrity / metadata"},
            {"name": "get_evidence_provenance", "purpose": "Source-to-record lineage"},
            {"name": "get_evidence_gaps", "purpose": "Known missing evidence"},
            {"name": "get_domain_features", "purpose": "Domain preprocessor scores"},
            {"name": "get_anomalies", "purpose": "Rule-based anomalies for case"},
            {"name": "get_conflicts", "purpose": "Cross-source conflicts for case"},
        ]

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        handlers = {
            "query_evidence": self.query_evidence,
            "get_event": self.get_event,
            "get_events": self.get_events,
            "get_timeline": self.get_timeline,
            "get_source_metadata": self.get_source_metadata,
            "get_evidence_provenance": self.get_evidence_provenance,
            "get_evidence_gaps": self.get_evidence_gaps,
            "get_domain_features": self.get_domain_features,
            "get_anomalies": self.get_anomalies,
            "get_conflicts": self.get_conflicts,
        }
        if name not in handlers:
            return {"error": f"Unknown tool: {name}", "available": list(TOOL_NAMES)}
        return handlers[name](**args)

    def query_evidence(
        self,
        *,
        source_type: str | None = None,
        q: str | None = None,
        evidence_id: str | None = None,
        is_valid: bool | None = True,
        limit: int = 25,
    ) -> dict[str, Any]:
        st: SourceType | None = None
        if source_type:
            try:
                st = SourceType(source_type)
            except ValueError:
                return {"error": f"Invalid source_type: {source_type}"}
        eid = uuid.UUID(evidence_id) if evidence_id else None
        rows, total = self.evidence.search_records(
            self.case_id,
            evidence_id=eid,
            source_type=st,
            is_valid=is_valid,
            q=q,
            limit=min(max(limit, 1), 100),
            offset=0,
        )
        items = []
        for record, artifact in rows:
            items.append(
                {
                    "record_id": str(record.record_id),
                    "evidence_id": str(record.evidence_id),
                    "filename": artifact.filename,
                    "source_type": artifact.source_type.value
                    if hasattr(artifact.source_type, "value")
                    else str(artifact.source_type),
                    "normalized_data": record.normalized_data,
                    "is_valid": record.is_valid,
                    "parse_warnings": record.parse_warnings or [],
                }
            )
        return {"total": total, "items": items}

    def get_event(self, *, event_id: str) -> dict[str, Any]:
        try:
            eid = uuid.UUID(event_id)
        except ValueError:
            return {"error": "Invalid event_id"}
        event = self.events.get(eid)
        if event is None or event.case_id != self.case_id:
            return {"error": "Event not found"}
        return self._serialize_event(event)

    def get_events(
        self,
        *,
        event_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        events = self.event_service.get_case_events(
            self.case_id, event_type=event_type, limit=limit
        )
        return {
            "count": len(events),
            "items": [self._serialize_event(e) for e in events],
        }

    def get_timeline(
        self,
        *,
        around_event_id: str | None = None,
        window_seconds: int = 300,
        limit: int = 100,
    ) -> dict[str, Any]:
        events = self.event_service.get_case_timeline(self.case_id)
        if around_event_id:
            try:
                center_id = uuid.UUID(around_event_id)
            except ValueError:
                return {"error": "Invalid around_event_id"}
            center = next((e for e in events if e.event_id == center_id), None)
            if center and center.corrected_timestamp:
                lo = center.corrected_timestamp - timedelta(seconds=window_seconds)
                hi = center.corrected_timestamp + timedelta(seconds=window_seconds)
                events = [
                    e
                    for e in events
                    if e.corrected_timestamp and lo <= e.corrected_timestamp <= hi
                ]
        events = events[:limit]
        return {
            "count": len(events),
            "window_seconds": window_seconds,
            "items": [self._serialize_event(e) for e in events],
        }

    def get_source_metadata(self, *, evidence_id: str | None = None) -> dict[str, Any]:
        artifacts = self.evidence.list_artifacts_for_case(self.case_id)
        if evidence_id:
            try:
                eid = uuid.UUID(evidence_id)
            except ValueError:
                return {"error": "Invalid evidence_id"}
            artifacts = [a for a in artifacts if a.evidence_id == eid]
            if not artifacts:
                return {"error": "Evidence not found"}
        return {
            "items": [
                {
                    "evidence_id": str(a.evidence_id),
                    "filename": a.filename,
                    "source_type": a.source_type.value
                    if hasattr(a.source_type, "value")
                    else str(a.source_type),
                    "sha256": a.sha256,
                    "processing_status": a.processing_status.value
                    if hasattr(a.processing_status, "value")
                    else str(a.processing_status),
                    "profile_id": a.profile_id,
                    "match_score": a.match_score,
                    "needs_review": a.needs_review,
                    "source_metadata": a.source_metadata,
                    "custody_history": a.custody_history or [],
                }
                for a in artifacts
            ]
        }

    def get_evidence_provenance(self, *, record_id: str) -> dict[str, Any]:
        try:
            rid = uuid.UUID(record_id)
        except ValueError:
            return {"error": "Invalid record_id"}
        record = self.evidence.get_record(rid)
        if record is None or record.case_id != self.case_id:
            return {"error": "Record not found"}
        artifact = self.evidence.get_artifact(record.evidence_id)
        return {
            "record_id": str(record.record_id),
            "evidence_id": str(record.evidence_id),
            "filename": artifact.filename if artifact else None,
            "sha256": artifact.sha256 if artifact else None,
            "field_provenance": record.field_provenance,
            "raw_data": record.raw_data,
            "normalized_data": record.normalized_data,
            "custody_history": (artifact.custody_history if artifact else []) or [],
        }

    def get_evidence_gaps(self) -> dict[str, Any]:
        """Heuristic gaps from domain features + sparse source coverage."""
        from app.services.domain_feature_service import DomainFeatureService

        artifacts = self.evidence.list_artifacts_for_case(self.case_id)
        present_types = {
            a.source_type.value if hasattr(a.source_type, "value") else str(a.source_type)
            for a in artifacts
        }
        expected = {
            "signal_log",
            "train_telemetry",
            "maintenance",
            "weather",
            "witness",
        }
        missing_sources = sorted(expected - present_types)

        features = DomainFeatureService(self.db).compute_for_case(self.case_id)
        missing_inputs: list[str] = []
        if features:
            for domain in features.domains:
                for item in domain.missing_inputs:
                    missing_inputs.append(f"{domain.domain}:{item}")

        failed = [
            {
                "evidence_id": str(a.evidence_id),
                "filename": a.filename,
                "error": a.error_detail,
            }
            for a in artifacts
            if (a.processing_status.value if hasattr(a.processing_status, "value") else str(a.processing_status))
            == "failed"
            or a.needs_review
        ]

        return {
            "missing_source_types": missing_sources,
            "missing_domain_inputs": missing_inputs,
            "needs_review_or_failed": failed,
        }

    def get_domain_features(self) -> dict[str, Any]:
        from app.services.domain_feature_service import DomainFeatureService

        result = DomainFeatureService(self.db).compute_for_case(self.case_id)
        if result is None:
            return {"error": "Case not found"}
        return result.model_dump(mode="json")

    def get_anomalies(self) -> dict[str, Any]:
        anomalies = self.quality.get_anomalies(self.case_id)
        return {
            "count": len(anomalies),
            "items": [
                {
                    "anomaly_id": str(a.anomaly_id),
                    "rule_id": a.rule_id,
                    "severity": a.severity.value
                    if hasattr(a.severity, "value")
                    else str(a.severity),
                    "title": a.title,
                    "explanation": a.explanation,
                    "affected_event_ids": [str(x) for x in (a.affected_event_ids or [])],
                    "evidence_refs": [str(x) for x in (a.evidence_refs or [])],
                }
                for a in anomalies
            ],
        }

    def get_conflicts(self) -> dict[str, Any]:
        conflicts = self.quality.get_conflicts(self.case_id)
        return {
            "count": len(conflicts),
            "items": [
                {
                    "conflict_id": str(c.conflict_id),
                    "conflict_type": c.conflict_type,
                    "severity": c.severity.value
                    if hasattr(c.severity, "value")
                    else str(c.severity),
                    "title": c.title,
                    "explanation": c.explanation,
                    "event_ids": [str(x) for x in (c.event_ids or [])],
                    "evidence_refs": [str(x) for x in (c.evidence_refs or [])],
                }
                for c in conflicts
            ],
        }

    @staticmethod
    def _serialize_event(event: Any) -> dict[str, Any]:
        return {
            "event_id": str(event.event_id),
            "evidence_id": str(event.evidence_id),
            "record_id": str(event.record_id) if event.record_id else None,
            "event_type": event.event_type,
            "raw_timestamp": _iso(event.raw_timestamp),
            "corrected_timestamp": _iso(event.corrected_timestamp),
            "temporal_confidence": event.temporal_confidence,
            "source_id": event.source_id,
            "entity_id": event.entity_id,
            "attributes": event.attributes or {},
            "evidence_refs": [str(x) for x in (event.evidence_refs or [])],
            "timeline_index": event.timeline_index,
        }
