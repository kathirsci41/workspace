import { useEffect, useState } from 'react';
import { documentPreviewPageUrl, documentPreviewUrl } from '../../api/documents';
import type { BundleDocument } from '../../types/api';

export function PdfPreviewPane({
  document,
  selectedPage,
  onPageChange,
}: {
  document: BundleDocument;
  selectedPage: number;
  onPageChange: (page: number) => void;
}) {
  const [zoom, setZoom] = useState(1.6);
  const pageCount = pageCountFromDocument(document);

  useEffect(() => {
    setZoom(1.6);
  }, [document.id]);

  return (
    <section className="pdf-pane" aria-label="PDF preview">
      <div className="pdf-pane__toolbar">
        <a className="button button--ghost" href={documentPreviewUrl(document.id)} target="_blank" rel="noreferrer">Open PDF</a>
        <button type="button" className="button button--ghost" disabled={selectedPage <= 1} onClick={() => onPageChange(selectedPage - 1)}>Previous</button>
        <span>Page {selectedPage} of {pageCount}</span>
        <button type="button" className="button button--ghost" disabled={selectedPage >= pageCount} onClick={() => onPageChange(selectedPage + 1)}>Next</button>
        <button type="button" className="button button--ghost" disabled={zoom <= 0.75} onClick={() => setZoom((current) => Math.max(0.75, current - 0.25))}>Zoom out</button>
        <span>{Math.round(zoom * 100)}%</span>
        <button type="button" className="button button--ghost" disabled={zoom >= 2} onClick={() => setZoom((current) => Math.min(2, current + 0.25))}>Zoom in</button>
      </div>
      <div className="pdf-pane__viewport">
        <img
          alt={`PDF page ${selectedPage} preview`}
          src={documentPreviewPageUrl(document.id, selectedPage)}
          style={{ width: `${Math.round(zoom * 100)}%` }}
        />
      </div>
    </section>
  );
}

function pageCountFromDocument(document: BundleDocument): number {
  const pageCount = document.metadata?.diagnostics?.page_count;
  return typeof pageCount === 'number' && pageCount > 0 ? pageCount : 1;
}
