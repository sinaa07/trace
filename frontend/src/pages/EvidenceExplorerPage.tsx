import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  CaseWorkspaceBanner,
  formatDateTime,
  formatJson,
} from "../components/CaseWorkspaceBanner";
import {
  getCase,
  listCaseEvidence,
  listCaseRecords,
} from "../services/api";
import {
  getActiveCaseId,
  setActiveCaseId,
} from "../services/workspace";
import type {
  Case,
  EvidenceArtifact,
  EvidenceRecord,
  SourceType,
} from "../types/case";

const SOURCE_TYPES: SourceType[] = [
  "signal_log",
  "train_telemetry",
  "maintenance",
  "weather",
  "witness",
  "other",
];

/** Prefer domain identity fields over repeating the filename as the row title. */
function recordTitle(record: EvidenceRecord): string {
  const data = {
    ...(record.raw_data ?? {}),
    ...(record.normalized_data ?? {}),
  } as Record<string, unknown>;

  const pick = (...keys: string[]): string | null => {
    for (const key of keys) {
      const value = data[key];
      if (value != null && String(value).trim() !== "") {
        return String(value).trim();
      }
    }
    return null;
  };

  const station =
    pick("station_name", "station", "station_code") ??
    pick("location_name");
  const signal = pick("signal_id", "signal", "signal_name");
  const train = pick("train_id", "train", "loco_id");
  const equipment = pick("equipment_id", "asset_id");
  const eventType = pick("event_type", "event", "message");
  const seq = pick("seq", "sequence", "row", "index");

  if (station && seq) return `${station} · stop ${seq}`;
  if (station) return station;
  if (signal && train) return `${signal} · ${train}`;
  if (signal) return `Signal ${signal}`;
  if (train) return `Train ${train}`;
  if (equipment) return `Equipment ${equipment}`;
  if (eventType) return eventType;

  const preview = Object.entries(record.normalized_data ?? {})
    .filter(([, v]) => v != null && String(v).trim() !== "")
    .slice(0, 2)
    .map(([k, v]) => `${k}=${String(v)}`)
    .join(" · ");
  return preview || `Row ${record.record_index}`;
}

function recordSubtitle(record: EvidenceRecord): string {
  const data = record.normalized_data ?? {};
  const bits: string[] = [];
  if (record.source_type) bits.push(record.source_type.replace(/_/g, " "));
  for (const key of ["track", "km_marker", "state", "speed", "timestamp"]) {
    if (data[key] != null && String(data[key]).trim() !== "") {
      bits.push(`${key}=${String(data[key])}`);
    }
    if (bits.length >= 4) break;
  }
  bits.push(record.filename ?? "artifact");
  bits.push(`row ${record.record_index}`);
  return bits.join(" · ");
}

