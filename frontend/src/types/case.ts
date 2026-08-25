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

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
