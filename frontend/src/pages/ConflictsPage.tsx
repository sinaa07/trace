import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CaseWorkspaceBanner, formatDateTime } from "../components/CaseWorkspaceBanner";
import { getCase, listCaseConflicts } from "../services/api";
import {
  getActiveCaseId,
  setActiveCaseId,
} from "../services/workspace";
import type { Case, EvidenceConflict } from "../types/case";

export function ConflictsPage() {
  const [params] = useSearchParams();
  const caseId = params.get("case") || getActiveCaseId();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [conflicts, setConflicts] = useState<EvidenceConflict[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      setActiveCaseId(id);
      const [caseResp, data] = await Promise.all([
        getCase(id),
        listCaseConflicts(id),
      ]);
      setCaseData(caseResp);
      setConflicts(data.conflicts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load conflicts");
      setConflicts([]);
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
        <h1>Conflicts</h1>
        <p>
          Cross-source contradictions aligned within the temporal tolerance
          window — signal state mismatches and maintenance-vs-sensor disagreements.
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
        <h2>Evidence conflicts ({conflicts.length})</h2>
        {loading ? (
          <div className="empty-state">Loading conflicts…</div>
        ) : !caseId ? null : conflicts.length === 0 ? (
          <div className="empty-state">No conflicts detected for this case.</div>
        ) : (
          <div className="finding-list">
            {conflicts.map((item) => (
              <article key={item.conflict_id} className="finding-card">
                <div className="finding-card-header">
                  <h3>{item.title}</h3>
                  <span className={`severity-pill ${item.severity}`}>
                    {item.severity}
                  </span>
                </div>
                <p>{item.explanation}</p>
                <div className="table-muted">
                  Type <code>{item.conflict_type}</code> · {formatDateTime(item.created_at)} ·{" "}
                  {item.event_ids.length} event(s) · {item.evidence_refs.length} evidence
                  ref(s)
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
