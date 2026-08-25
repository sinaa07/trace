import { useCallback, useEffect, useState } from "react";
import {
  createCase,
  deleteEvidence,
  getCase,
  listCaseEvidence,
  updateCase,
  uploadEvidence,
} from "../services/api";
import {
  getInvestigatorName,
  setInvestigatorName,
} from "../services/investigator";
import type {
  Case,
  EvidenceArtifact,
  SourceType,
} from "../types/case";

const SOURCE_TYPES: { value: SourceType; label: string }[] = [
  { value: "signal_log", label: "Signal Log" },
  { value: "train_telemetry", label: "Train Telemetry" },
  { value: "maintenance", label: "Maintenance Report" },
  { value: "weather", label: "Weather Data" },
  { value: "witness", label: "Witness Statement" },
  { value: "other", label: "Other" },
];

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getUploader(artifact: EvidenceArtifact): string {
  const uploaded = artifact.custody_history.find((e) => e.action === "uploaded");
  return uploaded?.actor ?? artifact.source_metadata?.operator?.toString() ?? "system";
}

function toLocalInputValue(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

interface CaseFormState {
  title: string;
  incidentTime: string;
  track: string;
  km: string;
  description: string;
}

const emptyCaseForm = (): CaseFormState => ({
  title: "",
  incidentTime: "",
  track: "",
  km: "",
  description: "",
});

export function CaseIngestionPage() {
  const [investigator, setInvestigator] = useState(getInvestigatorName());
  const [caseForm, setCaseForm] = useState<CaseFormState>(emptyCaseForm);
  const [editMode, setEditMode] = useState(false);
  const [activeCase, setActiveCase] = useState<Case | null>(null);
  const [evidence, setEvidence] = useState<EvidenceArtifact[]>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [sourceType, setSourceType] = useState<SourceType>("signal_log");
  const [sourceSystem, setSourceSystem] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const refreshEvidence = useCallback(async (caseId: string) => {
    const list = await listCaseEvidence(caseId);
    setEvidence(list.items);
  }, []);

  const loadCase = useCallback(
    async (caseId: string) => {
      const data = await getCase(caseId);
      setActiveCase(data);
      setCaseForm({
        title: data.title,
        incidentTime: toLocalInputValue(data.incident_time),
        track: data.location?.track?.toString() ?? "",
        km: data.location?.km?.toString() ?? "",
        description: (data.metadata?.description as string) ?? "",
      });
      await refreshEvidence(caseId);
    },
    [refreshEvidence],
  );

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const caseId = params.get("case");
    if (caseId) {
      loadCase(caseId).catch((err: Error) =>
        setError(err.message ?? "Failed to load case"),
      );
    }
  }, [loadCase]);

  function handleInvestigatorSave() {
    if (!investigator.trim()) {
      setError("Investigator name is required for chain-of-custody tracking.");
      return;
    }
    setInvestigatorName(investigator.trim());
    setSuccess("Investigator identity saved for this session.");
    setError(null);
  }

  async function handleCreateCase(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    const name = investigator.trim() || getInvestigatorName();
    if (!name) {
      setError("Set your investigator name before creating a case.");
      return;
    }
    if (!caseForm.title.trim()) {
      setError("Case title is required.");
      return;
    }

    setLoading(true);
    try {
      const location =
        caseForm.track || caseForm.km
          ? {
              ...(caseForm.track ? { track: caseForm.track } : {}),
              ...(caseForm.km ? { km: caseForm.km } : {}),
            }
          : null;

      const payload = {
        title: caseForm.title.trim(),
        incident_time: caseForm.incidentTime
          ? new Date(caseForm.incidentTime).toISOString()
          : null,
        location,
        created_by: name,
        metadata: caseForm.description.trim()
          ? { description: caseForm.description.trim() }
          : null,
      };

      const created = editMode && activeCase
        ? await updateCase(activeCase.case_id, payload)
        : await createCase(payload);

      setActiveCase(created);
      setEditMode(false);
      setSuccess(
        editMode
          ? "Case details updated."
          : "Case created. Upload evidence documents below.",
      );
      window.history.replaceState(
        {},
        "",
        `/ingestion?case=${created.case_id}`,
      );
      await refreshEvidence(created.case_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save case");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!activeCase) {
      setError("Create a case before uploading evidence.");
      return;
    }
    const name = investigator.trim() || getInvestigatorName();
    if (!name) {
      setError("Set your investigator name before uploading.");
      return;
    }
    if (!uploadFile) {
      setError("Select a file to upload.");
      return;
    }

    setLoading(true);
    try {
      const metadata: Record<string, unknown> = {
        operator: name,
        acquisition_time: new Date().toISOString(),
      };
      if (sourceSystem.trim()) {
        metadata.source_system = sourceSystem.trim();
      }

      await uploadEvidence(
        activeCase.case_id,
        uploadFile,
        sourceType,
        name,
        metadata,
      );

      setUploadFile(null);
      setSourceSystem("");
      setSuccess(`Uploaded ${uploadFile.name} — custody entry recorded.`);
      await Promise.all([
        refreshEvidence(activeCase.case_id),
        loadCase(activeCase.case_id),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(item: EvidenceArtifact) {
    const name = investigator.trim() || getInvestigatorName();
    if (!name) {
      setError("Set your investigator name to perform custody actions.");
      return;
    }

    const uploader = getUploader(item);
    if (name === uploader) {
      setError(
        "You cannot delete evidence you uploaded. Chain-of-custody requires a different investigator to remove artifacts.",
      );
      return;
    }

    if (
      !window.confirm(
        `Remove "${item.filename}" uploaded by ${uploader}? This action is audit-logged.`,
      )
    ) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await deleteEvidence(item.evidence_id, name);
      setSuccess(`Evidence "${item.filename}" removed by ${name}.`);
      if (activeCase) {
        await Promise.all([
          refreshEvidence(activeCase.case_id),
          loadCase(activeCase.case_id),
        ]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setLoading(false);
    }
  }

  function startNewCase() {
    setActiveCase(null);
    setEvidence([]);
    setEditMode(false);
    setCaseForm(emptyCaseForm());
    setError(null);
    setSuccess(null);
    window.history.replaceState({}, "", "/ingestion");
  }

  const currentInvestigator = investigator.trim() || getInvestigatorName();

  return (
    <>
      <div className="page-header">
        <h1>Case Ingestion</h1>
        <p>
          Create an investigation case with incident metadata, then upload
          source documents. Every upload records the investigator, timestamp,
          and SHA-256 hash in the chain of custody.
        </p>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <section className="panel">
        <h2>Investigator Identity</h2>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="investigator">Your name / badge ID</label>
            <input
              id="investigator"
              value={investigator}
              onChange={(e) => setInvestigator(e.target.value)}
              placeholder="e.g. Inspector Sharma"
            />
          </div>
        </div>
        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={handleInvestigatorSave}>
            Save Identity
          </button>
        </div>
      </section>

      {activeCase && (
        <div className="case-status-bar">
          <span>
            Case ID:<strong>{activeCase.case_id.slice(0, 8)}…</strong>
          </span>
          <span>
            Status:<strong>{activeCase.status}</strong>
          </span>
          <span>
            Created by:<strong>{activeCase.created_by ?? "—"}</strong>
          </span>
          <span>
            Evidence:<strong>{activeCase.evidence_count}</strong>
          </span>
          <span>
            Created:<strong>{formatDateTime(activeCase.created_at)}</strong>
          </span>
        </div>
      )}

      <section className="panel">
        <h2>{activeCase ? (editMode ? "Edit Case Details" : "Case Details") : "New Case"}</h2>
        <form onSubmit={handleCreateCase}>
          <div className="form-grid">
            <div className="form-field full-width">
              <label htmlFor="title">Case title *</label>
              <input
                id="title"
                value={caseForm.title}
                onChange={(e) =>
                  setCaseForm((f) => ({ ...f, title: e.target.value }))
                }
                placeholder="e.g. Derailment at KM 142 — Northern Line"
                required
                disabled={!!activeCase && !editMode}
              />
            </div>
            <div className="form-field">
              <label htmlFor="incidentTime">Incident date & time</label>
              <input
                id="incidentTime"
                type="datetime-local"
                value={caseForm.incidentTime}
                onChange={(e) =>
                  setCaseForm((f) => ({ ...f, incidentTime: e.target.value }))
                }
                disabled={!!activeCase && !editMode}
              />
            </div>
            <div className="form-field">
              <label htmlFor="track">Track / section</label>
              <input
                id="track"
                value={caseForm.track}
                onChange={(e) =>
                  setCaseForm((f) => ({ ...f, track: e.target.value }))
                }
                placeholder="e.g. T12"
                disabled={!!activeCase && !editMode}
              />
            </div>
            <div className="form-field">
              <label htmlFor="km">Kilometre marker</label>
              <input
                id="km"
                value={caseForm.km}
                onChange={(e) =>
                  setCaseForm((f) => ({ ...f, km: e.target.value }))
                }
                placeholder="e.g. 142.5"
                disabled={!!activeCase && !editMode}
              />
            </div>
            <div className="form-field full-width">
              <label htmlFor="description">Incident description</label>
              <textarea
                id="description"
                value={caseForm.description}
                onChange={(e) =>
                  setCaseForm((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="Brief summary of the accident circumstances…"
                disabled={!!activeCase && !editMode}
              />
            </div>
          </div>
          <div className="form-actions">
            {activeCase && !editMode ? (
              <>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setEditMode(true)}
                >
                  Edit Case
                </button>
                <button type="button" className="btn btn-secondary" onClick={startNewCase}>
                  New Case
                </button>
              </>
            ) : (
              <>
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading
                    ? "Saving…"
                    : activeCase && editMode
                      ? "Save Changes"
                      : "Create Case"}
                </button>
                {editMode && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setEditMode(false);
                      if (activeCase) loadCase(activeCase.case_id);
                    }}
                  >
                    Cancel
                  </button>
                )}
              </>
            )}
          </div>
        </form>
      </section>

      {activeCase && (
        <>
          <section className="panel">
            <h2>Upload Evidence</h2>
            <form onSubmit={handleUpload}>
              <div className="form-grid">
                <div className="form-field">
                  <label htmlFor="file">Document / data file *</label>
                  <input
                    id="file"
                    type="file"
                    accept=".csv,.json,.txt,.pdf"
                    onChange={(e) =>
                      setUploadFile(e.target.files?.[0] ?? null)
                    }
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="sourceType">Source type *</label>
                  <select
                    id="sourceType"
                    value={sourceType}
                    onChange={(e) =>
                      setSourceType(e.target.value as SourceType)
                    }
                  >
                    {SOURCE_TYPES.map((st) => (
                      <option key={st.value} value={st.value}>
                        {st.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="sourceSystem">Source system (optional)</label>
                  <input
                    id="sourceSystem"
                    value={sourceSystem}
                    onChange={(e) => setSourceSystem(e.target.value)}
                    placeholder="e.g. SCADA-East"
                  />
                </div>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading ? "Uploading…" : "Upload & Ingest"}
                </button>
              </div>
            </form>
          </section>

          <section className="panel">
            <h2>Uploaded Data ({evidence.length})</h2>
            {evidence.length === 0 ? (
              <div className="empty-state">
                No evidence uploaded yet. Add signal logs, telemetry, maintenance
                reports, or witness documents above.
              </div>
            ) : (
              <div className="evidence-list">
                {evidence.map((item) => {
                  const uploader = getUploader(item);
                  const canDelete =
                    currentInvestigator && currentInvestigator !== uploader;

                  return (
                    <article key={item.evidence_id} className="evidence-item">
                      <div className="evidence-item-header">
                        <div>
                          <h3>{item.filename}</h3>
                          <div className="evidence-meta">
                            Uploaded by <strong>{uploader}</strong> on{" "}
                            {formatDateTime(item.created_at)} ·{" "}
                            {formatFileSize(item.file_size)} ·{" "}
                            {item.record_count} records · SHA-256{" "}
                            <code>{item.sha256.slice(0, 12)}…</code>
                          </div>
                        </div>
                        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                          <span
                            className={`status-pill ${item.processing_status}`}
                          >
                            {item.processing_status}
                          </span>
                          {canDelete ? (
                            <button
                              type="button"
                              className="btn btn-danger"
                              disabled={loading}
                              onClick={() => handleDelete(item)}
                            >
                              Remove
                            </button>
                          ) : (
                            <span
                              className="evidence-meta"
                              title="Only a different investigator may remove uploaded evidence"
                            >
                              {currentInvestigator === uploader
                                ? "Cannot self-delete"
                                : "Set identity to remove"}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="evidence-meta">
                        Source: {item.source_type.replace("_", " ")}
                        {item.profile_id && ` · Profile: ${item.profile_id}`}
                        {item.needs_review && " · Needs review"}
                      </div>

                      <div className="custody-chain">
                        <h4>Chain of Custody</h4>
                        {item.custody_history.map((entry, idx) => (
                          <div key={idx} className="custody-entry">
                            <span className="action">{entry.action}</span>
                            <span>{entry.actor}</span>
                            <span>{formatDateTime(entry.timestamp)}</span>
                          </div>
                        ))}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}

            {evidence.length > 0 && (
              <div className="alert alert-info" style={{ marginTop: "1rem" }}>
                To add more evidence, use the upload form above. Removal requires
                a different investigator than the original uploader to preserve
                chain-of-custody integrity.
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}
