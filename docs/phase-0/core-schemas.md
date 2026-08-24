# Core schema freeze

Approved field definitions for Phase 1 case ingestion. Mirror in Pydantic (`backend/app/schemas/`) and SQLAlchemy (`backend/app/models/`).

## Case

| Field | Type | Required | Notes |
|---|---|---|---|
| `case_id` | UUID | yes (PK) | Generated server-side |
| `title` | string | yes | Human-readable case title |
| `incident_time` | datetime (tz-aware) | no | Validated if present |
| `location` | JSON object | no | e.g. `{track, km, region}` |
| `status` | enum | yes | `open`, `ingesting`, `ready`, `investigating`, `closed` |
| `metadata` | JSON object | no | Free-form incident metadata |
| `created_at` | datetime | yes | UTC storage |
| `updated_at` | datetime | yes | UTC storage |

## EvidenceArtifact

| Field | Type | Required | Notes |
|---|---|---|---|
| `evidence_id` | UUID | yes (PK) | Generated server-side |
| `case_id` | UUID | yes (FK) | Parent case |
| `filename` | string | yes | Original upload name |
| `source_type` | enum | yes | `signal_log`, `train_telemetry`, `maintenance`, `weather`, `witness`, `other` |
| `file_size` | integer | yes | Bytes |
| `sha256` | string(64) | yes | Computed on upload |
| `acquisition_time` | datetime | yes | From metadata or upload time |
| `source_metadata` | JSON object | no | Source system, operator, device ID, timezone hint |
| `processing_status` | enum | yes | `pending`, `parsing`, `cleaning`, `completed`, `failed` |
| `parser_version` | string | no | Set after successful parse |
| `profile_id` | string | no | Selected ProcessingProfile id (e.g. `signal_log_v1`) |
| `match_score` | float | no | Profile match confidence 0..1 |
| `match_reasons` | JSON array | no | Auditable reasons for profile selection |
| `needs_review` | boolean | yes | True when match is low-confidence or conflicts with declared `source_type` |
| `custody_history` | JSON array | yes | `[{action, actor, timestamp, sha256}]` |
| `storage_path` | string | yes | Relative path under evidence store |
| `error_detail` | string | no | Populated on failure |
| `created_at` | datetime | yes | UTC storage |

## EvidenceRecord

| Field | Type | Required | Notes |
|---|---|---|---|
| `record_id` | UUID | yes (PK) | Generated server-side |
| `evidence_id` | UUID | yes (FK) | Parent artifact |
| `case_id` | UUID | yes (FK) | Denormalized for query efficiency |
| `record_index` | integer | yes | Row/segment index in source file |
| `raw_data` | JSON object | yes | Original parsed values (immutable) |
| `normalized_data` | JSON object | yes | Cleaned values after mapping |
| `field_provenance` | JSON array | no | Per-field `{field, raw, normalized, transform}` |
| `parse_warnings` | JSON array | no | Non-fatal issues |
| `is_valid` | boolean | yes | False if row failed validation |
| `created_at` | datetime | yes | UTC storage |

## Event

| Field | Type | Required | Notes |
|---|---|---|---|
| `event_id` | UUID | yes (PK) | Generated server-side |
| `case_id` | UUID | yes (FK) | Parent case |
| `evidence_id` | UUID | yes (FK) | Source artifact |
| `record_id` | UUID | yes (FK) | Source evidence record |
| `event_type` | string | yes | e.g. `SIGNAL_STATE_CHANGE`, `SPEED_SAMPLE` |
| `raw_timestamp` | datetime (tz-aware) | no | From cleaned record before correction |
| `corrected_timestamp` | datetime (tz-aware) | no | After temporal reconstruction |
| `temporal_confidence` | float | yes | 0..1 confidence in timestamp |
| `clock_offset_seconds` | float | no | Applied offset for this evidence source |
| `source_id` | string | no | Signal/equipment identifier |
| `entity_id` | string | no | Train or primary entity |
| `location` | JSON object | no | Inherited from case or record context |
| `attributes` | JSON object | yes | Domain-specific payload |
| `evidence_refs` | JSON array | yes | Linked evidence UUID strings |
| `timeline_index` | integer | no | Order in unified case timeline |
| `created_at` | datetime | yes | UTC storage |

## AuditEvent

| Field | Type | Required | Notes |
|---|---|---|---|
| `audit_id` | UUID | yes (PK) | Generated server-side |
| `case_id` | UUID | yes (FK) | Parent case |
| `entity_type` | string | yes | e.g. `case`, `evidence_artifact` |
| `entity_id` | UUID | yes | Changed entity |
| `action` | string | yes | e.g. `case.created`, `evidence.uploaded` |
| `actor` | string | yes | MVP: `system` |
| `payload` | JSON object | no | Action-specific details |
| `created_at` | datetime | yes | UTC storage |

## Relationships

- Case 1→N EvidenceArtifact
- EvidenceArtifact 1→N EvidenceRecord
- EvidenceRecord 1→N Event
- Case 1→N Event
- Case 1→N AuditEvent

## Validation rules

- All timestamps stored as UTC; API returns ISO8601.
- SHA-256 must be 64 hex characters.
- Original evidence files are immutable once stored.
- When a field is transformed during cleaning, both raw and normalized values are preserved in `field_provenance`.
- Malformed rows are retained with `is_valid=false` and warnings; never silently dropped.
