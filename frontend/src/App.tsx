import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom';
import { AuditTrailPage } from './pages/AuditTrailPage';
import { BundleOverviewPage } from './pages/BundleOverviewPage';
import { BundlesPage } from './pages/BundlesPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { ExportsPage } from './pages/ExportsPage';
import { ExtractionReviewPage } from './pages/ExtractionReviewPage';
import { HealthPage } from './pages/HealthPage';
import { IssuesPage } from './pages/IssuesPage';
import { VerificationPage } from './pages/VerificationPage';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/bundles" replace />} />
        <Route path="/bundles" element={<BundlesPage />} />
        <Route path="/bundles/:bundleId" element={<BundleOverviewRedirect />} />
        <Route path="/bundles/:bundleId/overview" element={<BundleOverviewPage />} />
        <Route path="/bundles/:bundleId/documents" element={<DocumentsPage />} />
        <Route path="/bundles/:bundleId/extraction" element={<ExtractionReviewPage />} />
        <Route path="/bundles/:bundleId/extraction/:documentId" element={<ExtractionReviewPage />} />
        <Route path="/bundles/:bundleId/verification" element={<VerificationPage />} />
        <Route path="/bundles/:bundleId/issues" element={<IssuesPage />} />
        <Route path="/bundles/:bundleId/audit" element={<AuditTrailPage />} />
        <Route path="/bundles/:bundleId/exports" element={<ExportsPage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="*" element={<Navigate to="/bundles" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

function BundleOverviewRedirect() {
  const { bundleId } = useParams<{ bundleId: string }>();
  return <Navigate to={bundleId ? `/bundles/${bundleId}/overview` : '/bundles'} replace />;
}
