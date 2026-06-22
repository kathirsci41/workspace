import { fieldLabel, formatValue } from '../../lib/format';
import type { BundleDocument } from '../../types/api';
import { StatusBadge } from '../common/StatusBadge';
import {
  criticalFieldsForDocType,
  groupFieldsByDocType,
  isNeedsReviewSource,
  sourceLabel,
} from './extractedFieldsUtils';
import type { RawFieldMeta } from './extractedFieldsUtils';

export function ExtractedFieldsPanel({
  document,
  onEdit,
  onFieldClick,
}: {
  document: BundleDocument;
  onEdit: (field: string) => void;
  onFieldClick?: (field: string) => void;
}) {
  const metadata = document.metadata;
  const fields = dedupeFields(Object.entries(metadata?.extracted_data ?? {}).filter(([key]) => !key.startsWith('raw_')));
  const rawFieldMeta = ((metadata?.diagnostics?.field_metadata ?? {}) as Record<string, RawFieldMeta>);
  const groupedFields = groupFieldsByDocType(fields, document.document_type, rawFieldMeta);

  return (
    <section className="fields-panel" aria-label="Extracted fields">
      <div className="section-header">
        <div>
          <h2>Extracted Fields</h2>
          <p>{document.filename}</p>
        </div>
        <StatusBadge status={metadata?.status ?? 'PENDING'} />
      </div>
      {fields.length === 0 ? (
        <p className="muted">No extracted fields yet.</p>
      ) : (
        <div className="field-groups">
          {groupedFields.map((group) => (
            <section className={`field-group${group.variant ? ` field-group--${group.variant}` : ''}`} key={group.label} aria-label={group.label}>
              <h3>{group.label}</h3>
              <div className="field-table" role="table" aria-label={`${group.label} fields`}>
                {group.fields.map(([field, value]) => {
                  const fieldSource = rawFieldMeta[field]?.source;
                  const label = sourceLabel(fieldSource);
                  return (
                    <div className="field-table__row" role="row" key={field}>
                      <span
                        role="cell"
                        className={`field-name${onFieldClick ? ' field-name--clickable' : ''}`}
                        onClick={onFieldClick ? () => onFieldClick(field) : undefined}
                        tabIndex={onFieldClick ? 0 : undefined}
                        onKeyDown={onFieldClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onFieldClick(field); } : undefined}
                        aria-label={onFieldClick ? `Jump to ${fieldLabel(field)} in PDF` : undefined}
                      >
                        {fieldLabel(field)}
                        {isVerificationField(field, document.document_type) ? <em>Used in Review Results</em> : null}
                        {label ? <em className={`source-badge source-badge--${isNeedsReviewSource(fieldSource) ? 'warning' : 'info'}`}>{label}</em> : null}
                      </span>
                      <span role="cell" className="value-cell">{formatValue(value, field)}</span>
                      <span role="cell">{confidenceLabel(metadata?.field_confidences?.[field])}</span>
                      <span role="cell">
                        <button
                          className="button button--ghost field-correction-button"
                          type="button"
                          aria-label={`Correct ${fieldLabel(field)}`}
                          onClick={() => onEdit(field)}
                        >
                          Edit
                        </button>
                      </span>
                      {metadata?.field_evidence?.[field] ? (
                        <small className="field-evidence">
                          <b>Evidence</b>
                          <span>{metadata.field_evidence[field]}</span>
                        </small>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
      {metadata?.last_error ? <p role="alert">{metadata.last_error}</p> : null}
    </section>
  );
}

function confidenceLabel(value: number | null | undefined): string {
  if (typeof value !== 'number') return '-';
  return `${Math.round(value * 100)}%`;
}

type FieldEntry = [string, unknown];

const SEMANTIC_FIELD_ALIASES: Record<string, string> = {
  invoice_no: 'invoice_number',
  vendor_invoice_no: 'invoice_number',
  so_no: 'so_number',
  dc_no: 'dc_number',
  vendor_po_no: 'po_number',
  vendor_invoice_date: 'invoice_date',
  invoice_total: 'total_amount',
  subtotal_amount: 'taxable_amount',
  customer_ref_no: 'po_reference',
  gstin: 'vendor_gstin',
};

function dedupeFields(fields: FieldEntry[]): FieldEntry[] {
  const selected = new Map<string, { entry: FieldEntry; index: number }>();
  fields.forEach((entry, index) => {
    const [field, value] = entry;
    const semanticField = SEMANTIC_FIELD_ALIASES[field] ?? field;
    const key = `${semanticField}:${JSON.stringify(value)}`;
    const current = selected.get(key);
    if (!current || fieldPreference(field) < fieldPreference(current.entry[0])) {
      selected.set(key, { entry, index });
    }
  });
  return [...selected.values()]
    .sort((left, right) => left.index - right.index)
    .map(({ entry }) => entry);
}

function fieldPreference(field: string): number {
  return [
    'vendor_invoice_no',
    'vendor_invoice_date',
    'invoice_total',
    'taxable_amount',
    'po_reference',
    'vendor_gstin',
  ].includes(field) ? 0 : 1;
}

function isVerificationField(field: string, docType: string): boolean {
  const criticalKeys = criticalFieldsForDocType(docType);
  return criticalKeys.size > 0 ? criticalKeys.has(field) : isFallbackCriticalField(field);
}

function isFallbackCriticalField(field: string): boolean {
  return [
    'customer_po_no', 'customer_po_date', 'invoice_no', 'invoice_number',
    'invoice_date', 'vendor_invoice_no', 'vendor_invoice_date', 'vendor_po_no',
    'po_number', 'po_date', 'dc_no', 'dc_number', 'dc_date', 'so_no',
    'so_number', 'po_reference',
  ].includes(field);
}
