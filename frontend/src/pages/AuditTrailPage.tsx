import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CaseWorkspaceBanner, formatDateTime } from "../components/CaseWorkspaceBanner";
import { getCase, listCaseAudit } from "../services/api";
import { getActiveCaseId, setActiveCaseId } from "../services/workspace";
import type { AuditEvent, Case } from "../types/case";

export function AuditTrailPage() {
  const [params] = useSearchParams();
  const caseId = params.get("case") || getActiveCaseId();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      setActiveCaseId(id);
      const [caseResp, audit] = await Promise.all([
        getCase(id),
        listCaseAudit(id),
      ]);
      setCaseData(caseResp);
      setEvents(audit.events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit trail");
      setEvents([]);
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
        <h1>Audit Trail</h1>
        <p>
          State-changing actions across ingestion, timeline rebuild, investigation,
          and graph construction — who did what and when.
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
        <h2>Audit events ({events.length})</h2>
        {loading ? (
          <div className="empty-state">Loading audit trail…</div>
        ) : !caseId ? null : events.length === 0 ? (
          <div className="empty-state">No audit events recorded yet.</div>
        ) : (
          <div className="finding-list">
            {events.map((item) => (
              <article key={item.audit_id} className="finding-card">
                <div className="finding-card-header">
                  <h3>{item.action}</h3>
                  <span className="severity-pill medium">{item.actor}</span>
                </div>
                <div className="table-muted">
                  {item.entity_type} · <code>{item.entity_id}</code> ·{" "}
                  {formatDateTime(item.created_at)}
                </div>
                {item.payload && Object.keys(item.payload).length > 0 && (
                  <pre className="audit-payload">
                    {JSON.stringify(item.payload, null, 2)}
                  </pre>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
