import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { useState } from 'react';
import { getBundle } from '../api/bundles';
import { listBundleDocuments } from '../api/documents';
import { exportVerificationReport } from '../api/export';
import { getVerificationSummary } from '../api/verification';
import { ErrorState } from '../components/common/ErrorState';
import { KpiCard } from '../components/common/KpiCard';
import { LoadingState } from '../components/common/LoadingState';
import { StatusBadge } from '../components/common/StatusBadge';
import { AppShell } from '../components/layout/AppShell';
import { WorkflowTabs } from '../components/layout/WorkflowTabs';
import { useAsyncResource } from '../hooks/useAsyncResource';
import {
  buildDocumentGroups,
  canonicalDocumentType,
  documentLabel,
  extractionProgress,
  statusLabel,
  statusTone,
  type DerivedIssue,
  deriveIssues,
  REQUIRED_DOCUMENT_SLOTS,
} from '../lib/build1';
import { formatValue } from '../lib/format';
import type { BundleDocument, OrderBundle, VerificationSummary } from '../types/api';

export function ExportsPage() {
  const { bundleId } = useParams<{ bundleId: string }>();
  if (!bundleId) return <Navigate to="/bundles" replace />;
  return <ExportsContent bundleId={bundleId} />;
}

function ExportsContent({ bundleId }: { bundleId: string }) {
  const bundle   = useAsyncResource<OrderBundle>(() => getBundle(bundleId), [bundleId]);
  const documents = useAsyncResource<BundleDocument[]>(() => listBundleDocuments(bundleId), [bundleId]);
  const summary  = useAsyncResource<VerificationSummary>(() => getVerificationSummary(bundleId), [bundleId]);
  const [isExporting, setIsExporting]       = useState(false);
  const [exportError, setExportError]       = useState<string | null>(null);
  const [exportMessage, setExportMessage]   = useState<string | null>(null);
  const navigate = useNavigate();

  const docs    = documents.data ?? [];
  const sum     = summary.data ?? null;
  const bund    = bundle.data ?? null;
  const issues  = deriveIssues(sum, docs, bundleId);
  const billing = vendorBillingTotals(sum);
  const progress = extractionProgress(docs);

  const bundleStatus   = bund?.computed_status ?? bund?.status ?? null;
  const customerStatus = bund?.computed_customer_status ?? bund?.customer_delivery_status ?? null;
  const vendorStatus   = bund?.computed_vendor_status ?? bund?.vendor_procurement_status ?? null;

  // Business doc groups in Build 1 order
  const BUILD1_ORDER: Array<{ canonical: string; label: string }> = [
    { canonical: 'CUSTOMER_PO',    label: 'Customer PO' },
    { canonical: 'COMPANY_PO',     label: 'Vendor PO' },
    { canonical: 'VENDOR_INVOICE', label: 'Vendor Bills' },
    { canonical: 'COMPANY_DC',     label: 'Company DC' },
    { canonical: 'COMPANY_INVOICE',label: 'Company Invoice' },
  ];

  async function download() {
    setIsExporting(true);
    setExportError(null);
    setExportMessage(null);
    try {
      await exportVerificationReport(bundleId);
      setExportMessage('Download started.');
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsExporting(false);
    }
  }

  const isLoading = documents.isLoading || summary.isLoading || bundle.isLoading;
  const canonical_groups = new Map<string, BundleDocument[]>();
  for (const doc of docs) {
    const ct = canonicalDocumentType(doc.document_type) ?? doc.document_type;
    const list = canonical_groups.get(ct) ?? [];
    list.push(doc);
    canonical_groups.set(ct, list);
  }

  return (
    <AppShell
      bundleId={bundleId}
      title="Export"
      subtitle={bund?.bundle_number ?? bundleId}
      breadcrumbs={[
        { label: 'Orders', href: '/bundles' },
        { label: bund?.bundle_number ?? bundleId, href: `/bundles/${bundleId}/overview` },
        { label: 'Export' },
      ]}
    >
      <WorkflowTabs bundleId={bundleId} />
      <ErrorState message={bundle.error ?? documents.error ?? summary.error ?? exportError} />
      {isLoading ? <LoadingState label="Loading export data…" /> : null}

      {/* ── Header ──────────────────────────────────────────────────── */}
      {bund && (
        <section className="panel export-header">
          <div className="export-header__meta">
            <div>
              <span className="export-header__label">Order</span>
              <span className="export-header__value">{bund.bundle_number}</span>
            </div>
            {bund.customer_name && (
              <div>
                <span className="export-header__label">Customer</span>
                <span className="export-header__value">{bund.customer_name}</span>
              </div>
            )}
            {bund.customer_po_no && (
              <div>
                <span className="export-header__label">Customer PO</span>
                <span className="export-header__value">{bund.customer_po_no}</span>
              </div>
            )}
          </div>
          <div className="export-header__statuses">
            {bundleStatus   && <StatusBadge status={bundleStatus}   label={`Bundle: ${statusLabel(bundleStatus)}`} />}
            {customerStatus && <StatusBadge status={customerStatus} label={`Customer: ${statusLabel(customerStatus)}`} />}
            {vendorStatus   && <StatusBadge status={vendorStatus}   label={`Vendor: ${statusLabel(vendorStatus)}`} />}
          </div>
        </section>
      )}

      {/* ── KPI Cards ───────────────────────────────────────────────── */}
      <div className="kpi-grid export-kpi-grid">
        <KpiCard label="Uploaded Records"     value={progress.total}       tone="info" />
        <KpiCard label="Extracted"            value={progress.extracted}   tone={progress.extracted === progress.total ? 'success' : 'warning'} />
        <KpiCard label="Pending Extraction"   value={progress.pending}     tone={progress.pending ? 'warning' : 'success'} />
        <KpiCard label="Review Items"         value={issues.length}        tone={issues.length ? 'warning' : 'success'} />
        <KpiCard label="Critical Mismatches"  value={(sum?.checks ?? []).filter(c => c.result === 'MISMATCH').length} tone={(sum?.checks ?? []).some(c => c.result === 'MISMATCH') ? 'danger' : 'success'} />
        <KpiCard label="Business Doc Groups"  value={canonical_groups.size} tone="info" />
      </div>

      {/* ── Main Finding ─────────────────────────────────────────────── */}
      <section className={`panel export-finding export-finding--${issues.length ? (sum?.checks?.some(c => c.result === 'MISMATCH') ? 'danger' : 'warning') : 'success'}`}>
        <div className="export-finding__header">
          <h2>Main Finding</h2>
          <StatusBadge status={bundleStatus ?? 'REVIEW_REQUIRED'} />
        </div>
        <p className="export-finding__text">
          {mainFindingText(sum, billing, issues)}
        </p>
        {sum?.recommendation && (
          <p className="export-finding__recommendation">
            <strong>Recommendation:</strong> {sum.recommendation}
          </p>
        )}
      </section>

      {/* ── Financial Summary ────────────────────────────────────────── */}
      {billing.hasData && (
        <section className="panel export-financial">
          <h2>Financial Summary</h2>
          <div className="export-financial__grid">
            <FinancialRow label="Vendor PO Total"   value={billing.vendorPoTotal}      field="vendor_po_total" />
            <FinancialRow label="Vendor Bills Total" value={billing.vendorInvoiceTotal} field="vendor_invoice_total" />
            <FinancialRow
              label="Difference (PO − Bills)"
              value={billing.difference !== null ? billing.difference : null}
              field="difference"
              highlight={billing.difference !== null && Math.abs(billing.difference) > 2}
            />
            <div className="export-financial__result">
              <span className="export-financial__result-label">Result</span>
              <StatusBadge status={billing.billingResult} />
            </div>
          </div>
        </section>
      )}

      {/* ── Document Coverage ────────────────────────────────────────── */}
      <section className="panel">
        <h2>Document Coverage</h2>
        <p className="export-coverage__subtitle">Build 1 business flow order</p>
        <table className="export-coverage-table">
          <thead>
            <tr>
              <th>Business Group</th>
              <th>Uploaded</th>
              <th>Extracted</th>
              <th>Pending</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {BUILD1_ORDER.map(({ canonical, label }) => {
              const groupDocs = canonical_groups.get(canonical as any) ?? [];
              const uploaded  = groupDocs.length;
              const extracted = groupDocs.filter(d => ['EXTRACTED', 'MANUAL_ENTRY'].includes(d.metadata?.status ?? '')).length;
              const pending   = uploaded - extracted;
              const groupStatus = uploaded === 0 ? 'MISSING'
                : extracted === 0 ? 'PENDING'
                : extracted === uploaded ? 'EXTRACTED'
                : 'PARTIAL';
              const tone = groupStatus === 'MISSING' ? 'danger'
                : groupStatus === 'EXTRACTED' ? 'success'
                : 'warning';
              return (
                <tr key={canonical} className={`export-coverage-table__row export-coverage-table__row--${tone}`}>
                  <td className="export-coverage-table__group">{label}</td>
                  <td>{uploaded || '—'}</td>
                  <td>{uploaded ? extracted : '—'}</td>
                  <td>{uploaded ? pending : '—'}</td>
                  <td><StatusBadge status={groupStatus} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {/* ── Export Actions ───────────────────────────────────────────── */}
      <section className={`panel export-actions ${issues.length ? 'export-actions--warning' : ''}`}>
        <div className="export-actions__info">
          <h2>{issues.length ? 'Export with open review items' : 'Ready to download'}</h2>
          <p>{issues.length
            ? `The Excel report will include ${issues.length} open review item${issues.length > 1 ? 's' : ''} and current extracted values.`
            : 'All current checks are clear for this Build 1 report.'}</p>
          {exportMessage && <p className="export-actions__success" role="status">{exportMessage}</p>}
        </div>
        <div className="export-actions__buttons">
          <button
            className="button button--primary button--large"
            type="button"
            disabled={isExporting}
            onClick={download}
          >
            {isExporting ? 'Downloading…' : 'Download Excel Report'}
          </button>
          <button
            className="button button--ghost"
            type="button"
            onClick={() => navigate(`/bundles/${bundleId}/verification`)}
          >
            View Verification
          </button>
          <button
            className="button button--ghost"
            type="button"
            onClick={() => navigate(`/bundles/${bundleId}/documents`)}
          >
            View Documents
          </button>
        </div>
      </section>
    </AppShell>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function FinancialRow({
  label, value, field, highlight = false,
}: { label: string; value: number | null; field: string; highlight?: boolean }) {
  return (
    <div className={`export-financial__row ${highlight ? 'export-financial__row--highlight' : ''}`}>
      <span className="export-financial__row-label">{label}</span>
      <span className="export-financial__row-value">
        {value !== null ? formatValue(value, field) : '—'}
      </span>
    </div>
  );
}

// ── Domain logic ──────────────────────────────────────────────────────────────

interface BillingTotals {
  vendorPoTotal: number | null;
  vendorInvoiceTotal: number | null;
  difference: number | null;
  billingResult: string;
  hasData: boolean;
}

function vendorBillingTotals(summary: VerificationSummary | null | undefined): BillingTotals {
  const issue = (summary?.issues ?? []).find(
    (item) => typeof item.code === 'string' && /billing/i.test(item.code)
  ) as Record<string, unknown> | undefined;
  const check = summary?.checks.find((item) => item.check_id === 'VENDOR_BILLING_COVERAGE');

  const vendorPoTotal     = numVal(issue?.vendor_po_total) ?? numVal(check?.left_value);
  const vendorInvoiceTotal = numVal(issue?.vendor_invoice_total) ?? numVal(check?.right_value);
  const difference        = numVal(issue?.difference)
    ?? (vendorPoTotal !== null && vendorInvoiceTotal !== null
      ? vendorPoTotal - vendorInvoiceTotal : null);

  const billingResult = check?.result ?? (
    difference === null ? 'REVIEW_REQUIRED'
    : Math.abs(difference) <= 2 ? 'PASS' : 'REVIEW_REQUIRED'
  );

  return {
    vendorPoTotal,
    vendorInvoiceTotal,
    difference,
    billingResult,
    hasData: vendorPoTotal !== null || vendorInvoiceTotal !== null,
  };
}

function numVal(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function mainFindingText(
  summary: VerificationSummary | null | undefined,
  billing: BillingTotals,
  issues: DerivedIssue[],
): string {
  if (!summary) return 'Loading verification data…';
  if (issues.length === 0) {
    return 'All verification checks passed. The order bundle references and totals are consistent.';
  }
  const first = issues[0];
  if (billing.hasData && billing.vendorPoTotal !== null && billing.vendorInvoiceTotal !== null
      && billing.difference !== null) {
    const absDiff = Math.abs(billing.difference);
    const direction = billing.difference < 0 ? 'above' : 'below';
    return (
      `Vendor bills (${formatValue(billing.vendorInvoiceTotal, 'vendor_invoice_total')}) ` +
      `were matched to Vendor PO (${formatValue(billing.vendorPoTotal, 'vendor_po_total')}), ` +
      `but the billing total is ${formatValue(absDiff, 'difference')} ${direction} the PO value. ` +
      `Review with procurement/finance before closure.`
    );
  }
  return first.message || first.title;
}
