import { useState, useRef, useCallback, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { ZoomIn, ZoomOut, Maximize2, RotateCw } from 'lucide-react';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3.0;
const BTN_STEP = 0.15;

interface Props {
  url: string;
}

export default function PDFViewer({ url }: Props) {
  const [numPages, setNumPages] = useState(0);
  const [zoom, setZoom] = useState(1.0);          // 1.0 = fit-to-width
  const [rotate, setRotate] = useState(0);         // 0 | 90 | 180 | 270
  const [containerWidth, setContainerWidth] = useState(0);
  const [error, setError] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const isHovered = useRef(false);
  const lastPinchDist = useRef<number | null>(null);

  const clamp = (z: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));

  const zoomIn    = () => setZoom(z => clamp(z + BTN_STEP));
  const zoomOut   = () => setZoom(z => clamp(z - BTN_STEP));
  const fitPage   = () => setZoom(1.0);
  const rotateCw  = () => setRotate(r => (r + 90) % 360);

  // Reset rotation when a different document is loaded
  useEffect(() => { setRotate(0); }, [url]);

  // Measure container width → used as base page width at zoom=1.0
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect.width ?? 0;
      if (w > 0) setContainerWidth(w - 32); // leave 16px padding each side
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Ctrl+scroll inside container → zoom PDF (proportional, low sensitivity)
  const onWheel = useCallback((e: WheelEvent) => {
    if (!e.ctrlKey) return;
    e.preventDefault();
    e.stopPropagation();
    setZoom(z => clamp(z - e.deltaY * 0.003));
  }, []);

  // Window-level intercept: block browser page zoom when mouse is over PDF panel
  useEffect(() => {
    const guard = (e: WheelEvent) => {
      if (e.ctrlKey && isHovered.current) e.preventDefault();
    };
    window.addEventListener('wheel', guard, { passive: false });
    return () => window.removeEventListener('wheel', guard);
  }, []);

  // Pinch zoom (touch / touchpad two-finger)
  const onTouchMove = useCallback((e: TouchEvent) => {
    if (e.touches.length !== 2) return;
    e.preventDefault();
    const dx = e.touches[0].clientX - e.touches[1].clientX;
    const dy = e.touches[0].clientY - e.touches[1].clientY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (lastPinchDist.current !== null) {
      setZoom(z => clamp(z + (dist - lastPinchDist.current!) * 0.004));
    }
    lastPinchDist.current = dist;
  }, []);

  const onTouchEnd = useCallback(() => {
    lastPinchDist.current = null;
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.addEventListener('wheel', onWheel, { passive: false });
    el.addEventListener('touchmove', onTouchMove, { passive: false });
    el.addEventListener('touchend', onTouchEnd);
    return () => {
      el.removeEventListener('wheel', onWheel);
      el.removeEventListener('touchmove', onTouchMove);
      el.removeEventListener('touchend', onTouchEnd);
    };
  }, [onWheel, onTouchMove, onTouchEnd]);

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm">
        Failed to load PDF
      </div>
    );
  }

  // Page width = container width × zoom multiplier (fit-width at zoom=1.0)
  const pageWidth = containerWidth > 0 ? containerWidth * zoom : undefined;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-3 py-1.5 border-b border-gray-200 bg-gray-50 shrink-0">
        <button
          onClick={zoomOut}
          disabled={zoom <= MIN_ZOOM}
          className="p-1 rounded hover:bg-gray-200 disabled:opacity-40 transition-colors"
          title="Zoom out"
        >
          <ZoomOut size={15} />
        </button>
        <span className="text-xs text-gray-600 w-12 text-center select-none">
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={zoomIn}
          disabled={zoom >= MAX_ZOOM}
          className="p-1 rounded hover:bg-gray-200 disabled:opacity-40 transition-colors"
          title="Zoom in"
        >
          <ZoomIn size={15} />
        </button>
        <div className="w-px h-4 bg-gray-300 mx-1" />
        <button
          onClick={fitPage}
          className="p-1 rounded hover:bg-gray-200 transition-colors"
          title="Fit to width"
        >
          <Maximize2 size={15} />
        </button>
        <div className="w-px h-4 bg-gray-300 mx-1" />
        <button
          onClick={rotateCw}
          className="p-1 rounded hover:bg-gray-200 transition-colors"
          title="Rotate 90°"
        >
          <RotateCw size={15} />
        </button>
        {numPages > 1 && (
          <span className="ml-auto text-xs text-gray-500 select-none">
            {numPages} pages
          </span>
        )}
      </div>

      {/* PDF canvas */}
      <div
        ref={containerRef}
        onMouseEnter={() => { isHovered.current = true; }}
        onMouseLeave={() => { isHovered.current = false; }}
        className="flex-1 overflow-auto bg-gray-100 flex flex-col items-start py-4 px-4 gap-4"
      >
        <Document
          file={url}
          onLoadSuccess={({ numPages }) => setNumPages(numPages)}
          onLoadError={() => setError(true)}
          loading={
            <div className="flex items-center justify-center pt-16 text-gray-400 text-sm">
              Loading…
            </div>
          }
        >
          {Array.from({ length: numPages }, (_, i) => (
            <Page
              key={i + 1}
              pageNumber={i + 1}
              width={pageWidth}
              rotate={rotate}
              className="shadow-md"
              renderTextLayer={false}
              renderAnnotationLayer={false}
            />
          ))}
        </Document>
      </div>
    </div>
  );
}
