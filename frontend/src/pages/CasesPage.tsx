import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CaseWorkspaceBanner, formatDateTime } from "../components/CaseWorkspaceBanner";
import { listCases } from "../services/api";
import {
  getActiveCaseId,
  setActiveCaseId,
} from "../services/workspace";
import type { Case } from "../types/case";

export function CasesPage() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<Case[]>([]);
  const [total, setTotal] = useState(0);
  const [activeId, setActiveId] = useState(getActiveCaseId());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCases();
      setCases(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cases");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function openCase(caseItem: Case) {
    setActiveCaseId(caseItem.case_id);
    setActiveId(caseItem.case_id);
    navigate(`/overview?case=${caseItem.case_id}`);
  }

  return (
    <>
      <div className="page-header">
        <h1>Cases</h1>
        <p>
          Browse investigation cases and select one as the active workspace for
          Evidence Explorer, Timeline, Anomalies, and Conflicts.
        </p>
      </div>

      <CaseWorkspaceBanner caseId={activeId || null} />

      {error && <div className="alert alert-error">{error}</div>}

      <section className="panel">
        <div className="panel-toolbar">
          <h2>All cases ({total})</h2>
          <div className="form-actions" style={{ marginTop: 0 }}>
            <button type="button" className="btn btn-secondary" onClick={() => void refresh()}>
              Refresh
            </button>
            <Link to="/ingestion" className="btn btn-primary">
              New Case
            </Link>
          </div>
        </div>

        {loading ? (
          <div className="empty-state">Loading cases…</div>
        ) : cases.length === 0 ? (
          <div className="empty-state">
            No cases yet. <Link to="/ingestion">Create the first case</Link>.
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Evidence</th>
                  <th>Incident</th>
                  <th>Created</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {cases.map((item) => {
                  const isActive = item.case_id === activeId;
                  return (
                    <tr key={item.case_id} className={isActive ? "row-active" : undefined}>
                      <td>
                        <div className="table-primary">{item.title}</div>
                        <div className="table-muted">{item.case_id.slice(0, 8)}…</div>
                      </td>
                      <td>
                        <span className={`status-pill ${item.status}`}>{item.status}</span>
                      </td>
                      <td>{item.evidence_count}</td>
                      <td>{formatDateTime(item.incident_time)}</td>
                      <td>{formatDateTime(item.created_at)}</td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => openCase(item)}
                        >
                          {isActive ? "Open" : "Select"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
