import type { BundleDocument, DocumentType, OrderBundle, VerificationCheck, VerificationIssue, VerificationSummary } from '../types/api';
import { formatValue } from './format';

export type StatusTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral';
export type CheckFilter = 'All' | 'Customer Side' | 'Vendor Side' | 'Amounts' | 'References';
export type IssueSeverity = 'Critical' | 'Warning' | 'Info';

export interface RequiredDocumentSlot {
  type: DocumentType;
  label: string;
}

export interface DocumentSlot extends RequiredDocumentSlot {
  document: BundleDocument | null;
  state: 'uploaded' | 'missing';
}

export interface DocumentGroup extends RequiredDocumentSlot {
  documents: BundleDocument[];
  state: 'uploaded' | 'missing';
}

export interface DerivedIssue {
  id: string;
  title: string;
  message: string;
  whyItMatters: string;
  expectedLabel: string;
  foundLabel: string;
  differenceLabel: string;
  recommendedAction: string;
  relatedDocuments: string[];
  severity: IssueSeverity;
  status: 'Open';
  documentType: string | null;
  documentId: string | null;
  category: string;
  source: 'summary' | 'check' | 'document';
  actionLabel: string;
  actionPath: string;
}

export const REQUIRED_DOCUMENT_SLOTS: RequiredDocumentSlot[] = [
  { type: 'CUSTOMER_PO', label: 'Customer PO' },
  { type: 'COMPANY_INVOICE', label: 'Company Invoice' },
  { type: 'COMPANY_DC', label: 'Company Delivery Challan / DC' },
  { type: 'COMPANY_PO', label: 'Company PO to Vendor' },
  { type: 'VENDOR_INVOICE', label: 'Vendor Invoice' },
];

const STATUS_LABELS: Record<string, string> = {
  OK: 'Verification Passed',
  PASS: 'Verification Passed',
  PARTIAL_PASS: 'Partially Matched',
  REVIEW_REQUIRED: 'Needs Review',
  MISMATCH: 'Mismatch',
  MISSING_DOCUMENTS: 'Missing Documents',
  BLOCKED: 'Needs Review',
  UPLOADED: 'Uploaded',
  EXTRACTING: 'Extracting',
  PENDING_REVIEW: 'Needs Review',
  EXTRACTION_FAILED: 'Extraction Failed',
  VERIFIED: 'Verification Passed',
  REJECTED: 'Needs Review',
  PENDING: 'Extraction Pending',
  EXTRACTED: 'Extracted',
  FAILED: 'Extraction Failed',
  MANUAL_ENTRY: 'Needs Review',
};

const DOCUMENT_LABELS: Record<string, string> = Object.fromEntries(
  REQUIRED_DOCUMENT_SLOTS.map((slot) => [slot.type, slot.label]),
);

Object.assign(DOCUMENT_LABELS, {
  CUSTOMER_INVOICE: 'Customer Invoice',
  DELIVERY_CHALLAN: 'Delivery Challan',
  VENDOR_PO: 'Vendor PO',
  VENDOR_BILL: 'Vendor Bill',
});

const CANONICAL_DOCUMENT_TYPES: Record<string, DocumentType> = {
  CUSTOMER_PO: 'CUSTOMER_PO',
  COMPANY_INVOICE: 'COMPANY_INVOICE',
  CUSTOMER_INVOICE: 'COMPANY_INVOICE',
  COMPANY_DC: 'COMPANY_DC',
  DELIVERY_CHALLAN: 'COMPANY_DC',
  COMPANY_PO: 'COMPANY_PO',
  VENDOR_PO: 'COMPANY_PO',
  VENDOR_INVOICE: 'VENDOR_INVOICE',
  VENDOR_BILL: 'VENDOR_INVOICE',
};

export function statusLabel(status: string | null | undefined): string {
  if (!status) return 'Extraction Pending';
  return STATUS_LABELS[status] ?? titleCase(status);
}

