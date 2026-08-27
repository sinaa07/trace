import { Link } from "react-router-dom";

interface CaseWorkspaceBannerProps {
  caseId: string | null;
  title?: string | null;
  status?: string | null;
  evidenceCount?: number | null;
}

export function CaseWorkspaceBanner({
  caseId,
  title,
  status,
  evidenceCount,
}: CaseWorkspaceBannerProps) {
  if (!caseId) {
    return (
      <div className="alert alert-info">
        No active case selected.{" "}
        <Link to="/cases">Open Cases</Link> to choose a workspace, or{" "}
        <Link to="/ingestion">create a new case</Link>.
      </div>
    );
  }

  return (
    <div className="case-status-bar">
      <span>
        Active case:
        <strong>{title ?? caseId.slice(0, 8)}</strong>
      </span>
      {status && (
        <span>
          Status:<strong>{status}</strong>
        </span>
      )}
      {evidenceCount != null && (
        <span>
          Evidence:<strong>{evidenceCount}</strong>
        </span>
      )}
      <span>
        ID:<strong>{caseId.slice(0, 8)}…</strong>
      </span>
      <span className="case-status-actions">
        <Link to={`/overview?case=${caseId}`}>Overview</Link>
        <Link to={`/ingestion?case=${caseId}`}>Ingestion</Link>
        <Link to="/cases">Switch case</Link>
      </span>
    </div>
  );
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return value;
  }
}

export function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
