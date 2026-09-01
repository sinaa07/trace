import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CaseWorkspaceBanner } from "../components/CaseWorkspaceBanner";
import { getCase, getCaseEvidenceGaps } from "../services/api";
import { getActiveCaseId, setActiveCaseId } from "../services/workspace";
import type { Case } from "../types/case";

export function EvidenceGapsPage() {
  const [params] = useSearchParams();
  const caseId = params.get("case") || getActiveCaseId();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [missingSources, setMissingSources] = useState<string[]>([]);
  const [missingInputs, setMissingInputs] = useState<string[]>([]);
  const [needsReview, setNeedsReview] = useState<
    Array<Record<string, unknown>>
  >([]);
  const [weatherAvailable, setWeatherAvailable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      setActiveCaseId(id);
      const [caseResp, gaps] = await Promise.all([
        getCase(id),
        getCaseEvidenceGaps(id),
      ]);
      setCaseData(caseResp);
      setMissingSources(gaps.missing_source_types);
      setMissingInputs(gaps.missing_domain_inputs);
      setNeedsReview(gaps.needs_review_or_failed);
      setWeatherAvailable(gaps.external_weather_available);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load gaps");
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
        <h1>Evidence Gaps</h1>
        <p>
          Known missing source types, domain inputs, and artifacts needing review
          — surfaced for investigator follow-up.
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
        <h2>Gap analysis</h2>
        {loading ? (
          <div className="empty-state">Loading evidence gaps…</div>
        ) : !caseId ? null : (
          <div className="gap-grid">
            <article className="finding-card">
              <h3>Missing source types ({missingSources.length})</h3>
              {missingSources.length === 0 ? (
                <p className="table-muted">All expected source types present.</p>
              ) : (
                <ul>
                  {missingSources.map((s) => (
                    <li key={s}>
                      <code>{s}</code>
                    </li>
                  ))}
                </ul>
              )}
            </article>

            <article className="finding-card">
              <h3>Missing domain inputs ({missingInputs.length})</h3>
              {missingInputs.length === 0 ? (
                <p className="table-muted">No missing preprocessor inputs.</p>
              ) : (
                <ul>
                  {missingInputs.map((s) => (
                    <li key={s}>
                      <code>{s}</code>
                    </li>
                  ))}
                </ul>
              )}
            </article>

            <article className="finding-card">
              <h3>External weather MCP</h3>
              <p>
                {weatherAvailable
                  ? "Case has coordinates — environment agent can fetch Open-Meteo data."
                  : "No coordinates on case — set location lat/lon or upload GPS evidence."}
              </p>
            </article>

            <article className="finding-card">
              <h3>Needs review / failed ({needsReview.length})</h3>
              {needsReview.length === 0 ? (
                <p className="table-muted">No failed or review-flagged artifacts.</p>
              ) : (
                <ul>
                  {needsReview.map((item, i) => (
                    <li key={String(item.evidence_id ?? i)}>
                      <code>{String(item.filename ?? item.evidence_id)}</code>
                      {item.error ? ` — ${String(item.error)}` : ""}
                    </li>
                  ))}
                </ul>
              )}
            </article>
          </div>
        )}
      </section>
    </>
  );
}