export function statusTone(status: string | null | undefined): StatusTone {
  if (!status) return 'neutral';
  if (['OK', 'PASS', 'VERIFIED', 'EXTRACTED'].includes(status)) return 'success';
  if (['REVIEW_REQUIRED', 'PARTIAL_PASS', 'PENDING_REVIEW', 'PENDING', 'UPLOADED', 'EXTRACTING', 'MANUAL_ENTRY'].includes(status)) return 'warning';
  if (['MISMATCH', 'MISSING_DOCUMENTS', 'BLOCKED', 'EXTRACTION_FAILED', 'FAILED', 'REJECTED'].includes(status)) return 'danger';
  return 'neutral';
}

export function documentLabel(type: string | null | undefined): string {
  if (!type) return '-';
  return DOCUMENT_LABELS[type] ?? titleCase(type);
}

export function canonicalDocumentType(type: string | null | undefined): DocumentType | null {
  return type ? CANONICAL_DOCUMENT_TYPES[type] ?? null : null;
}

export function documentRecordTypeLabel(type: string, groupType: DocumentType): string {
  const aliasSuffix = type === groupType ? '' : ' alias';
  return `${documentLabel(type)} (${type}${aliasSuffix})`;
}

export function identifierLabel(value: string | null | undefined): string {
  if (!value) return '-';
  return titleCase(value);
}

export function bundleStatus(bundle: OrderBundle): string {
  return String(bundle.computed_status ?? bundle.status ?? 'REVIEW_REQUIRED');
}

export function documentUploadStatus(document: BundleDocument | null | undefined): 'Uploaded' | 'Missing' {
  return document ? 'Uploaded' : 'Missing';
}

export function documentExtractionStatus(document: BundleDocument | null | undefined): string {
  if (!document) return 'Pending';
  const diagnostics = document.metadata?.diagnostics ?? {};
  if (diagnostics.extraction_activity_status === 'queued' || diagnostics.queued === true) {
    return 'Waiting in extraction queue';
  }
  if (document.status === 'EXTRACTION_FAILED' || document.metadata?.status === 'FAILED') return 'Failed';
  if (['EXTRACTED', 'MANUAL_ENTRY'].includes(document.metadata?.status ?? '')) return 'Extracted';
  if (document.status === 'EXTRACTING') return 'Extracting';
  return 'Pending';
}

export function documentReviewStatus(document: BundleDocument | null | undefined): 'Clear' | 'Needs Review' {
  if (!document) return 'Needs Review';
  if (document.status === 'VERIFIED') return 'Clear';
  return 'Needs Review';
}

export function bundleQueueMetrics(bundles: OrderBundle[]) {
  return {
    total: bundles.length,
    needsReview: bundles.filter((bundle) => bundleStatus(bundle) === 'REVIEW_REQUIRED').length,
    verified: bundles.filter((bundle) => ['OK', 'PASS', 'VERIFIED'].includes(bundleStatus(bundle))).length,
    mismatches: bundles.filter((bundle) => bundleStatus(bundle) === 'MISMATCH').length,
    missingDocuments: bundles.filter((bundle) => bundleStatus(bundle) === 'MISSING_DOCUMENTS').length,
  };
}

export function buildDocumentSlots(documents: BundleDocument[]): DocumentSlot[] {
  return REQUIRED_DOCUMENT_SLOTS.map((slot) => {
    const document = documents.find((entry) => canonicalDocumentType(entry.document_type) === slot.type) ?? null;
    return { ...slot, document, state: document ? 'uploaded' : 'missing' };
  });
}

