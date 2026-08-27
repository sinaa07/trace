import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CaseWorkspaceBanner, formatDateTime } from "../components/CaseWorkspaceBanner";
import {
  getCase,
  listCaseAnomalies,
  listCaseConflicts,
  listCaseEvidence,
  getCaseTimeline,
} from "../services/api";
import {
  getActiveCaseId,
  setActiveCaseId,
} from "../services/workspace";
import type { Case } from "../types/case";

export function CaseOverviewPage() {
  const [params] = useSearchParams();
  const caseId = params.get("case") || getActiveCaseId();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [stats, setStats] = useState({
    evidence: 0,
    events: 0,
    anomalies: 0,
    conflicts: 0,
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      setActiveCaseId(id);
      const [caseResp, evidence, timeline, anomalies, conflicts] =
        await Promise.all([
          getCase(id),
          listCaseEvidence(id),
          getCaseTimeline(id),
          listCaseAnomalies(id),
          listCaseConflicts(id),
        ]);
      setCaseData(caseResp);
      setStats({
        evidence: evidence.total,
        events: timeline.event_count,
        anomalies: anomalies.anomaly_count,
        conflicts: conflicts.conflict_count,
      });
    } catch (err) {
      setCaseData(null);
      setError(err instanceof Error ? err.message : "Failed to load case overview");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (caseId) {
      void load(caseId);
    }
  }, [caseId, load]);

  return (
    <>
      <div className="page-header">
        <h1>Case Overview</h1>
        <p>
          Snapshot of the active investigation: evidence inventory, timeline
          events, rule anomalies, and cross-source conflicts.
        </p>
      </div>

      <CaseWorkspaceBanner
        caseId={caseId || null}
        title={caseData?.title}
        status={caseData?.status}
        evidenceCount={caseData?.evidence_count}
      />

      {error && <div className="alert alert-error">{error}</div>}
      {loading && <div className="empty-state">Loading overview…</div>}

      {caseData && !loading && (
        <>
          <section className="panel">
            <h2>{caseData.title}</h2>
            <div className="meta-grid">
              <div>
                <span className="meta-label">Incident time</span>
                <span>{formatDateTime(caseData.incident_time)}</span>
              </div>
              <div>
                <span className="meta-label">Location</span>
                <span>
                  {caseData.location
                    ? [caseData.location.track, caseData.location.km]
                        .filter(Boolean)
                        .join(" · ") || "—"
                    : "—"}
                </span>
              </div>
              <div>
                <span className="meta-label">Created by</span>
                <span>{caseData.created_by ?? "—"}</span>
              </div>
              <div>
                <span className="meta-label">Updated</span>
                <span>{formatDateTime(caseData.updated_at)}</span>
              </div>
            </div>
            {caseData.metadata?.description ? (
              <p className="overview-description">
                {String(caseData.metadata.description)}
              </p>
            ) : null}
          </section>

          <div className="stat-grid">
            <Link to={`/evidence?case=${caseData.case_id}`} className="stat-card">
              <span className="stat-value">{stats.evidence}</span>
              <span className="stat-label">Evidence artifacts</span>
            </Link>
            <Link to={`/timeline?case=${caseData.case_id}`} className="stat-card">
              <span className="stat-value">{stats.events}</span>
              <span className="stat-label">Timeline events</span>
            </Link>
            <Link to={`/anomalies?case=${caseData.case_id}`} className="stat-card">
              <span className="stat-value">{stats.anomalies}</span>
              <span className="stat-label">Anomalies</span>
            </Link>
            <Link to={`/conflicts?case=${caseData.case_id}`} className="stat-card">
              <span className="stat-value">{stats.conflicts}</span>
              <span className="stat-label">Conflicts</span>
            </Link>
          </div>
        </>
      )}
    </>
  );
}