export function EvidenceExplorerPage() {
  const [params, setParams] = useSearchParams();
  const caseId = params.get("case") || getActiveCaseId();

  const [caseData, setCaseData] = useState<Case | null>(null);
  const [artifacts, setArtifacts] = useState<EvidenceArtifact[]>([]);
  const [records, setRecords] = useState<EvidenceRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<EvidenceRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState(params.get("q") ?? "");
  const [sourceType, setSourceType] = useState<SourceType | "">(
    (params.get("source_type") as SourceType) || "",
  );
  const [evidenceId, setEvidenceId] = useState(params.get("evidence_id") ?? "");
  const [validity, setValidity] = useState<"" | "true" | "false">(
    (params.get("is_valid") as "" | "true" | "false") || "",
  );
  const [warningsOnly, setWarningsOnly] = useState(params.get("has_warnings") === "true");

  const loadCaseMeta = useCallback(async (id: string) => {
    setActiveCaseId(id);
    const [caseResp, evidence] = await Promise.all([
      getCase(id),
      listCaseEvidence(id),
    ]);
    setCaseData(caseResp);
    setArtifacts(evidence.items);
  }, []);

  const loadRecords = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCaseRecords(id, {
        q: q || undefined,
        source_type: sourceType || undefined,
        evidence_id: evidenceId || undefined,
        is_valid: validity === "" ? "" : validity === "true",
        has_warnings: warningsOnly ? true : "",
        limit: 200,
        offset: 0,
      });
      setRecords(data.items);
      setTotal(data.total);
      if (selected) {
        const still = data.items.find((r) => r.record_id === selected.record_id);
        setSelected(still ?? data.items[0] ?? null);
      } else if (data.items.length > 0) {
        setSelected(data.items[0]);
      } else {
        setSelected(null);
      }
    } catch (err) {
      setRecords([]);
      setTotal(0);
      setSelected(null);
      setError(err instanceof Error ? err.message : "Failed to load records");
    } finally {
      setLoading(false);
    }
  }, [q, sourceType, evidenceId, validity, warningsOnly, selected]);

  useEffect(() => {
    if (!caseId) return;
    void loadCaseMeta(caseId).catch((err: Error) =>
      setError(err.message ?? "Failed to load case"),
    );
  }, [caseId, loadCaseMeta]);

  useEffect(() => {
    if (!caseId) return;
    void loadRecords(caseId);
    // intentionally exclude selected from deps to avoid loops
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, q, sourceType, evidenceId, validity, warningsOnly]);

  function applyFilters(event: React.FormEvent) {
    event.preventDefault();
    const next = new URLSearchParams();
    if (caseId) next.set("case", caseId);
    if (q.trim()) next.set("q", q.trim());
    if (sourceType) next.set("source_type", sourceType);
    if (evidenceId) next.set("evidence_id", evidenceId);
    if (validity) next.set("is_valid", validity);
    if (warningsOnly) next.set("has_warnings", "true");
    setParams(next);
  }

  const provenanceRows = useMemo(
    () => selected?.field_provenance ?? [],
    [selected],
  );

  return (
    <>
      <div className="page-header">
        <h1>Evidence Explorer</h1>
        <p>
          Search and filter normalized evidence records. Drill into raw values,
          field provenance, and parse warnings for any selected row.
        </p>
      </div>

      <CaseWorkspaceBanner
        caseId={caseId || null}
        title={caseData?.title}
        status={caseData?.status}
        evidenceCount={caseData?.evidence_count}
      />

      {error && <div className="alert alert-error">{error}</div>}

      {caseId && (
        <>
          <section className="panel">
            <h2>Filters</h2>
            <form onSubmit={applyFilters}>
              <div className="form-grid">
                <div className="form-field">
                  <label htmlFor="q">Search</label>
                  <input
                    id="q"
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Signal ID, state, speed…"
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="sourceType">Source type</label>
                  <select
                    id="sourceType"
                    value={sourceType}
                    onChange={(e) => setSourceType(e.target.value as SourceType | "")}
                  >
                    <option value="">All</option>
                    {SOURCE_TYPES.map((st) => (
                      <option key={st} value={st}>
                        {st.replace("_", " ")}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="evidenceId">Artifact</label>
                  <select
                    id="evidenceId"
                    value={evidenceId}
                    onChange={(e) => setEvidenceId(e.target.value)}
                  >
                    <option value="">All artifacts</option>
                    {artifacts.map((a) => (
                      <option key={a.evidence_id} value={a.evidence_id}>
                        {a.filename}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="validity">Validity</label>
                  <select
                    id="validity"
                    value={validity}
                    onChange={(e) =>
                      setValidity(e.target.value as "" | "true" | "false")
                    }
                  >
                    <option value="">All</option>
                    <option value="true">Valid only</option>
                    <option value="false">Invalid only</option>
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="warnings">Warnings</label>
                  <label className="checkbox-inline">
                    <input
                      id="warnings"
                      type="checkbox"
                      checked={warningsOnly}
                      onChange={(e) => setWarningsOnly(e.target.checked)}
                    />
                    Has parse warnings
                  </label>
                </div>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading ? "Searching…" : "Apply filters"}
                </button>
              </div>
            </form>
          </section>

          <div className="explorer-layout">
            <section className="panel explorer-list">
              <h2>
                Records ({total}
                {records.length < total ? `, showing ${records.length}` : ""})
              </h2>
              {loading ? (
                <div className="empty-state">Loading records…</div>
              ) : records.length === 0 ? (
                <div className="empty-state">
                  No records match the current filters.
                </div>
              ) : (
                <div className="record-list">
                  {records.map((record) => {
                    const active = selected?.record_id === record.record_id;
                    return (
                      <button
                        key={record.record_id}
                        type="button"
                        className={`record-row${active ? " active" : ""}`}
                        onClick={() => setSelected(record)}
                      >
                        <div className="record-row-top">
                          <span className="table-primary">
                            {recordTitle(record)}
                          </span>
                          <span
                            className={`status-pill ${record.is_valid ? "completed" : "failed"}`}
                          >
                            {record.is_valid ? "valid" : "invalid"}
                          </span>
                        </div>
                        <div className="table-muted">{recordSubtitle(record)}</div>
                      </button>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="panel explorer-detail">
              <h2>Record detail & provenance</h2>
              {!selected ? (
                <div className="empty-state">Select a record to inspect provenance.</div>
              ) : (
                <div className="detail-stack">
                  <div className="meta-grid">
                    <div>
                      <span className="meta-label">Row</span>
                      <span>{recordTitle(selected)}</span>
                    </div>
                    <div>
                      <span className="meta-label">Record ID</span>
                      <span className="mono">{selected.record_id}</span>
                    </div>
                    <div>
                      <span className="meta-label">Source file</span>
                      <span>
                        {selected.filename} · row {selected.record_index}
                      </span>
                    </div>
                    <div>
                      <span className="meta-label">SHA-256</span>
                      <span className="mono">
                        {selected.sha256?.slice(0, 16) ?? "—"}…
                      </span>
                    </div>
                    <div>
                      <span className="meta-label">Created</span>
                      <span>{formatDateTime(selected.created_at)}</span>
                    </div>
                  </div>

                  {selected.parse_warnings && selected.parse_warnings.length > 0 && (
                    <div className="alert alert-error">
                      Warnings: {selected.parse_warnings.join("; ")}
                    </div>
                  )}

                  <div className="split-json">
                    <div>
                      <h3>Normalized</h3>
                      <pre>{formatJson(selected.normalized_data)}</pre>
                    </div>
                    <div>
                      <h3>Raw</h3>
                      <pre>{formatJson(selected.raw_data)}</pre>
                    </div>
                  </div>

                  <div>
                    <h3>Field provenance</h3>
                    {provenanceRows.length === 0 ? (
                      <div className="empty-state">No field provenance stored.</div>
                    ) : (
                      <div className="table-wrap">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Field</th>
                              <th>Raw</th>
                              <th>Normalized</th>
                              <th>Transform</th>
                            </tr>
                          </thead>
                          <tbody>
                            {provenanceRows.map((row, idx) => (
                              <tr key={`${row.field}-${idx}`}>
                                <td>{row.field}</td>
                                <td className="mono">{formatJson(row.raw)}</td>
                                <td className="mono">{formatJson(row.normalized)}</td>
                                <td>{row.transform ?? "—"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </>
  );
}
