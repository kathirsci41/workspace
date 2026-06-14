import { Navigate, useParams } from 'react-router-dom';
import { useState } from 'react';
import { getBundle } from '../api/bundles';
import { listBundleDocuments } from '../api/documents';
import { exportVerificationReport } from '../api/export';
import { getVerificationSummary } from '../api/verification';
import { ExportReadinessPanel } from '../components/exports/ExportReadinessPanel';
import { DataTable } from '../components/common/DataTable';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { AppShell } from '../components/layout/AppShell';
import { WorkflowTabs } from '../components/layout/WorkflowTabs';
import { useAsyncResource } from '../hooks/useAsyncResource';
import { deriveIssues, documentLabel } from '../lib/build1';
import { fieldLabel, formatValue } from '../lib/format';
import type { BundleDocument, OrderBundle, VerificationSummary } from '../types/api';

export function ExportsPage() {
  const { bundleId } = useParams<{ bundleId: string }>();
  if (!bundleId) return <Navigate to="/bundles" replace />;
  return <ExportsContent bundleId={bundleId} />;
}

function ExportsContent({ bundleId }: { bundleId: string }) {
  const bundle = useAsyncResource<OrderBundle>(() => getBundle(bundleId), [bundleId]);
  const documents = useAsyncResource<BundleDocument[]>(() => listBundleDocuments(bundleId), [bundleId]);
  const summary = useAsyncResource<VerificationSummary>(() => getVerificationSummary(bundleId), [bundleId]);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const issues = deriveIssues(summary.data, documents.data ?? [], bundleId);
  const vendorBilling = vendorBillingTotals(summary.data);
  const extractedSummaryEntries = Object.entries(summary.data?.extracted_summary ?? {})
    .filter(([key]) => key !== 'vendor_total');

  async function download() {
    setIsExporting(true);
    setExportError(null);
    setExportMessage(null);
    try {
      await exportVerificationReport(bundleId);
      setExportMessage('Export download started.');
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <AppShell
      bundleId={bundleId}
      title="Exports"
      subtitle={bundle.data?.bundle_number ?? 'Final checkpoint before downloading the Excel report.'}
      breadcrumbs={[{ label: 'Bundles', href: '/bundles' }, { label: bundle.data?.bundle_number ?? bundleId, href: `/bundles/${bundleId}/overview` }, { label: 'Exports' }]}
    >
      <WorkflowTabs bundleId={bundleId} />
      <ErrorState message={bundle.error ?? documents.error ?? summary.error ?? exportError} />
      {exportMessage ? <p role="status">{exportMessage}</p> : null}
      {documents.isLoading || summary.isLoading ? <LoadingState label="Loading export readiness..." /> : null}

      <section className={`export-checkpoint ${issues.length ? 'export-checkpoint--warning' : ''}`} aria-label="Export checkpoint">
        <div>
          <h2>{issues.length ? 'Export with unresolved review items' : 'Ready to download'}</h2>
          <p>{issues.length ? 'The Excel report will include open issues and current extracted values.' : 'All current checks are clear for this Build 1 report.'}</p>
        </div>
        <button className="button button--primary button--large" type="button" disabled={isExporting} onClick={download}>{isExporting ? 'Downloading...' : 'Download Excel Report'}</button>
      </section>

      <ExportReadinessPanel documents={documents.data ?? []} summary={summary.data} />

      <section className="panel">
        <h2>Report Contents Preview</h2>
        <DataTable label="Report contents preview" className="report-contents-table">
          <thead>
            <tr>
              <th>Section</th>
              <th>Included data</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Bundle metadata</td>
              <td>{bundle.data?.bundle_number ?? bundleId}</td>
            </tr>
            <tr>
              <td>Documents</td>
              <td>{(documents.data ?? []).map((document) => `${documentLabel(document.document_type)}: ${document.filename}`).join(', ') || '-'}</td>
            </tr>
            <tr>
              <td>Extracted summary</td>
              <td>
                <dl className="summary-key-values">
                  {extractedSummaryEntries.map(([key, value]) => (
                    <div key={key}>
                      <dt>{fieldLabel(key)}</dt>
                      <dd>{formatValue(value, key)}</dd>
                    </div>
                  ))}
                  {extractedSummaryEntries.length === 0 ? <div><dd>-</dd></div> : null}
                </dl>
              </td>
            </tr>
            <tr>
              <td>Vendor billing comparison</td>
              <td>
                <dl className="summary-key-values summary-key-values--billing">
                  <div>
                    <dt>Vendor PO Total</dt>
                    <dd>{formatValue(vendorBilling.vendorPoTotal, 'vendor_po_total')}</dd>
                  </div>
                  <div>
                    <dt>Vendor Invoice Total</dt>
                    <dd>{formatValue(vendorBilling.vendorInvoiceTotal, 'vendor_invoice_total')}</dd>
                  </div>
                  <div>
                    <dt>Difference</dt>
                    <dd>{formatValue(vendorBilling.difference, 'difference')}</dd>
                  </div>
                </dl>
              </td>
            </tr>
            <tr>
              <td>Review checks</td>
              <td>{summary.data?.checks.length ?? 0} checks</td>
            </tr>
            <tr>
              <td>Open issues</td>
              <td>{issues.length} open issues</td>
            </tr>
          </tbody>
        </DataTable>
      </section>

    </AppShell>
  );
}

function vendorBillingTotals(summary: VerificationSummary | null | undefined) {
  const issue = (summary?.issues ?? []).find((item) => (
    typeof item.code === 'string' && /vendor.*partial.*billing|vendor.*billing/i.test(item.code)
  )) as Record<string, unknown> | undefined;
  const check = summary?.checks.find((item) => item.check_id === 'VENDOR_BILLING_COVERAGE');
  const vendorPoTotal = numberValue(issue?.vendor_po_total) ?? numberValue(check?.left_value);
  const vendorInvoiceTotal = numberValue(issue?.vendor_invoice_total) ?? numberValue(check?.right_value);
  const difference = numberValue(issue?.difference)
    ?? (vendorPoTotal !== null && vendorInvoiceTotal !== null ? Math.abs(vendorPoTotal - vendorInvoiceTotal) : null);
  return { vendorPoTotal, vendorInvoiceTotal, difference };
}

function numberValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