export function buildDocumentGroups(documents: BundleDocument[]): DocumentGroup[] {
  return REQUIRED_DOCUMENT_SLOTS.map((slot) => {
    const matchingDocuments = documents.filter((entry) => canonicalDocumentType(entry.document_type) === slot.type);
    const rawTypes = new Set(matchingDocuments.map((document) => document.document_type));
    const label = slot.type === 'COMPANY_INVOICE'
      && rawTypes.has('COMPANY_INVOICE')
      && rawTypes.has('CUSTOMER_INVOICE')
      ? 'Company Invoice / Customer Invoice'
      : slot.label;
    return {
      ...slot,
      label,
      documents: matchingDocuments,
      state: matchingDocuments.length ? 'uploaded' : 'missing',
    };
  });
}

export function extractionProgress(documents: BundleDocument[]) {
  const total = documents.length;
  const extracted = documents.filter((document) => ['EXTRACTED', 'MANUAL_ENTRY'].includes(document.metadata?.status ?? '')).length;
  const failed = documents.filter((document) => document.status === 'EXTRACTION_FAILED' || document.metadata?.status === 'FAILED').length;
  const pending = Math.max(0, total - extracted - failed);
  const confidences = documents
    .flatMap((document) => Object.values(document.metadata?.field_confidences ?? {}))
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));

  return {
    total,
    extracted,
    pending,
    failed,
    confidenceAverage: confidences.length ? Math.round((confidences.reduce((sum, value) => sum + value, 0) / confidences.length) * 100) : null,
  };
}

export function verificationMetrics(summary: VerificationSummary | null | undefined) {
  const checks = summary?.checks ?? [];
  return {
    total: checks.length,
    passed: checks.filter((check) => check.result === 'PASS').length,
    mismatches: checks.filter((check) => check.result === 'MISMATCH').length,
    missingData: checks.filter((check) => check.result === 'MISSING_DOCUMENTS' || /missing/i.test(check.message)).length,
    notChecked: checks.filter((check) => ['REVIEW_REQUIRED', 'PARTIAL_PASS', 'BLOCKED'].includes(check.result)).length,
  };
}

export function checkCategory(check: VerificationCheck): CheckFilter {
  const text = `${check.check_id} ${check.check_name} ${check.message}`.toLowerCase();
  if (/amount|total|billing|coverage|tax|net/.test(text)) return 'Amounts';
  if (isCustomerDocument(check.left_document_type) || isCustomerDocument(check.right_document_type)) return 'Customer Side';
  if (isVendorDocument(check.left_document_type) || isVendorDocument(check.right_document_type)) return 'Vendor Side';
  return 'References';
}

export function checkDisplayName(check: VerificationCheck): string {
  if (check.check_id === 'VENDOR_BILLING_COVERAGE' && check.result !== 'PASS') {
    return 'Vendor invoice total is lower than Vendor PO total';
  }
  const name = plainCheckName(check.check_name || identifierLabel(check.check_id));
  if (check.result === 'PASS') return name;

  const corrected = name
    .replace(/\bmatches between\b/i, 'differs between')
    .replace(/\bmatches\b/i, 'does not match')
    .replace(/\bmatch\b/i, 'mismatch');

  return corrected === name ? `Mismatch: ${name}` : corrected;
}

export function checkDisplayMessage(check: VerificationCheck): string {
  if (check.check_id === 'VENDOR_BILLING_COVERAGE' && check.result !== 'PASS') {
    return `${documentLabel(check.right_document_type)} total ${formatValue(check.right_value, check.check_id)} does not fully cover ${documentLabel(check.left_document_type)} total ${formatValue(check.left_value, check.check_id)}.`;
  }
  const message = check.message || checkDisplayName(check);
  if (check.result === 'PASS') return message;
  return message
    .replace(/\bmatches between\b/i, 'differs between')
    .replace(/\bmatches\b/i, 'does not match');
}

export function checkImpactLabel(check: VerificationCheck): string {
  if (check.result === 'PASS') return '-';
  if (check.severity === 'BLOCKER') return 'High';
  if (check.severity === 'WARNING') return 'Medium';
  return 'Low';
}

