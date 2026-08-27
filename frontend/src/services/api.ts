import type {
  AnomaliesListResponse,
  ApiError,
  Case,
  CaseCreatePayload,
  CaseListResponse,
  CaseUpdatePayload,
  ConflictsListResponse,
  EvidenceArtifact,
  EvidenceListResponse,
  EvidenceRecord,
  EvidenceRecordsListResponse,
  EvidenceRecordsQuery,
  FindingsListResponse,
  HypothesesListResponse,
  InvestigationRunResponse,
  SourceType,
  TimelineResponse,
} from "../types/case";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function parseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as ApiError | { detail: ApiError };
    const err =
      "detail" in body && body.detail?.error
        ? body.detail.error
        : "error" in body
          ? body.error
          : null;
    if (err?.message) return err.message;
  } catch {
    /* ignore */
  }
  return `Request failed (${response.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error(
      "Unable to reach TRACE API. Confirm the backend is running on port 8000.",
    );
  }
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function createCase(payload: CaseCreatePayload): Promise<Case> {
  return request<Case>("/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listCases(
  limit = 100,
  offset = 0,
): Promise<CaseListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return request<CaseListResponse>(`/cases?${params}`);
}

export async function getCase(caseId: string): Promise<Case> {
  return request<Case>(`/cases/${caseId}`);
}

export async function updateCase(
  caseId: string,
  payload: CaseUpdatePayload,
): Promise<Case> {
  return request<Case>(`/cases/${caseId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listCaseEvidence(
  caseId: string,
): Promise<EvidenceListResponse> {
  return request<EvidenceListResponse>(`/cases/${caseId}/evidence`);
}

export async function listCaseRecords(
  caseId: string,
  query: EvidenceRecordsQuery = {},
): Promise<EvidenceRecordsListResponse> {
  const params = new URLSearchParams();
  if (query.evidence_id) params.set("evidence_id", query.evidence_id);
  if (query.source_type) params.set("source_type", query.source_type);
  if (query.is_valid === true || query.is_valid === false) {
    params.set("is_valid", String(query.is_valid));
  }
  if (query.has_warnings === true || query.has_warnings === false) {
    params.set("has_warnings", String(query.has_warnings));
  }
  if (query.q?.trim()) params.set("q", query.q.trim());
  if (query.limit != null) params.set("limit", String(query.limit));
  if (query.offset != null) params.set("offset", String(query.offset));
  const qs = params.toString();
  return request<EvidenceRecordsListResponse>(
    `/cases/${caseId}/records${qs ? `?${qs}` : ""}`,
  );
}

export async function getEvidenceRecord(
  recordId: string,
): Promise<EvidenceRecord> {
  return request<EvidenceRecord>(`/evidence/records/${recordId}`);
}

export async function uploadEvidence(
  caseId: string,
  file: File,
  sourceType: SourceType,
  actor: string,
  sourceMetadata?: Record<string, unknown>,
): Promise<EvidenceArtifact> {
  const form = new FormData();
  form.append("file", file);
  form.append("source_type", sourceType);
  form.append("actor", actor);
  if (sourceMetadata && Object.keys(sourceMetadata).length > 0) {
    form.append("source_metadata", JSON.stringify(sourceMetadata));
  }

  return request<EvidenceArtifact>(`/cases/${caseId}/evidence`, {
    method: "POST",
    body: form,
  });
}

export async function deleteEvidence(
  evidenceId: string,
  actor: string,
): Promise<void> {
  const params = new URLSearchParams({ actor });
  return request<void>(`/evidence/${evidenceId}?${params}`, {
    method: "DELETE",
  });
}

export async function getEvidence(
  evidenceId: string,
): Promise<EvidenceArtifact> {
  return request<EvidenceArtifact>(`/evidence/${evidenceId}`);
}

export async function getCaseTimeline(
  caseId: string,
): Promise<TimelineResponse> {
  return request<TimelineResponse>(`/cases/${caseId}/timeline`);
}

export async function rebuildCaseTimeline(
  caseId: string,
): Promise<TimelineResponse> {
  return request<TimelineResponse>(`/cases/${caseId}/timeline/rebuild`, {
    method: "POST",
  });
}

export async function listCaseAnomalies(
  caseId: string,
): Promise<AnomaliesListResponse> {
  return request<AnomaliesListResponse>(`/cases/${caseId}/anomalies`);
}

export async function listCaseConflicts(
  caseId: string,
): Promise<ConflictsListResponse> {
  return request<ConflictsListResponse>(`/cases/${caseId}/conflicts`);
}

export async function runInvestigation(
  caseId: string,
  actor = "investigator",
): Promise<InvestigationRunResponse> {
  return request<InvestigationRunResponse>(`/cases/${caseId}/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor, replace_existing: true }),
  });
}

export async function listCaseFindings(
  caseId: string,
): Promise<FindingsListResponse> {
  return request<FindingsListResponse>(`/cases/${caseId}/findings`);
}

export async function listCaseHypotheses(
  caseId: string,
): Promise<HypothesesListResponse> {
  return request<HypothesesListResponse>(`/cases/${caseId}/hypotheses`);
}
