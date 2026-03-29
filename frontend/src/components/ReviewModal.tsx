import { useState, useEffect, useRef } from 'react';
import {
  X, Check, Ban, Loader2, PenLine,
  Zap, Camera, AlertTriangle, ChevronDown, ChevronUp, Hash, Plus,
} from 'lucide-react';
import {
  useMetadata,
  useVerifyMetadata,
  useRejectMetadata,
  useFieldTemplate,
  useSaveCorrections,
} from '@/hooks/useExtraction';
import { useUpdatePO } from '@/hooks/usePurchaseOrders';
import { getPreviewUrl } from '@/api/documents';
import PDFViewer from '@/components/PDFViewer';
import clsx from 'clsx';

interface Props {
  documentId: string;
  onClose: () => void;
  onVerified: () => void;
  mode?: 'review' | 'edit';
  onSaved?: () => void;
}

// Confidence thresholds for field-level colouring
const CONF_HIGH   = 0.85;
const CONF_MEDIUM = 0.60;

export default function ReviewModal({ documentId, onClose, onVerified, mode = 'review', onSaved }: Props) {
  const { data: metadata, isLoading } = useMetadata(documentId);
  const verifyMutation     = useVerifyMetadata();
  const rejectMutation     = useRejectMetadata();
  const correctionsMutation = useSaveCorrections();   // NEW Phase 8
  const updatePOMutation   = useUpdatePO();

  const isDataEmpty = !metadata?.extracted_data ||
    Object.keys(metadata.extracted_data).length === 0;
  const { data: template } = useFieldTemplate(documentId, isDataEmpty && !isLoading);

  const [formData, setFormData]           = useState<Record<string, string>>({});
  const [customFields, setCustomFields]   = useState<{ id: string; label: string; value: string }[]>([]);
  const [isManualMode, setIsManualMode]   = useState(false);
  const [errorsOpen, setErrorsOpen]       = useState(true);
  const [warningsOpen, setWarningsOpen]   = useState(false);

  // SO entry prompt — shown when PO has no SO number (verify blocked until set)
  const [soPrompt, setSoPrompt]           = useState<{ poId: string } | null>(null);
  const [soInput, setSoInput]             = useState('');
  const [soMismatchMsg, setSoMismatchMsg] = useState<string | null>(null);
  // Store editedData so we can re-verify automatically after SO is saved
  const pendingEditedData = useRef<Record<string, unknown> | null>(null);

  // Snapshot of original extracted values for diffing corrections
  const originalSnapshot = useRef<Record<string, string>>({});

  // Array fields that must never be included in formData — they can only come from extraction
  const ARRAY_FIELDS = new Set(['order_items', 'delivery_locations']);

  useEffect(() => {
    if (metadata?.extracted_data && Object.keys(metadata.extracted_data).length > 0) {
      const initial: Record<string, string> = {};
      for (const [key, value] of Object.entries(metadata.extracted_data)) {
        if (key.startsWith('_') || key.startsWith('custom_')) continue;
        if (ARRAY_FIELDS.has(key)) continue;  // Keep arrays out of formData — they must not be overwritten by string coercion
        initial[key] = value != null ? String(value) : '';
      }
      // Always include operator_notes (from existing data or empty)
      initial['operator_notes'] = (metadata.extracted_data['operator_notes'] as string) ?? '';
      setFormData(initial);
      // Load existing custom fields
      const existingCustom = Object.entries(metadata.extracted_data)
        .filter(([k]) => k.startsWith('custom_'))
        .map(([k, v]) => ({ id: crypto.randomUUID(), label: k.slice(7), value: String(v ?? '') }));
      setCustomFields(existingCustom);
      // Snapshot for correction diffing (includes custom fields)
      const snap: Record<string, string> = { ...initial };
      for (const { label, value } of existingCustom) snap[`custom_${label}`] = value;
      originalSnapshot.current = snap;
      setIsManualMode(
        metadata.model_version === 'manual' ||
        Object.values(metadata.extracted_data).every((v) => v === null || v === '')
      );
    } else if (template?.fields) {
      const initial: Record<string, string> = {};
      for (const key of Object.keys(template.fields)) {
        initial[key] = '';
      }
      initial['operator_notes'] = '';
      setFormData(initial);
      setCustomFields([]);
      originalSnapshot.current = { ...initial };
      setIsManualMode(true);
    }
  }, [metadata, template]);

  // ── Derive validation errors/warnings from extracted_data ────────
  const validationErrors: string[] = Array.isArray(
    metadata?.extracted_data?.['_validation_errors']
  )
    ? (metadata!.extracted_data!['_validation_errors'] as string[])
    : [];

  const validationWarnings: string[] = Array.isArray(
    metadata?.extracted_data?.['_validation_warnings']
  )
    ? (metadata!.extracted_data!['_validation_warnings'] as string[])
    : [];

  // ── Per-field confidence helper ───────────────────────────────────
  const fieldConf = metadata?.field_confidences ?? null;

  const getFieldConfidence = (key: string): number | null => {
    if (!fieldConf) return null;
    return fieldConf[key] ?? null;
  };

  const confColour = (conf: number | null) => {
    if (conf === null) return 'border-gray-300';
    if (conf >= CONF_HIGH)   return 'border-green-400';
    if (conf >= CONF_MEDIUM) return 'border-amber-400';
    return 'border-red-400';
  };

  const confBadgeColour = (conf: number | null) => {
    if (conf === null) return '';
    if (conf >= CONF_HIGH)   return 'text-green-600 bg-green-50';
    if (conf >= CONF_MEDIUM) return 'text-amber-600 bg-amber-50';
    return 'text-red-600 bg-red-50';
  };

  // ── Verify: diff + save corrections, then verify ──────────────────
  const handleVerify = async () => {
    // Build corrections list — fields that changed from original
    const corrections = Object.entries(formData)
      .filter(([key]) => !key.startsWith('_'))
      .filter(([key, val]) => val !== (originalSnapshot.current[key] ?? ''))
      .map(([key, val]) => ({ field: key, corrected_value: val || null }));

    // Fire-and-forget corrections (don't block on failure)
    if (corrections.length > 0) {
      correctionsMutation.mutate({ documentId, corrections });
    }

    // Build editedData for the verify call (same logic as before)
    const editedData: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(formData)) {
      if (key.startsWith('_')) continue;
      if (ARRAY_FIELDS.has(key)) continue;  // Never overwrite extracted arrays with stringified versions
      if (value === '') {
        editedData[key] = null;
      } else if (
        !isNaN(Number(value)) &&
        (key.includes('amount') || key.includes('count') ||
         key.includes('quantity') || key.includes('subtotal') ||
         key.includes('tax'))
      ) {
        editedData[key] = Number(value);
      } else if (key === 'signature_present') {
        editedData[key] = value === 'true';
      } else {
        editedData[key] = value;
      }
    }

    // Inject custom fields into editedData
    for (const { label, value } of customFields) {
      if (label.trim()) editedData[`custom_${label.trim()}`] = value;
    }

    setSoMismatchMsg(null);
    verifyMutation.mutate(
      { documentId, editedData },
      {
        onSuccess: (result) => {
          if (result.verification_pending && result.po_id) {
            // PO has no SO yet — save editedData and prompt operator
            pendingEditedData.current = editedData;
            setSoPrompt({ poId: result.po_id });
          } else if (result.so_mismatch_message) {
            // SO in document doesn't match PO SO — show inline message
            setSoMismatchMsg(result.so_mismatch_message);
          } else {
            onVerified();
          }
        },
      }
    );
  };

  // ── SO entry submit: save SO then re-verify ────────────────────────
  const handleSoSubmit = () => {
    if (!soPrompt || !soInput.trim()) return;
    updatePOMutation.mutate(
      { id: soPrompt.poId, body: { so_number: soInput.trim() } },
      {
        onSuccess: () => {
          setSoPrompt(null);
          // Re-verify with the same data now that SO is set
          if (pendingEditedData.current) {
            verifyMutation.mutate(
              { documentId, editedData: pendingEditedData.current },
              {
                onSuccess: (result) => {
                  if (result.so_mismatch_message) {
                    setSoMismatchMsg(result.so_mismatch_message);
                  } else {
                    onVerified();
                  }
                },
              }
            );
          } else {
            onVerified();
          }
        },
      }
    );
  };

  const handleSave = () => {
    const corrections = Object.entries(formData)
      .filter(([key]) => !key.startsWith('_'))
      .filter(([key, val]) => val !== (originalSnapshot.current[key] ?? ''))
      .map(([key, val]) => ({ field: key, corrected_value: val || null }));

    // Include custom field changes
    for (const { label, value } of customFields) {
      if (!label.trim()) continue;
      const key = `custom_${label.trim()}`;
      if (value !== (originalSnapshot.current[key] ?? ''))
        corrections.push({ field: key, corrected_value: value || null });
    }

    if (corrections.length === 0) {
      onClose();
      return;
    }

    correctionsMutation.mutate(
      { documentId, corrections },
      { onSuccess: () => { onSaved?.(); onClose(); } }
    );
  };

  const handleReject = () => {
    rejectMutation.mutate(documentId, { onSuccess: onClose });
  };

  const addCustomField = () =>
    setCustomFields((f) => [...f, { id: crypto.randomUUID(), label: '', value: '' }]);

  const removeCustomField = (id: string) =>
    setCustomFields((f) => f.filter((cf) => cf.id !== id));

  // ── Field ordering and labels ─────────────────────────────────────
  const FIELD_ORDER: Record<string, string[]> = {
    CUSTOMER_PO:     ['po_number', 'bsif_name', 'po_date', 'quotation_no', 'quotation_date', 'grand_total', 'delivery_details', 'terms_and_conditions'],
    COMPANY_PO:      ['po_number', 'po_date', 'mode_of_bill', 'vendor_name'],
    VENDOR_DC:       ['dc_number', 'dc_date', 'po_reference', 'vendor_name', 'items_description', 'quantity', 'vehicle_number', 'receiver_name'],
    VENDOR_INVOICE:  ['invoice_number', 'customer_order_no', 'po_reference'],
    COMPANY_DC:      ['dc_number', 'po_reference', 'sales_order_no', 'dispatch_to'],
    COMPANY_INVOICE: ['invoice_number', 'so_number', 'po_reference', 'customer_name', 'total_amount'],
  };

  const FIELD_LABELS: Record<string, string> = {
    bsif_name:             'Customer Name',
    po_date:               'PO Date',
    quotation_no:          'Quotation No',
    quotation_date:        'Quotation Date',
    grand_total:           'Grand Total',
    delivery_details:      'Delivery Details',
    terms_and_conditions:  'Terms & Conditions',
    mode_of_bill:      'Mode of Bill',
    dc_number:         'DC No',
    dc_date:           'DC Date',
    po_reference:      'Customer Order No',
    sales_order_no:    'Sales Order No',
    dispatch_to:       'Delivery To',
    invoice_number:    'Invoice No',
    customer_order_no: 'Customer Order No',
    so_number:         'Sales Order No',
    customer_name:     'Customer Name',
    total_amount:      'Total Amount',
    vendor_name:       'Vendor Name',
    items_description: 'Items',
    receiver_name:     'Receiver Name',
    vehicle_number:    'Vehicle No',
    quantity:          'Quantity',
  };

  const DOC_LABEL_OVERRIDES: Record<string, Record<string, string>> = {
    CUSTOMER_PO: { po_number: 'Customer PO Number' },
    COMPANY_PO:  { po_number: 'Order No', po_date: 'Order Date' },
    VENDOR_DC:   { po_reference: 'PO Reference' },
  };

  const formatLabel = (key: string) => {
    const docType = metadata?.document_type ?? '';
    const override = DOC_LABEL_OVERRIDES[docType]?.[key];
    if (override) return override;
    if (FIELD_LABELS[key]) return FIELD_LABELS[key];
    return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  };

  const sortedFormKeys = (keys: string[]): string[] => {
    const docType = metadata?.document_type ?? '';
    const order = FIELD_ORDER[docType] ?? [];
    const inOrder = order.filter((k) => keys.includes(k));
    const rest    = keys.filter((k) => !order.includes(k) && k !== 'operator_notes');
    return [...inOrder, ...rest];
  };

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <Loader2 size={32} className="animate-spin text-white" />
      </div>
    );
  }

  const extractionVersion = metadata?.extraction_version;
  const extractionRoute   = metadata?.extraction_route;

  return (
    <div className="fixed inset-0 z-50 flex bg-black/60">

      {/* ── SO Entry Popup — centered overlay on top of the modal ─── */}
      {soPrompt && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                <Hash size={20} className="text-amber-600" />
              </div>
              <div>
                <h4 className="text-base font-semibold text-gray-900">SO Number Required</h4>
                <p className="text-sm text-gray-500">Enter it to complete verification</p>
              </div>
            </div>
            <p className="text-sm text-gray-600">
              The SO number must be set before this document can be verified.
              Enter it now, or close and set it from the PO page before verifying.
            </p>
            <input
              type="text"
              value={soInput}
              onChange={(e) => setSoInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSoSubmit()}
              placeholder="e.g. 1OTM2526-001448"
              autoFocus
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-400 focus:outline-none"
            />
            {updatePOMutation.isError && (
              <p className="text-xs text-red-600">Failed to save SO number. You can set it from the PO page.</p>
            )}
            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={handleSoSubmit}
                disabled={!soInput.trim() || updatePOMutation.isPending || verifyMutation.isPending}
                className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 disabled:opacity-50"
              >
                <Check size={16} />
                {updatePOMutation.isPending || verifyMutation.isPending ? 'Saving...' : 'Save & Verify'}
              </button>
              <button
                onClick={() => { setSoPrompt(null); onClose(); }}
                className="px-4 py-2.5 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Later
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="m-auto bg-white rounded-xl shadow-2xl w-[95vw] h-[90vh] max-w-7xl flex flex-col">

        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h3 className="text-lg font-semibold">
              {mode === 'edit' ? 'Edit Extracted Data' : isManualMode ? 'Manual Data Entry' : 'Review Extracted Data'}
            </h3>
            {metadata && (
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <span className="text-xs text-gray-500 uppercase">
                  {metadata.document_type?.replace(/_/g, ' ')}
                </span>

                {/* Overall confidence */}
                {metadata.confidence_score != null && (
                  <span
                    className={clsx(
                      'text-xs font-medium px-2 py-0.5 rounded-full',
                      metadata.confidence_score >= 80
                        ? 'bg-green-100 text-green-700'
                        : metadata.confidence_score >= 50
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-red-100 text-red-700'
                    )}
                  >
                    {metadata.confidence_score}% confidence
                  </span>
                )}

                {/* ── NEW Phase 1: route badge ─────────────────── */}
                {extractionRoute === 'digital' && (
                  <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-medium">
                    <Zap size={11} /> Digital — no OCR
                  </span>
                )}
                {extractionRoute === 'scanned' && (
                  <span className="inline-flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full font-medium">
                    <Camera size={11} /> Scanned
                  </span>
                )}

                {/* ── NEW Phase 7: extraction version ─────────── */}
                {extractionVersion != null && extractionVersion > 1 && (
                  <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                    v{extractionVersion}
                  </span>
                )}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <X size={20} />
          </button>
        </div>

        {/* ── Body: split view ────────────────────────────────────── */}
        <div className="flex-1 flex min-h-0">

          {/* Left: PDF */}
          <div className="w-1/2 border-r border-gray-200">
            <PDFViewer url={getPreviewUrl(documentId)} />
          </div>

          {/* Right: Form */}
          <div className="w-1/2 flex flex-col">
            <div className="flex-1 overflow-y-auto p-6 space-y-3">

              {/* Manual mode notice */}
              {isManualMode && Object.keys(formData).length > 0 && (
                <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg px-4 py-3 flex items-center gap-2 mb-2">
                  <PenLine size={16} />
                  Manual entry mode — fill in the fields from the document on the left, then click Verify.
                </div>
              )}

              {/* ── NEW Phase 6: validation errors banner ──────── */}
              {validationErrors.length > 0 && (
                <div className="border border-red-300 rounded-lg overflow-hidden mb-1">
                  <button
                    onClick={() => setErrorsOpen((o) => !o)}
                    className="w-full flex items-center justify-between px-4 py-2.5 bg-red-50 text-red-700 text-sm font-medium"
                  >
                    <span className="flex items-center gap-2">
                      <AlertTriangle size={15} />
                      {validationErrors.length} validation error{validationErrors.length > 1 ? 's' : ''} — review before verifying
                    </span>
                    {errorsOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </button>
                  {errorsOpen && (
                    <ul className="px-4 py-2 bg-red-50 space-y-1">
                      {validationErrors.map((err, i) => (
                        <li key={i} className="text-xs text-red-700 flex gap-2">
                          <span className="mt-0.5 flex-shrink-0">•</span>
                          {err}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {/* ── NEW Phase 6: validation warnings banner ────── */}
              {validationWarnings.length > 0 && (
                <div className="border border-amber-300 rounded-lg overflow-hidden mb-1">
                  <button
                    onClick={() => setWarningsOpen((o) => !o)}
                    className="w-full flex items-center justify-between px-4 py-2.5 bg-amber-50 text-amber-700 text-sm font-medium"
                  >
                    <span className="flex items-center gap-2">
                      <AlertTriangle size={15} />
                      {validationWarnings.length} warning{validationWarnings.length > 1 ? 's' : ''}
                    </span>
                    {warningsOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </button>
                  {warningsOpen && (
                    <ul className="px-4 py-2 bg-amber-50 space-y-1">
                      {validationWarnings.map((w, i) => (
                        <li key={i} className="text-xs text-amber-700 flex gap-2">
                          <span className="mt-0.5 flex-shrink-0">•</span>
                          {w}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {/* ── Per-field confidence legend (only when LM data present) */}
              {fieldConf && Object.keys(fieldConf).length > 0 && (
                <div className="flex items-center gap-3 text-xs text-gray-400 pb-1">
                  <span>Field confidence:</span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-green-400 inline-block" /> ≥85%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" /> 60–85%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-red-400 inline-block" /> &lt;60%
                  </span>
                </div>
              )}

              {/* ── Form fields ──────────────────────────────────── */}
              {sortedFormKeys(Object.keys(formData).filter((k) => !ARRAY_FIELDS.has(k))).map((key) => {
                const value = formData[key];
                const conf  = getFieldConfidence(key);
                const isChanged = value !== (originalSnapshot.current[key] ?? '');

                return (
                  <div key={key}>
                    <label className="flex items-center justify-between text-xs font-medium text-gray-500 mb-1">
                      <span>
                        {formatLabel(key)}
                        {/* Changed indicator */}
                        {isChanged && (
                          <span className="ml-1.5 text-blue-500 font-semibold" title="Modified">
                            ✎
                          </span>
                        )}
                      </span>
                      {/* ── NEW Phase 5: per-field confidence badge ── */}
                      {conf !== null && (
                        <span
                          className={clsx(
                            'text-xs px-1.5 py-0.5 rounded font-medium',
                            confBadgeColour(conf)
                          )}
                        >
                          {Math.round(conf * 100)}%
                        </span>
                      )}
                    </label>

                    {key === 'signature_present' ? (
                      <select
                        value={value}
                        onChange={(e) =>
                          setFormData((f) => ({ ...f, [key]: e.target.value }))
                        }
                        className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none border-gray-300"
                      >
                        <option value="">Unknown</option>
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={value}
                        onChange={(e) =>
                          setFormData((f) => ({ ...f, [key]: e.target.value }))
                        }
                        placeholder={`Enter ${formatLabel(key).toLowerCase()}`}
                        className={clsx(
                          'w-full px-3 py-2 border-l-4 border rounded-lg text-sm',
                          'focus:ring-2 focus:ring-blue-500 focus:outline-none',
                          // Left border from confidence, right border from value presence
                          conf !== null
                            ? confColour(conf)
                            : value
                              ? 'border-gray-300'
                              : 'border-red-200 bg-red-50'
                        )}
                      />
                    )}
                  </div>
                );
              })}

              {Object.keys(formData).length === 0 && !isLoading && (
                <p className="text-sm text-gray-400 py-8 text-center">
                  No extraction data or template available. Try re-extracting the document.
                </p>
              )}

              {/* ── Operator Remarks — always visible ─────────────── */}
              {'operator_notes' in formData && (
                <div className="pt-3 mt-1 border-t border-gray-100">
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    Remarks
                    {formData['operator_notes'] !== (originalSnapshot.current['operator_notes'] ?? '') && (
                      <span className="ml-1.5 text-blue-500 font-semibold" title="Modified">✎</span>
                    )}
                  </label>
                  <textarea
                    rows={3}
                    value={formData['operator_notes']}
                    onChange={(e) => setFormData((f) => ({ ...f, operator_notes: e.target.value }))}
                    placeholder="Add any notes or remarks about this document..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none"
                  />
                </div>
              )}

              {/* ── Custom Fields ──────────────────────────────────── */}
              <div className="pt-3 mt-1 border-t border-gray-100">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-gray-500">Custom Fields</span>
                  <button
                    onClick={addCustomField}
                    className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
                  >
                    <Plus size={13} /> Add Field
                  </button>
                </div>
                {customFields.length === 0 && (
                  <p className="text-xs text-gray-400 italic">No custom fields — click "Add Field" to add one.</p>
                )}
                {customFields.map(({ id, label, value }) => (
                  <div key={id} className="flex gap-2 mb-2 items-center">
                    <input
                      placeholder="Label"
                      value={label}
                      onChange={(e) => setCustomFields((f) => f.map((cf) => cf.id === id ? { ...cf, label: e.target.value } : cf))}
                      className="w-2/5 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                    />
                    <input
                      placeholder="Value"
                      value={value}
                      onChange={(e) => setCustomFields((f) => f.map((cf) => cf.id === id ? { ...cf, value: e.target.value } : cf))}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                    />
                    <button
                      onClick={() => removeCustomField(id)}
                      className="p-1.5 text-gray-400 hover:text-red-500 rounded"
                    >
                      <X size={15} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* ── Action buttons ─────────────────────────────────── */}
            <div className="px-6 py-4 border-t border-gray-200 space-y-2">

              {mode === 'edit' ? (
                <>
                  {correctionsMutation.isError && (
                    <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
                      Failed to save changes. Please try again.
                    </div>
                  )}
                  <div className="flex items-center justify-between gap-3">
                    {(() => {
                      const changed = Object.entries(formData).filter(
                        ([k, v]) => !k.startsWith('_') && v !== (originalSnapshot.current[k] ?? '')
                      ).length;
                      return changed > 0 ? (
                        <span className="text-xs text-blue-600">
                          {changed} field{changed > 1 ? 's' : ''} modified
                        </span>
                      ) : (
                        <span />
                      );
                    })()}
                    <div className="flex items-center gap-3">
                      <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleSave}
                        disabled={correctionsMutation.isPending}
                        className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                      >
                        <Check size={16} />
                        {correctionsMutation.isPending ? 'Saving...' : 'Save Changes'}
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  {/* ── SO mismatch banner ─────────────────────────────── */}
                  {soMismatchMsg && (
                    <div className="bg-orange-50 border border-orange-300 rounded-lg px-4 py-3 space-y-1">
                      <div className="flex items-center gap-2 text-orange-800 text-sm font-semibold">
                        <AlertTriangle size={15} />
                        SO Number Mismatch
                      </div>
                      <p className="text-xs text-orange-700">{soMismatchMsg}</p>
                      <p className="text-xs text-orange-700 font-medium">
                        Please check the correct SO number on the PO, or re-upload the correct document.
                      </p>
                    </div>
                  )}

                  {!soPrompt && (
                    <>
                      {(verifyMutation.isError || rejectMutation.isError) && (
                        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
                          {(() => {
                            const err = (verifyMutation.error || rejectMutation.error) as any;
                            const detail = err?.response?.data?.detail;
                            if (typeof detail === 'string') return detail;
                            if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
                            return err?.message || 'Operation failed. Please try again.';
                          })()}
                        </div>
                      )}
                      <div className="flex items-center justify-between gap-3">
                        {(() => {
                          const changed = Object.entries(formData).filter(
                            ([k, v]) => !k.startsWith('_') && v !== (originalSnapshot.current[k] ?? '')
                          ).length;
                          return changed > 0 ? (
                            <span className="text-xs text-blue-600">
                              {changed} field{changed > 1 ? 's' : ''} modified
                            </span>
                          ) : (
                            <span />
                          );
                        })()}

                        <div className="flex items-center gap-3">
                          <button
                            onClick={handleReject}
                            disabled={rejectMutation.isPending}
                            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-red-600 border border-red-300 rounded-lg hover:bg-red-50 disabled:opacity-50"
                          >
                            <Ban size={16} />
                            {rejectMutation.isPending ? 'Rejecting...' : 'Reject'}
                          </button>
                          <button
                            onClick={onClose}
                            className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={handleVerify}
                            disabled={verifyMutation.isPending}
                            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50"
                          >
                            <Check size={16} />
                            {verifyMutation.isPending ? 'Verifying...' : 'Verify'}
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
