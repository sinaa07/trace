import { Link } from "react-router-dom";
import { getInvestigatorName } from "../../services/investigator";

export function Navbar() {
  const investigator = getInvestigatorName();

  return (
    <header className="navbar">
      <div className="navbar-brand-group">
        <Link to="/" className="navbar-brand-row">
          <span className="navbar-brand">
            <span className="navbar-brand-mark">TR</span>
            TRACE
          </span>
        </Link>
        <span className="navbar-subtitle">
          Railway Accident Digital Forensics
        </span>
      </div>
      <div className="navbar-meta">
        {investigator ? `Investigator: ${investigator}` : "Set identity on Case Ingestion"}
      </div>
    </header>
  );
}
