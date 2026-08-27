import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CaseWorkspaceBanner, formatDateTime } from "../components/CaseWorkspaceBanner";
import { getCase, listCaseAnomalies } from "../services/api";
import {
  getActiveCaseId,
  setActiveCaseId,
} from "../services/workspace";
import type { Anomaly, Case } from "../types/case";

export function AnomaliesPage() {
  const [params] = useSearchParams();
  const caseId = params.get("case") || getActiveCaseId();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      setActiveCaseId(id);
      const [caseResp, data] = await Promise.all([
        getCase(id),
        listCaseAnomalies(id),
      ]);
      setCaseData(caseResp);
      setAnomalies(data.anomalies);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load anomalies");
      setAnomalies([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (caseId) void load(caseId);
  }, [caseId, load]);

  return (
    <>
      <div className="page-header">
        <h1>Anomalies</h1>
        <p>
          Rule-based railway anomalies detected after temporal reconstruction —
          impossible sequences, threshold breaches, and invalid signal transitions.
        </p>
      </div>

      <CaseWorkspaceBanner
        caseId={caseId || null}
        title={caseData?.title}
        status={caseData?.status}
        evidenceCount={caseData?.evidence_count}
      />

      {error && <div className="alert alert-error">{error}</div>}

      <section className="panel">
        <h2>Detected anomalies ({anomalies.length})</h2>
        {loading ? (
          <div className="empty-state">Loading anomalies…</div>
        ) : !caseId ? null : anomalies.length === 0 ? (
          <div className="empty-state">No anomalies detected for this case.</div>
        ) : (
          <div className="finding-list">
            {anomalies.map((item) => (
              <article key={item.anomaly_id} className="finding-card">
                <div className="finding-card-header">
                  <h3>{item.title}</h3>
                  <span className={`severity-pill ${item.severity}`}>
                    {item.severity}
                  </span>
                </div>
                <p>{item.explanation}</p>
                <div className="table-muted">
                  Rule <code>{item.rule_id}</code> · {formatDateTime(item.created_at)} ·{" "}
                  {item.affected_event_ids.length} event(s) ·{" "}
                  {item.evidence_refs.length} evidence ref(s)
                </div>
                {item.details && (
                  <pre className="json-block">{JSON.stringify(item.details, null, 2)}</pre>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
