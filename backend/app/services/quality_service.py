from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.anomalies.engine import AnomalyRuleEngine
from app.core.conflicts.detector import ConflictDetector
from app.models import Anomaly, EvidenceConflict
from app.services.audit import AuditService
from app.services.storage.repositories.event_repo import EventRepository
from app.services.storage.repositories.quality_repo import QualityRepository


class QualityAnalysisService:
    def __init__(
        self,
        db: Session,
        *,
        anomaly_engine: AnomalyRuleEngine | None = None,
        conflict_detector: ConflictDetector | None = None,
    ) -> None:
        self.db = db
        self.event_repo = EventRepository(db)
        self.quality_repo = QualityRepository(db)
        self.audit = AuditService(db)
        self.anomaly_engine = anomaly_engine or AnomalyRuleEngine()
        self.conflict_detector = conflict_detector or ConflictDetector()

    def analyze_case(self, case_id: uuid.UUID, *, actor: str = "system") -> tuple[int, int]:
        events = self.event_repo.list_for_case(case_id)

        anomaly_findings = self.anomaly_engine.evaluate(events)
        db_anomalies = [
            Anomaly(
                case_id=case_id,
                rule_id=f.rule_id,
                severity=f.severity,
                title=f.title,
                explanation=f.explanation,
                affected_event_ids=f.affected_event_ids,
                evidence_refs=f.evidence_refs,
                details=f.details,
            )
            for f in anomaly_findings
        ]
        self.quality_repo.replace_anomalies(case_id, db_anomalies)

        conflict_findings = self.conflict_detector.evaluate(events)
        db_conflicts = [
            EvidenceConflict(
                case_id=case_id,
                conflict_type=f.conflict_type,
                severity=f.severity,
                title=f.title,
                explanation=f.explanation,
                event_ids=f.event_ids,
                evidence_refs=f.evidence_refs,
                details=f.details,
            )
            for f in conflict_findings
        ]
        self.quality_repo.replace_conflicts(case_id, db_conflicts)

        self.audit.log(
            case_id=case_id,
            entity_type="case",
            entity_id=case_id,
            action="quality.analyzed",
            payload={
                "anomaly_count": len(db_anomalies),
                "conflict_count": len(db_conflicts),
            },
            actor=actor,
        )
        return len(db_anomalies), len(db_conflicts)

    def get_anomalies(self, case_id: uuid.UUID):
        return self.quality_repo.list_anomalies(case_id)

    def get_conflicts(self, case_id: uuid.UUID):
        return self.quality_repo.list_conflicts(case_id)