export function checkExplanation(check: VerificationCheck): string {
  if (check.result === 'PASS') return checkDisplayMessage(check);
  const left = formatValue(check.left_value, check.check_id);
  const right = formatValue(check.right_value, check.check_id);
  if (left !== '-' || right !== '-') {
    return `${documentLabel(check.left_document_type)} shows ${left}; ${documentLabel(check.right_document_type)} shows ${right}.`;
  }
  return checkDisplayMessage(check);
}

export function isAutomatedTestBundle(bundle: OrderBundle): boolean {
  return /^(OA-ACCEPT-|UPLOAD-SMOKE-|AUDIT-|OA-HIGHLIGHT-|OA-REVIEW-|BUILD1-DEMO-|(?:OA-PANIMALAR|PANIMALAR-ORDER)-\d{10,}$)/i.test(bundle.bundle_number);
}

export function deriveIssues(summary: VerificationSummary | null | undefined, documents: BundleDocument[], bundleId = ''): DerivedIssue[] {
  const issues: DerivedIssue[] = [];
  const slots = buildDocumentSlots(documents);

  const summaryIssues = summary?.issues ?? [];

  for (const issue of summaryIssues) {
    const documentType = typeof issue.document_type === 'string' ? issue.document_type : null;
    const documentId = typeof issue.document_id === 'string' ? issue.document_id : null;
    const code = String(issue.code ?? 'Verification Issue');
    const issueMessage = String(issue.message ?? 'Review the backend verification issue.');
    const relatedDocuments = relatedDocumentsForIssue(code, issueMessage, documentType);
    issues.push({
      id: `summary-${code}-${issues.length}`,
      title: summaryIssueTitle(code, issueMessage),
      message: friendlyIssueMessage(issueMessage, issue),
      whyItMatters: issueWhyItMatters(code, issueMessage),
      expectedLabel: summaryIssueValue(issue, 'expected') ?? valueFromIssue(issue, ['vendor_po_total', 'customer_po_total', 'expected_value']) ?? '-',
      foundLabel: summaryIssueValue(issue, 'found') ?? valueFromIssue(issue, ['vendor_invoice_total', 'invoice_total', 'found_value']) ?? '-',
      differenceLabel: valueFromIssue(issue, ['difference', 'delta']) ?? '-',
      recommendedAction: recommendedActionForIssue(code, issueMessage, documentType),
      relatedDocuments,
      severity: severityFromIssue(issue),
      status: 'Open',
      documentType,
      documentId,
      category: documentType ? documentLabel(documentType) : 'Review Results',
      source: 'summary',
      actionLabel: documentId ? `Review ${documentLabel(documentType)}` : documentType ? `Upload ${documentLabel(documentType)}` : 'View Review Results',
      actionPath: documentId ? `/bundles/${bundleId}/extraction/${documentId}` : `/bundles/${bundleId}/documents`,
    });
  }

  if (summaryIssues.length === 0) {
    for (const check of summary?.checks ?? []) {
      if (check.result === 'PASS') continue;
      const relatedDocuments = Array.from(new Set([
        documentLabel(check.left_document_type),
        documentLabel(check.right_document_type),
      ].filter((value) => value !== '-')));
      issues.push({
        id: `check-${check.check_id}`,
        title: checkDisplayName(check),
        message: checkDisplayMessage(check),
        whyItMatters: check.severity === 'BLOCKER' ? 'This can block a confident document match.' : 'This should be reviewed before relying on the report.',
        expectedLabel: `${formatValue(check.left_value, check.check_id)} from ${documentLabel(check.left_document_type)}`,
        foundLabel: `${formatValue(check.right_value, check.check_id)} from ${documentLabel(check.right_document_type)}`,
        differenceLabel: checkDifferenceLabel(check),
        recommendedAction: 'Review the related document evidence and correct extracted values if needed.',
        relatedDocuments,
        severity: check.result === 'MISMATCH' || check.severity === 'BLOCKER' ? 'Critical' : 'Warning',
        status: 'Open',
        documentType: check.left_document_type ?? check.right_document_type,
        documentId: check.left_document_id ?? check.right_document_id,
        category: checkCategory(check),
        source: 'check',
        actionLabel: 'View Review Results',
        actionPath: `/bundles/${bundleId}/verification?check=${encodeURIComponent(check.check_id)}`,
      });
    }
  }

  for (const slot of slots) {
    if (slot.document) continue;
    issues.push({
      id: `missing-${slot.type}`,
      title: `Missing Document: ${slot.label}`,
      message: `${slot.label} has not been uploaded.`,
      whyItMatters: 'Required documents must be present before the bundle can be reviewed confidently.',
      expectedLabel: slot.label,
      foundLabel: 'Not uploaded',
      differenceLabel: '-',
      recommendedAction: `Upload ${slot.label}.`,
      relatedDocuments: [slot.label],
      severity: 'Critical',
      status: 'Open',
      documentType: slot.type,
      documentId: null,
      category: 'Missing Document',
      source: 'document',
      actionLabel: `Upload missing document ${slot.label}`,
      actionPath: `/bundles/${bundleId}/documents`,
    });
  }

  return issues;
}

