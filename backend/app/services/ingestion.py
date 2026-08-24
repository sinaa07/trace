import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.parsers.registry import ParserRegistry
from app.core.processing.cleaner import DomainProcessor
from app.core.processing.registry import ProcessingProfileRegistry
from app.models import CaseStatus, EvidenceArtifact, EvidenceRecord, ProcessingStatus, SourceType
from app.services.audit import AuditService
from app.services.event_service import EventService
from app.services.provenance import ProvenanceService
from app.services.storage.file_store import FileStore
from app.services.storage.repositories.case_repo import CaseRepository
from app.services.storage.repositories.evidence_repo import EvidenceRepository


class DuplicateEvidenceError(Exception):
    def __init__(self, sha256: str) -> None:
        self.sha256 = sha256
        super().__init__(f"Duplicate evidence hash for case: {sha256}")


class IngestionOrchestrator:
    def __init__(
        self,
        db: Session,
        file_store: FileStore | None = None,
        parser_registry: ParserRegistry | None = None,
        domain_processor: DomainProcessor | None = None,
        profile_registry: ProcessingProfileRegistry | None = None,
    ) -> None:
        self.db = db
        self.file_store = file_store or FileStore()
        self.parser_registry = parser_registry or ParserRegistry()
        registry = profile_registry or ProcessingProfileRegistry()
        self.domain_processor = domain_processor or DomainProcessor(registry=registry)
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.audit = AuditService(db)
        self.provenance = ProvenanceService()
        self.event_service = EventService(db, profile_registry=registry)

    async def ingest(
        self,
        case_id: uuid.UUID,
        filename: str,
        content: bytes,
        source_type: SourceType,
        source_metadata: dict[str, Any] | None = None,
        mime: str | None = None,
        actor: str = "system",
    ) -> EvidenceArtifact:
        case = self.case_repo.get(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")

        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise ValueError(
                f"File exceeds maximum upload size of {settings.max_upload_size_mb}MB"
            )

        sha256 = self.provenance.compute_sha256(content)
        if settings.reject_duplicate_hash:
            existing = self.evidence_repo.find_by_sha256_for_case(case_id, sha256)
            if existing:
                raise DuplicateEvidenceError(sha256)

        self.case_repo.update_status(case, CaseStatus.INGESTING)
        evidence_id = uuid.uuid4()
        storage_path = self.file_store.store_raw(
            case_id, evidence_id, filename, content
        )

        merged_metadata = dict(source_metadata or {})
        acquisition_time = merged_metadata.get("acquisition_time")
        if isinstance(acquisition_time, str):
            acquisition_time = datetime.fromisoformat(acquisition_time)
        if not isinstance(acquisition_time, datetime):
            acquisition_time = datetime.now(timezone.utc)

        artifact = EvidenceArtifact(
            evidence_id=evidence_id,
            case_id=case_id,
            filename=filename,
            source_type=source_type,
            file_size=len(content),
            sha256=sha256,
            acquisition_time=acquisition_time,
            source_metadata=merged_metadata or None,
            processing_status=ProcessingStatus.PENDING,
            custody_history=self.provenance.initial_custody_entry(sha256, actor),
            storage_path=storage_path,
            needs_review=False,
        )
        self.evidence_repo.create_artifact(artifact)
        self.audit.log(
            case_id=case_id,
            entity_type="evidence_artifact",
            entity_id=evidence_id,
            action="evidence.uploaded",
            payload={"filename": filename, "sha256": sha256},
            actor=actor,
        )
        self.db.commit()

        try:
            artifact.processing_status = ProcessingStatus.PARSING
            self.db.commit()

            file_path = self.file_store.absolute_raw_path(storage_path)
            parse_result = self.parser_registry.parse(file_path, filename, mime)

            hints = parse_result.source_metadata_hints
            if hints:
                merged = dict(artifact.source_metadata or {})
                merged.update({k: v for k, v in hints.items() if k not in merged})
                artifact.source_metadata = merged

            artifact.processing_status = ProcessingStatus.CLEANING
            self.db.commit()

            cleaned_records, selection = self.domain_processor.select_and_clean(
                parse_result.records,
                source_type,
                filename=filename,
                source_metadata=artifact.source_metadata,
                parse_warnings=parse_result.warnings,
            )

            artifact.profile_id = selection.profile.id
            artifact.match_score = selection.match_score
            artifact.match_reasons = selection.match_reasons
            artifact.needs_review = selection.needs_review

            db_records = [
                EvidenceRecord(
                    evidence_id=evidence_id,
                    case_id=case_id,
                    record_index=idx,
                    raw_data=rec.raw_data,
                    normalized_data=rec.normalized_data,
                    field_provenance=rec.field_provenance,
                    parse_warnings=rec.parse_warnings,
                    is_valid=rec.is_valid,
                )
                for idx, rec in enumerate(cleaned_records)
            ]
            self.evidence_repo.bulk_create_records(db_records)

            manifest = {
                "evidence_id": str(evidence_id),
                "case_id": str(case_id),
                "filename": filename,
                "record_count": len(db_records),
                "invalid_count": sum(1 for r in db_records if not r.is_valid),
                "parser_version": parse_result.parser_version,
                "profile_id": selection.profile.id,
                "profile_version": selection.profile.version,
                "match_score": selection.match_score,
                "match_reasons": selection.match_reasons,
                "needs_review": selection.needs_review,
                "warnings": parse_result.warnings,
            }
            self.file_store.write_manifest(case_id, evidence_id, manifest)

            artifact.processing_status = ProcessingStatus.COMPLETED
            artifact.parser_version = parse_result.parser_version
            artifact.custody_history = self.provenance.append_custody_entry(
                artifact.custody_history, "parsed", sha256, actor
            )
            self.audit.log(
                case_id=case_id,
                entity_type="evidence_artifact",
                entity_id=evidence_id,
                action="evidence.parsed",
                payload={
                    "record_count": len(db_records),
                    "parser_version": parse_result.parser_version,
                    "profile_id": selection.profile.id,
                    "match_score": selection.match_score,
                    "needs_review": selection.needs_review,
                },
                actor=actor,
            )
            self.case_repo.update_status(case, CaseStatus.READY)
            self.db.commit()
            self.db.refresh(artifact)

            try:
                event_count = self.event_service.extract_for_artifact(
                    artifact, actor=actor, rebuild_timeline=True
                )
                manifest["event_count"] = event_count
                self.file_store.write_manifest(case_id, evidence_id, manifest)
            except Exception as event_exc:
                self.audit.log(
                    case_id=case_id,
                    entity_type="evidence_artifact",
                    entity_id=evidence_id,
                    action="events.extract_failed",
                    payload={"error": str(event_exc)},
                    actor=actor,
                )
                self.db.commit()

            return artifact

        except Exception as exc:
            artifact.processing_status = ProcessingStatus.FAILED
            artifact.error_detail = str(exc)
            artifact.custody_history = self.provenance.append_custody_entry(
                artifact.custody_history, "parse_failed", sha256, actor
            )
            self.audit.log(
                case_id=case_id,
                entity_type="evidence_artifact",
                entity_id=evidence_id,
                action="evidence.parse_failed",
                payload={"error": str(exc)},
                actor=actor,
            )
            self.db.commit()
            raise

    def get_artifact_summary(self, evidence_id: uuid.UUID) -> tuple[EvidenceArtifact | None, int, int, int]:
        artifact = self.evidence_repo.get_artifact(evidence_id)
        if not artifact:
            return None, 0, 0, 0
        total, invalid, warnings = self.evidence_repo.record_stats(evidence_id)
        return artifact, total, invalid, warnings
