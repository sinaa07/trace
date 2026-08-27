import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CaseWorkspaceBanner, formatDateTime } from "../components/CaseWorkspaceBanner";
import {
  getCase,
  listCaseFindings,
  runInvestigation,
} from "../services/api";
import {
  getActiveCaseId,
  setActiveCaseId,
} from "../services/workspace";
import { getInvestigatorName } from "../services/investigator";
import type { Case, HypothesisFinding } from "../types/case";

export function FindingsPage() {
  const [params] = useSearchParams();
  const caseId = params.get("case") || getActiveCaseId();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [findings, setFindings] = useState<HypothesisFinding[]>([]);
  const [metaSummary, setMetaSummary] = useState<string | null>(null);
  const [provider, setProvider] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      setActiveCaseId(id);
      const [caseResp, data] = await Promise.all([
        getCase(id),
        listCaseFindings(id),
      ]);
      setCaseData(caseResp);
      setFindings(data.findings);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load findings");
      setFindings([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (caseId) void load(caseId);
  }, [caseId, load]);

  const onInvestigate = async () => {
    if (!caseId) return;
    setRunning(true);
    setError(null);
    try {
      const result = await runInvestigation(
        caseId,
        getInvestigatorName() || "investigator",
      );
      setFindings(result.findings);
      setMetaSummary(result.meta_summary);
      setProvider(result.provider);
      const refreshed = await getCase(caseId);
      setCaseData(refreshed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Investigation failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>Findings</h1>
        <p>
          Structured HypothesisFinding outputs from domain agents — support,
          contradict, missing evidence, and evidence-weighted rank scores.
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
        <div className="panel-toolbar">
          <h2>Agent findings ({findings.length})</h2>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!caseId || running}
            onClick={() => void onInvestigate()}
          >
            {running ? "Running investigation…" : "Run investigation"}
          </button>
        </div>
        {provider && (
          <p className="table-muted">
            Provider: <code>{provider}</code>
            {metaSummary ? ` · ${metaSummary.split("\n")[0]}` : ""}
          </p>
        )}
        {loading ? (
          <div className="empty-state">Loading findings…</div>
        ) : !caseId ? null : findings.length === 0 ? (
          <div className="empty-state">
            No findings yet. Run investigation to generate domain hypotheses.
          </div>
        ) : (
          <div className="finding-list">
            {findings.map((item) => (
              <article key={item.finding_id} className="finding-card">
                <div className="finding-card-header">
                  <h3>{item.hypothesis}</h3>
                  <span className="severity-pill medium">
                    {item.domain}
                    {item.rank_score != null
                      ? ` · ${item.rank_score.toFixed(3)}`
                      : ""}
                  </span>
                </div>
                <p>{item.reasoning_summary || item.reasoning}</p>
                <div className="table-muted">
                  Agent <code>{item.agent_id}</code> · confidence{" "}
                  {item.confidence.toFixed(2)} ·{" "}
                  {item.supporting_evidence.length} support ·{" "}
                  {item.contradicting_evidence.length} contradict ·{" "}
                  {item.missing_evidence.length} missing ·{" "}
                  {formatDateTime(item.created_at)}
                </div>
                {item.uncertainty && (
                  <p className="table-muted">Uncertainty: {item.uncertainty}</p>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
