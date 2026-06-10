import { Navigate, useParams } from 'react-router-dom';
import { useState } from 'react';
import { getBundle } from '../api/bundles';
import { deleteDocument, extractDocument, listBundleDocuments, reextractDocument, uploadDocument } from '../api/documents';
import { getVerificationSummary } from '../api/verification';
import { DocumentSlotCard } from '../components/documents/DocumentSlotCard';
import { UploadDocumentModal } from '../components/documents/UploadDocumentModal';
import { ErrorState } from '../components/common/ErrorState';
import { KpiCard } from '../components/common/KpiCard';
import { LoadingState } from '../components/common/LoadingState';
import { AppShell } from '../components/layout/AppShell';
import { WorkflowTabs } from '../components/layout/WorkflowTabs';
import { useAsyncResource } from '../hooks/useAsyncResource';
import { buildDocumentSlots, extractionProgress } from '../lib/build1';
import type { BundleDocument, DocumentType, OrderBundle, VerificationSummary } from '../types/api';

export function DocumentsPage() {
  const { bundleId } = useParams<{ bundleId: string }>();
  if (!bundleId) return <Navigate to="/bundles" replace />;
  return <DocumentsContent bundleId={bundleId} />;
}

function DocumentsContent({ bundleId }: { bundleId: string }) {
  const bundle = useAsyncResource<OrderBundle>(() => getBundle(bundleId), [bundleId]);
  const documents = useAsyncResource<BundleDocument[]>(() => listBundleDocuments(bundleId), [bundleId]);
  const summary = useAsyncResource<VerificationSummary>(() => getVerificationSummary(bundleId), [bundleId]);
  const [modalType, setModalType] = useState<DocumentType | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const slots = buildDocumentSlots(documents.data ?? []);
  const extraction = extractionProgress(documents.data ?? []);
  const missing = slots.filter((slot) => !slot.document).length;

  async function refresh() {
    await Promise.all([documents.reload(), summary.reload(), bundle.reload()]);
  }

  async function run(actionName: string, action: () => Promise<unknown>) {
    setBusyAction(actionName);
    setMutationError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleUpload(documentType: DocumentType, file: File) {
    await run('upload', () => uploadDocument(bundleId, documentType, file));
    setIsUploadOpen(false);
  }

  return (
    <AppShell
      bundleId={bundleId}
      title="Documents"
      subtitle={bundle.data?.bundle_number ?? 'Upload and manage the required PDFs.'}
      breadcrumbs={[{ label: 'Bundles', href: '/bundles' }, { label: bundle.data?.bundle_number ?? bundleId, href: `/bundles/${bundleId}/overview` }, { label: 'Documents' }]}
      actions={<button className="button button--primary" type="button" onClick={() => { setModalType(null); setIsUploadOpen(true); }}>Upload Document</button>}
    >
      <WorkflowTabs bundleId={bundleId} />
      <ErrorState message={documents.error ?? summary.error ?? mutationError} />
      {documents.isLoading ? <LoadingState label="Loading documents..." /> : null}

      <section className="kpi-grid" aria-label="Document KPIs">
        <KpiCard label="Required Documents" value={5} tone="info" />
        <KpiCard label="Uploaded" value={documents.data?.length ?? 0} tone="success" />
        <KpiCard label="Extracted" value={extraction.extracted} tone="success" />
        <KpiCard label="Pending Extraction" value={extraction.pending} tone="warning" />
        <KpiCard label="Missing" value={missing} tone={missing ? 'danger' : 'success'} />
      </section>

      <section className="document-slot-grid" aria-label="Required document slots">
        {slots.map((slot) => (
          <DocumentSlotCard
            key={slot.type}
            bundleId={bundleId}
            slot={slot}
            isBusy={busyAction?.includes(slot.document?.id ?? slot.type) ?? false}
            onUpload={() => { setModalType(slot.type); setIsUploadOpen(true); }}
            onExtract={() => slot.document && run(`extract-${slot.document.id}`, () => extractDocument(slot.document!.id))}
            onReextract={() => slot.document && run(`reextract-${slot.document.id}`, () => reextractDocument(slot.document!.id))}
            onDelete={() => slot.document && run(`delete-${slot.document.id}`, () => deleteDocument(slot.document!.id))}
          />
        ))}
      </section>

      <UploadDocumentModal
        isOpen={isUploadOpen}
        documentType={modalType}
        isUploading={busyAction === 'upload'}
        error={mutationError}
        onClose={() => setIsUploadOpen(false)}
        onUpload={handleUpload}
      />
    </AppShell>
  );
}
