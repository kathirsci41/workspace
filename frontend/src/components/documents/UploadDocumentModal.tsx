import { FormEvent, useState } from 'react';
import { REQUIRED_DOCUMENT_SLOTS } from '../../lib/build1';
import type { DocumentType } from '../../types/api';

export function UploadDocumentModal({
  isOpen,
  documentType,
  isUploading,
  error,
  onClose,
  onUpload,
}: {
  isOpen: boolean;
  documentType: DocumentType | null;
  isUploading: boolean;
  error: string | null;
  onClose: () => void;
  onUpload: (documentType: DocumentType, file: File) => Promise<void>;
}) {
  const [selectedType, setSelectedType] = useState<DocumentType>(documentType ?? 'CUSTOMER_PO');
  const [file, setFile] = useState<File | null>(null);
  const activeType = documentType ?? selectedType;
  const label = REQUIRED_DOCUMENT_SLOTS.find((slot) => slot.type === activeType)?.label ?? activeType;

  if (!isOpen) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    await onUpload(activeType, file);
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="upload-document-title">
        <div className="modal__header">
          <h2 id="upload-document-title">Upload Document</h2>
          <button className="icon-button" type="button" aria-label="Close upload document modal" onClick={onClose}>x</button>
        </div>
        <form className="form-grid" onSubmit={submit}>
          {documentType ? (
            <p><strong>{label}</strong></p>
          ) : (
            <label>
              Document type
              <select value={selectedType} onChange={(event) => setSelectedType(event.target.value as DocumentType)}>
                {REQUIRED_DOCUMENT_SLOTS.map((slot) => <option key={slot.type} value={slot.type}>{slot.label}</option>)}
              </select>
            </label>
          )}
          <label>
            PDF file
            <input type="file" accept="application/pdf,.pdf" required onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>
          {error ? <p role="alert">{error}</p> : null}
          <div className="modal__actions">
            <button className="button button--ghost" type="button" onClick={onClose}>Cancel</button>
            <button className="button button--primary" type="submit" disabled={isUploading || !file}>
              {isUploading ? 'Uploading...' : 'Upload'}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
