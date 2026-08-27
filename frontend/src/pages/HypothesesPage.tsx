import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CaseWorkspaceBanner, formatDateTime } from "../components/CaseWorkspaceBanner";
import { getCase, listCaseHypotheses } from "../services/api";
import {
  getActiveCaseId,
  setActiveCaseId,
} from "../services/workspace";
import type { Case, RankedHypothesis } from "../types/case";

export function HypothesesPage() {
  const [params] = useSearchParams();
  const caseId = params.get("case") || getActiveCaseId();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [hypotheses, setHypotheses] = useState<RankedHypothesis[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      setActiveCaseId(id);
      const [caseResp, data] = await Promise.all([
        getCase(id),
        listCaseHypotheses(id),
      ]);
      setCaseData(caseResp);
      setHypotheses(data.hypotheses);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load hypotheses");
      setHypotheses([]);
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
        <h1>Hypotheses</h1>
        <p>
          Evidence-weighted ranking across domain findings. Agent confidence is
          not treated as a Bayesian probability.
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
        <h2>Ranked hypotheses ({hypotheses.length})</h2>
        {loading ? (
          <div className="empty-state">Loading hypotheses…</div>
        ) : !caseId ? null : hypotheses.length === 0 ? (
          <div className="empty-state">
            No ranked hypotheses yet. Run investigation from the Findings page.
          </div>
        ) : (
          <div className="finding-list">
            {hypotheses.map((item, index) => (
              <article key={item.finding.finding_id} className="finding-card">
                <div className="finding-card-header">
                  <h3>
                    #{index + 1} · {item.finding.hypothesis}
                  </h3>
                  <span className="severity-pill high">
                    score {item.weighted_score.toFixed(3)}
                  </span>
                </div>
                <p>{item.finding.reasoning_summary || item.finding.reasoning}</p>
                <div className="dim-grid">
                  <span>support {item.dimensions.evidence_support.toFixed(2)}</span>
                  <span>
                    temporal {item.dimensions.temporal_consistency.toFixed(2)}
                  </span>
                  <span>
                    source {item.dimensions.source_reliability.toFixed(2)}
                  </span>
                  <span>
                    complete {item.dimensions.evidence_completeness.toFixed(2)}
                  </span>
                  <span>
                    contradict −{item.dimensions.contradiction_penalty.toFixed(2)}
                  </span>
                  <span>causal {item.dimensions.causal_support.toFixed(2)}</span>
                </div>
                <div className="table-muted">
                  {item.finding.domain} · agent{" "}
                  <code>{item.finding.agent_id}</code> ·{" "}
                  {formatDateTime(item.finding.created_at)}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
