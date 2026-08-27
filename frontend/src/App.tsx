import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { AnomaliesPage } from "./pages/AnomaliesPage";
import { CaseIngestionPage } from "./pages/CaseIngestionPage";
import { CaseOverviewPage } from "./pages/CaseOverviewPage";
import { CasesPage } from "./pages/CasesPage";
import { ConflictsPage } from "./pages/ConflictsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EvidenceExplorerPage } from "./pages/EvidenceExplorerPage";
import { FindingsPage } from "./pages/FindingsPage";
import { HypothesesPage } from "./pages/HypothesesPage";
import { TimelinePage } from "./pages/TimelinePage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="ingestion" element={<CaseIngestionPage />} />
          <Route path="cases" element={<CasesPage />} />
          <Route path="overview" element={<CaseOverviewPage />} />
          <Route path="evidence" element={<EvidenceExplorerPage />} />
          <Route path="timeline" element={<TimelinePage />} />
          <Route path="anomalies" element={<AnomaliesPage />} />
          <Route path="conflicts" element={<ConflictsPage />} />
          <Route path="findings" element={<FindingsPage />} />
          <Route path="hypotheses" element={<HypothesesPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