export function outcomeSummary(summary: VerificationSummary | null | undefined, documents: BundleDocument[], bundleId: string) {
  const issues = deriveIssues(summary, documents, bundleId);
  const primaryIssue = issues[0] ?? null;
  const status = summary?.bundle_status ?? 'REVIEW_REQUIRED';
  if (primaryIssue) {
    return {
      status,
      title: `${statusLabel(status)}: ${primaryIssue.title}`,
      reason: primaryIssue.message,
      nextAction: primaryIssue.recommendedAction,
      actionLabel: primaryIssue.actionLabel,
      actionPath: primaryIssue.actionPath,
    };
  }
  return {
    status,
    title: `${statusLabel(status)}: No open issues found`,
    reason: 'The current review checks do not show mismatches or missing required documents.',
    nextAction: 'Download the Excel report or continue reviewing extracted values.',
    actionLabel: 'Download Report',
    actionPath: `/bundles/${bundleId}/exports`,
  };
}

export function topIssues(summary: VerificationSummary | null | undefined, documents: BundleDocument[], limit = 4): DerivedIssue[] {
  return deriveIssues(summary, documents).slice(0, limit);
}

export function firstNextAction(summary: VerificationSummary | null | undefined, documents: BundleDocument[], bundleId: string): DerivedIssue | null {
  return deriveIssues(summary, documents, bundleId)[0] ?? null;
}

export function formatCount(value: number | null | undefined): string {
  return typeof value === 'number' ? new Intl.NumberFormat('en-IN').format(value) : '-';
}

function severityFromIssue(issue: VerificationIssue): IssueSeverity {
  const text = `${String(issue.code ?? '')} ${String(issue.message ?? '')}`.toLowerCase();
  if (/missing|mismatch|blocking|absent|unmatched/.test(text)) return 'Critical';
  if (/review|warning|partial/.test(text)) return 'Warning';
  return 'Info';
}

function plainCheckName(value: string): string {
  return value
    .replace(/\bverification\b/gi, 'review')
    .replace(/\bVendor invoice total covers Vendor PO total\b/i, 'Vendor invoice total compared with Vendor PO total')
    .replace(/\bAmount comparison\b/i, 'Amount comparison')
    .replace(/\bCustomer name match\b/i, 'Customer name comparison')
    .replace(/\bVendor name match\b/i, 'Vendor name comparison')
    .trim();
}

function checkDifferenceLabel(check: VerificationCheck): string {
  if (typeof check.left_value === 'number' && typeof check.right_value === 'number') {
    return formatValue(Math.abs(check.left_value - check.right_value), check.check_id);
  }
  return '-';
}

