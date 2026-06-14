import { useEffect, useState } from 'react';
import { documentPreviewPageUrl, documentPreviewUrl } from '../../api/documents';
import type { BundleDocument, FieldLocation } from '../../types/api';

export function PdfPreviewPane({
  document,
  selectedPage,
  onPageChange,
  highlightLocation,
}: {
  document: BundleDocument;
  selectedPage: number;
  onPageChange: (page: number) => void;
  highlightLocation?: FieldLocation | null;
}) {
  const [zoom, setZoom] = useState(1.6);
  const pageCount = pageCountFromDocument(document);

  useEffect(() => {
    setZoom(1.6);
  }, [document.id]);

  const showHighlight = canHighlight(highlightLocation) && highlightLocation!.page === selectedPage;
  const noHighlight = !showHighlight && isScannedNoHighlight(highlightLocation);

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
      {noHighlight ? (
        <p className="pdf-highlight-unavailable" role="status">
          Highlight unavailable — field was extracted from scanned OCR text without position data.
        </p>
      ) : null}
      <div className="pdf-pane__viewport">
        <div className="pdf-highlight-container" style={{ width: `${Math.round(zoom * 100)}%` }}>
          <img
            alt={`PDF page ${selectedPage} preview`}
            src={documentPreviewPageUrl(document.id, selectedPage)}
            style={{ width: '100%' }}
          />
          {showHighlight ? (
            <div
              className="pdf-highlight-overlay"
              style={bboxToPercent(
                highlightLocation!.bbox!,
                highlightLocation!.page_width!,
                highlightLocation!.page_height!,
              )}
              aria-hidden="true"
            />
          ) : null}
        </div>
      </div>
    </section>
  );
}

export function bboxToPercent(
  bbox: [number, number, number, number],
  pageWidth: number,
  pageHeight: number,
): { left: string; top: string; width: string; height: string } {
  const [x0, y0, x1, y1] = bbox;
  return {
    left: `${((x0 / pageWidth) * 100).toFixed(2)}%`,
    top: `${((y0 / pageHeight) * 100).toFixed(2)}%`,
    width: `${(((x1 - x0) / pageWidth) * 100).toFixed(2)}%`,
    height: `${(((y1 - y0) / pageHeight) * 100).toFixed(2)}%`,
  };
}

export function canHighlight(location: FieldLocation | null | undefined): boolean {
  return !!(location?.bbox && location.page_width && location.page_height);
}

export function isScannedNoHighlight(location: FieldLocation | null | undefined): boolean {
  if (!location) return false;
  return !location.bbox;
}

function pageCountFromDocument(document: BundleDocument): number {
  const pageCount = document.metadata?.diagnostics?.page_count;
  return typeof pageCount === 'number' && pageCount > 0 ? pageCount : 1;
}
