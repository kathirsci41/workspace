import { Link } from 'react-router-dom';
import { documentPreviewUrl } from '../../api/documents';
import { documentExtractionStatus, documentReviewStatus, documentUploadStatus, type DocumentSlot } from '../../lib/build1';

export function DocumentSlotCard({
  bundleId,
  slot,
  isBusy,
  onUpload,
  onExtract,
  onReextract,
  onDelete,
}: {
  bundleId: string;
  slot: DocumentSlot;
  isBusy: boolean;
  onUpload: () => void;
  onExtract: () => void;
  onReextract: () => void;
  onDelete: () => void;
}) {
  const document = slot.document;
  const extractionStatus = documentExtractionStatus(document);
  const primaryAction = document
    ? extractionStatus === 'Extracted'
      ? { label: 'Review Extraction', kind: 'link' as const }
      : { label: isBusy ? 'Extracting...' : 'Run Extraction', kind: 'extract' as const }
    : { label: 'Upload Document', kind: 'upload' as const };
  return (
    <article className={`document-slot document-slot--${slot.state}`}>
      <div className="document-slot__header">
        <div>
          <h3>{slot.label}</h3>
          <span className="muted">Required document</span>
        </div>
      </div>
      {document ? (
        <>
          <div className="document-slot__primary">
            {primaryAction.kind === 'link' ? (
              <Link className="button button--primary" to={`/bundles/${bundleId}/extraction/${document.id}`}>{primaryAction.label}</Link>
            ) : (
              <button className="button button--primary" type="button" disabled={isBusy} onClick={onExtract}>{primaryAction.label}</button>
            )}
          </div>
          <dl className="detail-list">
            <div>
              <dt>Filename</dt>
              <dd>{document.filename}</dd>
            </div>
          </dl>
          <div className="status-dimensions">
            <span><b>Document</b>{documentUploadStatus(document)}</span>
            <span><b>Extraction</b>{extractionStatus}</span>
            <span><b>Review</b>{documentReviewStatus(document)}</span>
          </div>
          {document.last_error || document.metadata?.last_error ? (
            <p className="state-message state-message--error">{document.last_error || document.metadata?.last_error}</p>
          ) : null}
          <div className="document-slot__secondary-actions">
            <a className="button button--ghost" href={documentPreviewUrl(document.id)} target="_blank" rel="noreferrer">Preview PDF</a>
            <details className="more-menu">
              <summary className="button button--ghost">More</summary>
              <div className="more-menu__items">
                <button type="button" onClick={onUpload}>Replace</button>
                {extractionStatus === 'Extracted' ? (
                  <button type="button" disabled={isBusy} onClick={onReextract}>{isBusy ? 'Re-extracting...' : 'Re-extract'}</button>
                ) : null}
                <button className="more-menu__danger" type="button" disabled={isBusy} onClick={onDelete}>Delete</button>
              </div>
            </details>
          </div>
        </>
      ) : (
        <>
          <div className="status-dimensions">
            <span><b>Document</b>Missing</span>
            <span><b>Extraction</b>Pending</span>
            <span><b>Review</b>Needs Review</span>
          </div>
          <button className="button button--primary" type="button" onClick={onUpload}>Upload Document</button>
        </>
      )}
    </article>
  );
}