function summaryIssueTitle(code: string, message: string): string {
  const text = `${code} ${message}`.toLowerCase();
  if (/vendor invoice total.*does not fully cover|partial_billing/.test(text)) return 'Vendor invoice total is lower than Vendor PO total';
  if (/missing/.test(text)) return identifierLabel(code).replace(/\bMissing Documents\b/i, 'Missing Document');
  if (/mismatch|differ|does not match/.test(text)) return identifierLabel(code).replace(/\bMatches\b/i, 'Mismatch');
  return identifierLabel(code).replace(/\bReview Required\b/i, 'Needs Review');
}

function friendlyIssueMessage(message: string, issue?: VerificationIssue): string {
  const record = issue as unknown as Record<string, unknown> | undefined;
  if (record?.vendor_po_total && record.vendor_invoice_total) {
    return `Vendor Invoice Total ${formatValue(record.vendor_invoice_total, 'vendor_invoice_total')} does not fully cover Vendor PO Total ${formatValue(record.vendor_po_total, 'vendor_po_total')}.`;
  }
  return message.replace(/\bverification\b/gi, 'review');
}

function issueWhyItMatters(code: string, message: string): string {
  const text = `${code} ${message}`.toLowerCase();
  if (/vendor invoice total|partial_billing/.test(text)) {
    return 'The vendor-side cost may represent partial billing or a missing vendor invoice.';
  }
  if (/missing/.test(text)) return 'The bundle cannot be checked completely until the required document is uploaded.';
  return 'The report will include this review item until the source values are confirmed.';
}

function relatedDocumentsForIssue(code: string, message: string, documentType: string | null): string[] {
  const text = `${code} ${message}`.toLowerCase();
  if (/vendor invoice total|partial_billing/.test(text)) {
    return ['Company PO to Vendor', 'Vendor Invoice'];
  }
  return documentType ? [documentLabel(documentType)] : [];
}

function recommendedActionForIssue(code: string, message: string, documentType: string | null): string {
  const text = `${code} ${message}`.toLowerCase();
  if (/vendor invoice total|partial_billing/.test(text)) {
    return 'Confirm whether this is partial billing. If yes, export with review note. If not, upload the remaining vendor invoice.';
  }
  if (/missing/.test(text) && documentType) return `Upload ${documentLabel(documentType)}.`;
  return 'Review the related document evidence and correct extracted values if needed.';
}

function valueFromIssue(issue: VerificationIssue, keys: string[]): string | null {
  for (const key of keys) {
    const value = (issue as unknown as Record<string, unknown>)[key];
    if (value !== undefined && value !== null && value !== '') return formatValue(value, key);
  }
  return null;
}

function summaryIssueValue(issue: VerificationIssue, kind: 'expected' | 'found'): string | null {
  const record = issue as unknown as Record<string, unknown>;
  if (kind === 'expected') {
    return valueFromIssue(issue, ['expected', 'expected_value', 'left_value'])
      ?? (record.vendor_po_total ? `${formatValue(record.vendor_po_total, 'vendor_po_total')} Vendor PO` : null);
  }
  return valueFromIssue(issue, ['found', 'found_value', 'right_value'])
    ?? (record.vendor_invoice_total ? `${formatValue(record.vendor_invoice_total, 'vendor_invoice_total')} Vendor Invoice` : null);
}

function isCustomerDocument(type: string | null | undefined): boolean {
  return ['CUSTOMER_PO', 'CUSTOMER_INVOICE', 'COMPANY_INVOICE', 'DELIVERY_CHALLAN', 'COMPANY_DC'].includes(String(type));
}

function isVendorDocument(type: string | null | undefined): boolean {
  return ['VENDOR_PO', 'COMPANY_PO', 'VENDOR_INVOICE', 'VENDOR_BILL'].includes(String(type));
}

function titleCase(value: string): string {
  const acronyms = new Set(['api', 'dc', 'erp', 'id', 'ocr', 'pdf', 'po', 'sku', 'so']);
  return value
    .toLowerCase()
    .split('_')
    .map((part) => acronyms.has(part) ? part.toUpperCase() : part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}
