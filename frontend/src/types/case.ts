export type CaseStatus =
  | "open"
  | "ingesting"
  | "ready"
  | "investigating"
  | "closed";

export type SourceType =
  | "signal_log"
  | "train_telemetry"
  | "maintenance"
  | "weather"
  | "witness"
  | "other";

export type ProcessingStatus =
  | "pending"
  | "parsing"
  | "cleaning"
  | "completed"
  | "failed";

export type Severity = "low" | "medium" | "high" | "critical";

export interface CaseLocation {
  track?: string;
  km?: string | number;
  region?: string;
}

export interface Case {
  case_id: string;
  title: string;
  incident_time: string | null;
  location: CaseLocation | null;
  status: CaseStatus;
  metadata: Record<string, unknown> | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  evidence_count: number;
}

export interface CaseCreatePayload {
  title: string;
  incident_time?: string | null;
  location?: CaseLocation | null;
  metadata?: Record<string, unknown> | null;
  created_by?: string | null;
}

export interface CaseUpdatePayload {
  title?: string;
  incident_time?: string | null;
  location?: CaseLocation | null;
  metadata?: Record<string, unknown> | null;
}

export interface CaseListResponse {
  items: Case[];
  total: number;
  limit: number;
  offset: number;
}

export interface CustodyEntry {
  action: string;
  actor: string;
  timestamp: string;
  sha256: string;
}

export interface EvidenceArtifact {
  evidence_id: string;
  case_id: string;
  filename: string;
  source_type: SourceType;
  file_size: number;
  sha256: string;
  acquisition_time: string;
  source_metadata: Record<string, unknown> | null;
  processing_status: ProcessingStatus;
  parser_version: string | null;
  profile_id: string | null;
  match_score: number | null;
  match_reasons: string[] | null;
  needs_review: boolean;
  custody_history: CustodyEntry[];
  storage_path: string;
  error_detail: string | null;
  created_at: string;
  record_count: number;
  warning_count: number;
  invalid_record_count: number;
}

export interface EvidenceListResponse {
  case_id: string;
  items: EvidenceArtifact[];
  total: number;
}

export interface FieldProvenance {
  field: string;
  raw?: unknown;
  normalized?: unknown;
  transform?: string;
}

export interface EvidenceRecord {
  record_id: string;
  evidence_id: string;
  case_id: string;
  record_index: number;
  raw_data: Record<string, unknown>;
  normalized_data: Record<string, unknown>;
  field_provenance: FieldProvenance[] | null;
  parse_warnings: string[] | null;
  is_valid: boolean;
  created_at: string;
  filename?: string | null;
  source_type?: SourceType | null;
  sha256?: string | null;
}

export interface EvidenceRecordsListResponse {
  case_id: string;
  items: EvidenceRecord[];
  total: number;
  limit: number;
  offset: number;
  filters: Record<string, unknown>;
}

export interface EvidenceRecordsQuery {
  evidence_id?: string;
  source_type?: SourceType | "";
  is_valid?: boolean | "";
  has_warnings?: boolean | "";
  q?: string;
  limit?: number;
  offset?: number;
}

export interface TimelineEvent {
  event_id: string;
  case_id: string;
  evidence_id: string;
  record_id: string;
  event_type: string;
  raw_timestamp: string | null;
  corrected_timestamp: string | null;
  temporal_confidence: number;
  clock_offset_seconds: number | null;
  clock_drift_factor: number | null;
  source_id: string | null;
  entity_id: string | null;
  location: Record<string, unknown> | null;
  attributes: Record<string, unknown>;
  evidence_refs: string[];
  timeline_index: number | null;
  created_at: string;
}

export interface TimelineResponse {
  case_id: string;
  event_count: number;
  events: TimelineEvent[];
  rebuilt_at: string | null;
}

export interface Anomaly {
  anomaly_id: string;
  case_id: string;
  rule_id: string;
  severity: Severity;
  title: string;
  explanation: string;
  affected_event_ids: string[];
  evidence_refs: string[];
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface EvidenceConflict {
  conflict_id: string;
  case_id: string;
  conflict_type: string;
  severity: Severity;
  title: string;
  explanation: string;
  event_ids: string[];
  evidence_refs: string[];
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface AnomaliesListResponse {
  case_id: string;
  anomaly_count: number;
  anomalies: Anomaly[];
}

export interface ConflictsListResponse {
  case_id: string;
  conflict_count: number;
  conflicts: EvidenceConflict[];
}

export interface HypothesisFinding {
  finding_id: string;
  case_id: string;
  agent_id: string;
  domain: string;
  hypothesis: string;
  reasoning: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  relevant_events: string[];
  missing_evidence: string[];
  assumptions: string[];
  reasoning_summary: string;
  confidence: number;
  uncertainty: string | null;
  domain_features: Record<string, unknown> | null;
  rank_score: number | null;
  created_at: string;
}

export interface RankingDimensionScores {
  evidence_support: number;
  temporal_consistency: number;
  source_reliability: number;
  causal_support: number;
  evidence_completeness: number;
  contradiction_penalty: number;
}

export interface RankedHypothesis {
  finding: HypothesisFinding;
  dimensions: RankingDimensionScores;
  weighted_score: number;
}

export interface InvestigationRunResponse {
  case_id: string;
  run_id: string;
  generated_at: string;
  provider: string;
  meta_summary: string;
  findings: HypothesisFinding[];
  ranked: RankedHypothesis[];
}

export interface FindingsListResponse {
  case_id: string;
  findings: HypothesisFinding[];
  total: number;
}

export interface HypothesesListResponse {
  case_id: string;
  hypotheses: RankedHypothesis[];
  total: number;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
