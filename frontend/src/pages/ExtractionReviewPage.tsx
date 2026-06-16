import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { useState } from 'react';
import { listAuditEvents } from '../api/audit';
import { getBundle } from '../api/bundles';
import { getDocument, listBundleDocuments, patchExtractedData, reextractDocument } from '../api/documents';
import { getVerificationSummary } from '../api/verification';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PdfPreviewPane } from '../components/documents/PdfPreviewPane';
import { ExtractedFieldsPanel } from '../components/extraction/ExtractedFieldsPanel';
import { useExtractionActivity } from '../components/extraction/ExtractionActivityContext';
import { ManualCorrectionModal } from '../components/extraction/ManualCorrectionModal';
import { AppShell } from '../components/layout/AppShell';
import { WorkflowTabs } from '../components/layout/WorkflowTabs';
import { useAsyncResource } from '../hooks/useAsyncResource';
import { documentLabel } from '../lib/build1';
import { formatDateTime } from '../lib/format';
import type { AuditEvent, BundleDocument, OcrRotationPreference, OrderBundle, VerificationSummary } from '../types/api';

export function ExtractionReviewPage() {
  const { bundleId, documentId } = useParams<{ bundleId: string; documentId?: string }>();
  if (!bundleId) return <Navigate to="/bundles" replace />;
  return <ExtractionReviewContent bundleId={bundleId} documentId={documentId} />;
}

