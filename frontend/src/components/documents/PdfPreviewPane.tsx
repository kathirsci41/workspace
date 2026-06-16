import { useEffect, useRef, useState } from 'react';
import { documentPreviewPageUrl, documentPreviewUrl } from '../../api/documents';
import type { BundleDocument, FieldLocation, OcrRotationPreference } from '../../types/api';
import { bboxToPercent, canHighlight, isScannedNoHighlight } from './pdfHighlight';

type Rotation = 0 | 90 | 180 | 270;
type PageDims = { w: number; h: number };

const DEFAULT_PAGE_DIMS: PageDims = { w: 210, h: 297 };

export function PdfPreviewPane({
  document,
  selectedPage,
  highlightLocation,
  ocrRotationPreference = 'auto',
  onOcrRotationPreferenceChange,
}: {
  document: BundleDocument;
  selectedPage: number;
  onPageChange?: (page: number) => void;
  highlightLocation?: FieldLocation | null;
  ocrRotationPreference?: OcrRotationPreference;
  onOcrRotationPreferenceChange?: (rotation: OcrRotationPreference) => void;
}) {
  const [zoom, setZoom] = useState(1.0);
  const [fitToWidth, setFitToWidth] = useState(true);
  const [rotation, setRotation] = useState<Rotation>(0);
  const [loadedPages, setLoadedPages] = useState<Set<number>>(new Set());
  const [failedPages, setFailedPages] = useState<Set<number>>(new Set());
  const [pageDims, setPageDims] = useState<Map<number, PageDims>>(new Map());
  const [pdfModalOpen, setPdfModalOpen] = useState(false);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const viewportRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const pageCount = pageCountFromDocument(document);

  useEffect(() => {
    setLoadedPages(new Set());
    setFailedPages(new Set());
    setPageDims(new Map());
    setFitToWidth(true);
    setZoom(1.0);
    setRotation(0);
    pageRefs.current.clear();
  }, [document.id]);

  useEffect(() => {
    const el = pageRefs.current.get(selectedPage);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [selectedPage]);

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      const raw = -e.deltaY * 0.003;
      const delta = Math.max(-0.15, Math.min(0.15, raw));
      setFitToWidth(false);
      setZoom((z) => Math.min(3, Math.max(0.5, +(z + delta).toFixed(3))));
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (pdfModalOpen) {
      dialog.showModal();
    } else if (dialog.open) {
      dialog.close();
    }
  }, [pdfModalOpen]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const onCancel = (e: Event) => {
      e.preventDefault();
      setPdfModalOpen(false);
    };
    dialog.addEventListener('cancel', onCancel);
    return () => dialog.removeEventListener('cancel', onCancel);
  }, []);

  function handleDialogBackdropClick(e: React.MouseEvent<HTMLDialogElement>) {
    if (e.target === dialogRef.current) setPdfModalOpen(false);
  }

  function markLoaded(page: number, dims?: PageDims) {
    if (dims) {
      setPageDims((prev) => new Map(prev).set(page, dims));
    }
    setLoadedPages((prev) => {
      const next = new Set(prev);
      next.add(page);
      return next;
    });
  }

  function handleImageLoad(page: number, e: React.SyntheticEvent<HTMLImageElement>) {
    const { naturalWidth: w, naturalHeight: h } = e.currentTarget;
    setFailedPages((prev) => {
      if (!prev.has(page)) return prev;
      const next = new Set(prev);
      next.delete(page);
      return next;
    });
    markLoaded(page, w && h ? { w, h } : undefined);
  }

  function handleImageError(page: number) {
    setFailedPages((prev) => {
      const next = new Set(prev);
      next.add(page);
      return next;
    });
    markLoaded(page);
  }

  function rotateRight() {
    setRotation((r) => ((r + 90) % 360) as Rotation);
  }

  function rotateLeft() {
    setRotation((r) => ((r + 270) % 360) as Rotation);
  }

  function rotateReset() {
    setRotation(0);
  }

  function handleOcrRotationChange(value: string) {
    if (!onOcrRotationPreferenceChange) return;
    onOcrRotationPreferenceChange(value === 'auto' ? 'auto' : Number(value) as OcrRotationPreference);
  }

  const isSideways = rotation === 90 || rotation === 270;

  function dimsForPage(page: number): PageDims {
    return pageDims.get(page) ?? DEFAULT_PAGE_DIMS;
  }

  function baseWidthPercent(): number {
    return fitToWidth ? 100 : zoom * 100;
  }

  function pageFrameStyle(page: number): React.CSSProperties {
    const { w, h } = dimsForPage(page);
    const baseWidth = baseWidthPercent();
    if (isSideways) {
      const ratio = h / w;
      return {
        width: percent(baseWidth * ratio),
        aspectRatio: `${h} / ${w}`,
      };
    }
    return {
      width: percent(baseWidth),
      aspectRatio: `${w} / ${h}`,
    };
  }

  function pageLayerStyle(page: number): React.CSSProperties {
    const { w, h } = dimsForPage(page);
    const ratio = h / w;
    return {
      width: isSideways ? percent(100 / ratio) : '100%',
      aspectRatio: `${w} / ${h}`,
      transform: `translate(-50%, -50%) rotate(${rotation}deg)`,
      transformOrigin: 'center center',
    };
  }

  function imageStyle(isLoaded: boolean): React.CSSProperties {
    return {
      width: '100%',
      height: '100%',
      display: isLoaded ? 'block' : 'none',
    };
  }

  return (
    <section className="pdf-pane" aria-label="PDF preview">
      <div className="pdf-pane__toolbar">
        <button
          type="button"
          className="button button--ghost"
          onClick={() => setPdfModalOpen(true)}
          title="Preview full PDF in a popup"
        >
          Preview PDF
        </button>

        <button
          type="button"
          className={`button ${fitToWidth && !isSideways ? 'button--primary' : 'button--ghost'}`}
          onClick={() => setFitToWidth((v) => !v)}
          title={fitToWidth ? 'Switch to manual zoom' : 'Fit to pane width'}
        >
          Fit width
        </button>

        <button
          type="button"
          className="button button--ghost"
          disabled={zoom <= 0.5}
          onClick={() => { setFitToWidth(false); setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2))); }}
          title="Zoom out"
        >
          -
        </button>
        <span className="pdf-zoom-label">{Math.round(zoom * 100)}%</span>
        <button
          type="button"
          className="button button--ghost"
          disabled={zoom >= 3}
          onClick={() => { setFitToWidth(false); setZoom((z) => Math.min(3, +(z + 0.25).toFixed(2))); }}
          title="Zoom in"
        >
          +
        </button>

        <button
          type="button"
          className="button button--ghost"
          onClick={rotateLeft}
          title="Rotate left (counter-clockwise)"
          aria-label="Rotate left"
        >
          ↺
        </button>
        <span className="pdf-rotation-label" aria-label={`Current rotation: ${rotation}°`}>
          {rotation}°
        </span>
        <button
          type="button"
          className="button button--ghost"
          onClick={rotateRight}
          title="Rotate right (clockwise)"
          aria-label="Rotate right"
        >
          ↻
        </button>
        {rotation !== 0 && (
          <button
            type="button"
            className="button button--ghost"
            onClick={rotateReset}
            title="Reset rotation to 0°"
            aria-label="Reset rotation"
          >
            Reset
          </button>
        )}

        <label className="pdf-ocr-rotation">
          <span>OCR Rotation</span>
          <select
            aria-label="OCR rotation"
            value={String(ocrRotationPreference)}
            disabled={!onOcrRotationPreferenceChange}
            onChange={(event) => handleOcrRotationChange(event.target.value)}
          >
            <option value="auto">Auto</option>
            <option value="0">0deg</option>
            <option value="90">90deg</option>
            <option value="180">180deg</option>
            <option value="270">270deg</option>
          </select>
        </label>
        <button
          type="button"
          className="button button--ghost"
          disabled={!onOcrRotationPreferenceChange}
          onClick={() => onOcrRotationPreferenceChange?.(rotation)}
          aria-label="Use current preview rotation for OCR"
          title="Use current preview rotation for OCR"
        >
          Use current preview rotation for OCR
        </button>
        <span className="pdf-ocr-rotation-summary">
          OCR: {ocrRotationPreference === 'auto' ? 'Auto' : `${ocrRotationPreference}deg`}
        </span>

        <span className="pdf-pane__page-count">
          {pageCount} page{pageCount !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="pdf-pane__viewport" ref={viewportRef}>
        {Array.from({ length: pageCount }, (_, i) => i + 1).map((page) => {
          const isLoaded = loadedPages.has(page);
          const hasFailed = failedPages.has(page);
          const showHighlight =
            !hasFailed && rotation === 0 && canHighlight(highlightLocation) && highlightLocation!.page === page;
          const showRotatedHighlightWarning =
            rotation !== 0 && page === selectedPage && canHighlight(highlightLocation) && highlightLocation!.page === page;
          const showNoHighlight =
            rotation === 0 && page === selectedPage && isScannedNoHighlight(highlightLocation);

          return (
            <div
              key={page}
              ref={(el) => {
                if (el) pageRefs.current.set(page, el);
                else pageRefs.current.delete(page);
              }}
              className="pdf-page-wrapper"
              data-page={page}
            >
              <div className="pdf-page-label">Page {page} / {pageCount}</div>

              {showNoHighlight && (
                <p className="pdf-highlight-unavailable" role="status">
                  Highlight unavailable — field was extracted from scanned OCR text without position data.
                </p>
              )}
              {showRotatedHighlightWarning && (
                <p className="pdf-highlight-unavailable" role="status">
                  Highlight position unavailable while rotated — reset rotation to see the field highlight.
                </p>
              )}

              <div
                className="pdf-highlight-container pdf-page-frame"
                data-testid={`pdf-page-frame-${page}`}
                data-rotation={rotation}
                style={pageFrameStyle(page)}
              >
                {!isLoaded && !hasFailed && (
                  <div className="pdf-page-skeleton" aria-label={`Loading page ${page}...`} />
                )}
                {hasFailed && (
                  <p className="pdf-preview-error" role="status">
                    PDF preview unavailable for page {page}. The stored PDF file may be missing or unavailable.
                  </p>
                )}
                <div className="pdf-page-layer" style={pageLayerStyle(page)}>
                  <img
                    alt={`PDF page ${page} preview`}
                    src={documentPreviewPageUrl(document.id, page)}
                    style={imageStyle(isLoaded && !hasFailed)}
                    onLoad={(e) => handleImageLoad(page, e)}
                    onError={() => handleImageError(page)}
                  />
                  {showHighlight && (
                    <div
                      className="pdf-highlight-overlay"
                      style={bboxToPercent(
                        highlightLocation!.bbox!,
                        highlightLocation!.page_width!,
                        highlightLocation!.page_height!,
                      )}
                      aria-hidden="true"
                    />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <dialog
        ref={dialogRef}
        className="pdf-modal"
        onClick={handleDialogBackdropClick}
        aria-label={`Full PDF preview: ${document.filename}`}
      >
        <div className="pdf-modal__header">
          <span className="pdf-modal__title" title={document.filename}>
            {document.filename}
          </span>
          <button
            type="button"
            className="button button--ghost pdf-modal__close"
            onClick={() => setPdfModalOpen(false)}
            aria-label="Close PDF preview"
          >
            Close
          </button>
        </div>
        {pdfModalOpen && (
          <iframe
            src={documentPreviewUrl(document.id)}
            className="pdf-modal__frame"
            title={`Full PDF: ${document.filename}`}
          />
        )}
      </dialog>
    </section>
  );
}

function pageCountFromDocument(document: BundleDocument): number {
  const pageCount = document.metadata?.diagnostics?.page_count;
  return typeof pageCount === 'number' && pageCount > 0 ? pageCount : 1;
}

function percent(value: number): string {
  const rounded = Number(value.toFixed(2));
  return `${rounded}%`;
}
