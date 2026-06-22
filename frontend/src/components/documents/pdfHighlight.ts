import type { FieldLocation } from '../../types/api';

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