function ExtractionReviewContent({ bundleId, documentId }: { bundleId: string; documentId?: string }) {
  const navigate = useNavigate();
  const bundle = useAsyncResource<OrderBundle>(() => getBundle(bundleId), [bundleId]);
  const documents = useAsyncResource<BundleDocument[]>(() => listBundleDocuments(bundleId), [bundleId]);
  const selectedDocumentId = documentId ?? documents.data?.[0]?.id ?? null;
  const selectedDocument = useAsyncResource<BundleDocument | null>(() => selectedDocumentId ? getDocument(selectedDocumentId) : Promise.resolve(null), [selectedDocumentId]);
  const summary = useAsyncResource<VerificationSummary>(() => getVerificationSummary(bundleId), [bundleId]);
  const audit = useAsyncResource<AuditEvent[]>(() => listAuditEvents(bundleId), [bundleId]);
  const [page, setPage] = useState(1);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [highlightedField, setHighlightedField] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isReextracting, setIsReextracting] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [ocrRotationPreferences, setOcrRotationPreferences] = useState<Record<string, OcrRotationPreference>>({});
  const extractionActivity = useExtractionActivity();
  const activeDocument = selectedDocument.data;
  const fieldLocations = activeDocument?.metadata?.field_locations ?? {};
  const highlightLocation = highlightedField ? (fieldLocations[highlightedField] ?? null) : null;
  const ocrRotationPreference: OcrRotationPreference = activeDocument
    ? ocrRotationPreferences[activeDocument.id] ?? 'auto'
    : 'auto';
  const activeDocumentIsExtracting = activeDocument ? extractionActivity.isExtracting(activeDocument.id) : false;

  function handleFieldClick(field: string) {
    setHighlightedField(field);
    const location = fieldLocations[field];
    if (location?.page && typeof location.page === 'number') {
      setPage(location.page);
    }
  }

  async function refreshAll() {
    await Promise.all([selectedDocument.reload(), documents.reload(), summary.reload(), audit.reload()]);
  }

  async function saveCorrection(field: string, value: string, reason: string) {
    if (!activeDocument) return;
    setIsSaving(true);
    setMutationError(null);
    try {
      await patchExtractedData(activeDocument.id, { [field]: value }, reason);
      setEditingField(null);
      await refreshAll();
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleReextract() {
    if (!activeDocument) return;
    setIsReextracting(true);
    setMutationError(null);
    try {
      await extractionActivity.runExtraction(
        activeDocument,
        () => reextractDocument(activeDocument.id, { ocrRotationDegrees: ocrRotationPreference }),
      );
      await refreshAll();
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsReextracting(false);
    }
  }

  return (
    <AppShell
      bundleId={bundleId}
      title="Extraction Review"
      subtitle={bundle.data?.bundle_number ?? 'Review extracted values against PDF evidence.'}
      breadcrumbs={[{ label: 'Bundles', href: '/bundles' }, { label: bundle.data?.bundle_number ?? bundleId, href: `/bundles/${bundleId}/overview` }, { label: 'Extraction Review' }]}
      actions={(
        <div className="extraction-actions">
          <span className="extraction-actions__rotation">OCR Rotation: {ocrRotationLabel(ocrRotationPreference)}</span>
          <button
            className="button button--primary"
            type="button"
            disabled={!activeDocument || isReextracting || activeDocumentIsExtracting}
            onClick={handleReextract}
          >
            {isReextracting || activeDocumentIsExtracting ? 'Re-extracting...' : 'Re-extract'}
          </button>
        </div>
      )}
    >
      <WorkflowTabs bundleId={bundleId} />
      <ErrorState message={documents.error ?? selectedDocument.error ?? summary.error ?? audit.error ?? mutationError} />
      {documents.isLoading || selectedDocument.isLoading ? <LoadingState label="Loading extraction review..." /> : null}

      <div className="review-grid">
        <aside className="panel document-selector-panel">
          <h2>Documents in Bundle</h2>
          <label>
            Document selector
            <select
              aria-label="Document selector"
              value={selectedDocumentId ?? ''}
              onChange={(event) => {
                setPage(1);
                navigate(`/bundles/${bundleId}/extraction/${event.target.value}`);
              }}
            >
              {(documents.data ?? []).map((document) => (
                <option key={document.id} value={document.id}>{documentLabel(document.document_type)} - {document.filename}</option>
              ))}
            </select>
          </label>
          {activeDocument ? (
            <dl className="detail-list">
              <div>
                <dt>Document type</dt>
                <dd>{documentLabel(activeDocument.document_type)}</dd>
              </div>
              <div>
                <dt>Filename</dt>
                <dd className="safe-wrap">{activeDocument.filename}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{formatDateTime(activeDocument.updated_at)}</dd>
              </div>
              <div>
                <dt>Primary reference</dt>
                <dd>{activeDocument.metadata?.primary_ref_no ?? '-'}</dd>
              </div>
            </dl>
          ) : null}
        </aside>

        <div className="panel preview-panel">
          {activeDocument ? (
            <PdfPreviewPane
              document={activeDocument}
              selectedPage={page}
              highlightLocation={highlightLocation}
              ocrRotationPreference={ocrRotationPreference}
              onOcrRotationPreferenceChange={(nextPreference) => {
                setOcrRotationPreferences((prev) => ({
                  ...prev,
                  [activeDocument.id]: nextPreference,
                }));
              }}
            />
          ) : <p className="muted">Upload a document to preview extracted evidence.</p>}
        </div>

        <div className="panel fields-panel-wrap">
          {activeDocument ? (
            <>
              <p className="fields-hint">Click a field name to locate it in the PDF.</p>
              <ExtractedFieldsPanel document={activeDocument} onEdit={setEditingField} onFieldClick={handleFieldClick} />
            </>
          ) : (
            <p className="muted">No document selected.</p>
          )}
        </div>
      </div>

      <ManualCorrectionModal
        field={editingField}
        currentValue={editingField ? activeDocument?.metadata?.extracted_data?.[editingField] : null}
        isSaving={isSaving}
        error={mutationError}
        onClose={() => setEditingField(null)}
        onSave={saveCorrection}
      />
    </AppShell>
  );
}

function ocrRotationLabel(preference: OcrRotationPreference): string {
  return preference === 'auto' ? 'Auto' : `${preference}deg`;
}
