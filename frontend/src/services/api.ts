import type {
  ApiError,
  Case,
  CaseCreatePayload,
  CaseUpdatePayload,
  EvidenceArtifact,
  EvidenceListResponse,
  SourceType,
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

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
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
