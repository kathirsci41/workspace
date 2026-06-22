import { Link } from 'react-router-dom';
import { documentPreviewUrl } from '../../api/documents';
import {
  documentExtractionStatus,
  documentRecordTypeLabel,
  identifierLabel,
  statusLabel,
  type DocumentGroup,
} from '../../lib/build1';
import { formatDateTime } from '../../lib/format';
import type { BundleDocument } from '../../types/api';

export function DocumentSlotCard({
  bundleId,
  group,
  isBusy,
  onUpload,
  onExtract,
  onReextract,
  onDelete,
  activityLabel,
}: {
  bundleId: string;
  group: DocumentGroup;
  isBusy: (documentId: string) => boolean;
  activityLabel?: (documentId: string) => string | null;
  onUpload: () => void;
  onExtract: (document: BundleDocument) => void;
  onReextract: (document: BundleDocument) => void;
  onDelete: (document: BundleDocument) => void;
}) {
  return (
    <section className={`document-slot document-slot--${group.state}`} role="region" aria-label={group.label}>
      <div className="document-slot__header">
        <div>
          <h3>{group.label}</h3>
          <span className="muted">Required document</span>
        </div>
        <span className="document-slot__count">{group.documents.length} uploaded</span>
      </div>

      {group.documents.length ? (
        <>
          <div className="document-record-list">
            {group.documents.map((document) => (
              <DocumentRecordRow
                key={document.id}
                bundleId={bundleId}
                document={document}
                group={group}
                isBusy={isBusy(document.id)}
                activityLabel={activityLabel?.(document.id) ?? null}
                onExtract={() => onExtract(document)}
                onReextract={() => onReextract(document)}
                onDelete={() => onDelete(document)}
              />
            ))}
          </div>
          <button className="button button--ghost document-slot__add" type="button" onClick={onUpload}>
            Add another {group.label}
          </button>
        </>
      ) : (
        <>
          <p className="document-slot__empty">No {group.label} uploaded.</p>
          <button className="button button--primary" type="button" aria-label={`Upload ${group.label}`} onClick={onUpload}>Upload</button>
        </>
      )}
    </section>
  );
}

function DocumentRecordRow({
  bundleId,
  document,
  group,
  isBusy,
  activityLabel,
  onExtract,
  onReextract,
  onDelete,
}: {
  bundleId: string;
  document: BundleDocument;
  group: DocumentGroup;
  isBusy: boolean;
  activityLabel: string | null;
  onExtract: () => void;
  onReextract: () => void;
  onDelete: () => void;
}) {
  const extractionStatus = activityLabel ?? documentExtractionStatus(document);
  const shouldReextract = extractionStatus === 'Extracted' || extractionStatus === 'Failed';
  const route = document.metadata?.diagnostics?.extraction_route;
  const routeLabel = typeof route === 'string' && route ? identifierLabel(route) : '-';
  const isActionBusy = isBusy || activityLabel === 'Waiting in extraction queue' || activityLabel === 'Extracting';

  return (
    <article className="document-record" aria-label={document.filename}>
      <div className="document-record__header">
        <div>
          <h4>{document.filename}</h4>
          {document.document_type !== group.type ? <span className="muted">Alias record</span> : null}
        </div>
        <span className="status-badge status-badge--neutral">{extractionStatus}</span>
      </div>

      <dl className="document-record__details">
        <div>
          <dt>Document type</dt>
          <dd>{documentRecordTypeLabel(document.document_type, group.type)}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{statusLabel(document.status)}</dd>
        </div>
        <div>
          <dt>Extraction status</dt>
          <dd>{extractionStatus}</dd>
        </div>
        <div>
          <dt>Extraction route</dt>
          <dd>{routeLabel}</dd>
        </div>
        <div>
          <dt>Uploaded</dt>
          <dd>{formatDateTime(document.created_at)}</dd>
        </div>
      </dl>

      {document.last_error || document.metadata?.last_error ? (
        <p className="state-message state-message--error">{document.last_error || document.metadata?.last_error}</p>
      ) : null}

      <div className="document-record__actions">
        <button
          className="button button--primary button--small"
          type="button"
          aria-label={`${shouldReextract ? 'Re-extract' : 'Extract'} ${document.filename}`}
          disabled={isActionBusy}
          onClick={shouldReextract ? onReextract : onExtract}
        >
          {isActionBusy ? (activityLabel === 'Waiting in extraction queue' ? 'Queued' : 'Working...') : shouldReextract ? 'Re-extract' : 'Extract'}
        </button>
        <Link
          className="button button--ghost button--small"
          aria-label={`Review ${document.filename}`}
          to={`/bundles/${bundleId}/extraction/${document.id}`}
        >
          Review
        </Link>
        <a
          className="button button--ghost button--small"
          aria-label={`Preview ${document.filename}`}
          href={documentPreviewUrl(document.id)}
          target="_blank"
          rel="noreferrer"
        >
          Preview
        </a>
        <button
          className="button button--danger button--small"
          type="button"
          aria-label={`Delete ${document.filename}`}
          disabled={isActionBusy}
          onClick={onDelete}
        >
          Delete
        </button>
      </div>
    </article>
  );
}
