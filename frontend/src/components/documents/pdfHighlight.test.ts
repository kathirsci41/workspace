import { fireEvent, render, screen } from '@testing-library/react';
import { createElement } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { bboxToPercent, canHighlight, isScannedNoHighlight } from './pdfHighlight';
import { PdfPreviewPane } from './PdfPreviewPane';
import type { BundleDocument, FieldLocation } from '../../types/api';

const baseDocument: BundleDocument = {
  id: 'doc-1',
  order_bundle_id: 'bundle-1',
  document_type: 'COMPANY_INVOICE',
  filename: 'invoice.pdf',
  content_type: 'application/pdf',
  status: 'PENDING_REVIEW',
  last_error: null,
  created_at: '2026-02-13T09:00:00Z',
  updated_at: '2026-02-13T09:10:00Z',
  metadata: {
    id: 'meta-1',
    document_id: 'doc-1',
    status: 'EXTRACTED',
    extracted_data: { invoice_no: '1ITR2526001878' },
    diagnostics: { page_count: 1 },
    primary_ref_no: '1ITR2526001878',
    po_ref_no: null,
    last_error: null,
  },
};

const digitalLocation: FieldLocation = {
  page: 1,
  bbox: [10, 20, 120, 42],
  page_width: 500,
  page_height: 700,
  evidence_text: 'Invoice No: 1ITR2526001878',
  source: 'digital_text',
  confidence: 0.92,
};

const scannedLocation: FieldLocation = {
  page: 1,
  bbox: null,
  page_width: null,
  page_height: null,
  evidence_text: null,
  source: 'ocr',
  confidence: 0.85,
};

describe('bboxToPercent', () => {
  it('converts bbox to percentage coordinates relative to page dimensions', () => {
    const result = bboxToPercent([10, 20, 110, 70], 500, 700);
    expect(result).toEqual({
      left: `${((10 / 500) * 100).toFixed(2)}%`,
      top: `${((20 / 700) * 100).toFixed(2)}%`,
      width: `${((100 / 500) * 100).toFixed(2)}%`,
      height: `${((50 / 700) * 100).toFixed(2)}%`,
    });
  });
});

describe('canHighlight', () => {
  it('returns true when bbox and page dimensions are present', () => {
    expect(canHighlight(digitalLocation)).toBe(true);
  });

  it('returns false when bbox is null', () => {
    expect(canHighlight(scannedLocation)).toBe(false);
  });

  it('returns false when location is null', () => {
    expect(canHighlight(null)).toBe(false);
  });
});

describe('isScannedNoHighlight', () => {
  it('returns true for scanned/ocr locations with no bbox', () => {
    expect(isScannedNoHighlight(scannedLocation)).toBe(true);
  });

  it('returns false for digital locations with bbox', () => {
    expect(isScannedNoHighlight(digitalLocation)).toBe(false);
  });

  it('returns false when location is null', () => {
    expect(isScannedNoHighlight(null)).toBe(false);
  });
});

describe('PdfPreviewPane component', () => {
  it('renders highlight overlay when highlightLocation has bbox and page matches', () => {
    render(
      createElement(PdfPreviewPane, {
        document: baseDocument,
        selectedPage: 1,
        onPageChange: vi.fn(),
        highlightLocation: digitalLocation,
      }),
    );
    expect(document.querySelector('.pdf-highlight-overlay')).not.toBeNull();
    expect(document.querySelector('.pdf-highlight-unavailable')).toBeNull();
  });

  it('does not render overlay when highlighted page does not match selected page', () => {
    const otherPageLocation: FieldLocation = { ...digitalLocation, page: 2 };
    render(
      createElement(PdfPreviewPane, {
        document: baseDocument,
        selectedPage: 1,
        onPageChange: vi.fn(),
        highlightLocation: otherPageLocation,
      }),
    );
    expect(document.querySelector('.pdf-highlight-overlay')).toBeNull();
    expect(document.querySelector('.pdf-highlight-unavailable')).toBeNull();
  });

  it('renders scanned OCR unavailable message when bbox is null', () => {
    render(
      createElement(PdfPreviewPane, {
        document: baseDocument,
        selectedPage: 1,
        onPageChange: vi.fn(),
        highlightLocation: scannedLocation,
      }),
    );
    expect(document.querySelector('.pdf-highlight-overlay')).toBeNull();
    expect(screen.getByRole('status')).toHaveTextContent(
      'Highlight unavailable — field was extracted from scanned OCR text without position data.',
    );
  });

  it('does not render overlay or message when no highlightLocation', () => {
    render(
      createElement(PdfPreviewPane, {
        document: baseDocument,
        selectedPage: 1,
        onPageChange: vi.fn(),
      }),
    );
    expect(document.querySelector('.pdf-highlight-overlay')).toBeNull();
    expect(document.querySelector('.pdf-highlight-unavailable')).toBeNull();
  });

  it('shows a preview-unavailable message when a page image fails to load', () => {
    render(
      createElement(PdfPreviewPane, {
        document: baseDocument,
        selectedPage: 1,
      }),
    );

    fireEvent.error(screen.getByAltText('PDF page 1 preview'));

    expect(screen.getByRole('status')).toHaveTextContent(
      'PDF preview unavailable for page 1. The stored PDF file may be missing or unavailable.',
    );
    expect(screen.getByAltText('PDF page 1 preview')).not.toBeVisible();
  });
});

describe('PdfPreviewPane rotation controls', () => {
  function renderPane(highlightLocation?: FieldLocation | null) {
    return render(
      createElement(PdfPreviewPane, {
        document: baseDocument,
        selectedPage: 1,
        highlightLocation,
      }),
    );
  }

  it('renders Rotate Left, Rotate Right, and Reset controls', () => {
    renderPane();
    expect(screen.getByRole('button', { name: 'Rotate left' })).not.toBeNull();
    expect(screen.getByRole('button', { name: 'Rotate right' })).not.toBeNull();
    // Reset only shown when rotation != 0; not visible at start
    expect(screen.queryByRole('button', { name: 'Reset rotation' })).toBeNull();
  });

  it('shows Reset button and 90° label after one Rotate Right click', () => {
    renderPane();
    fireEvent.click(screen.getByRole('button', { name: 'Rotate right' }));
    expect(screen.getByRole('button', { name: 'Reset rotation' })).not.toBeNull();
    expect(screen.getByLabelText('Current rotation: 90°')).not.toBeNull();
  });

  it('cycles Rotate Right through 0 → 90 → 180 → 270 → 0', () => {
    renderPane();
    const rotateRight = screen.getByRole('button', { name: 'Rotate right' });
    fireEvent.click(rotateRight);
    expect(screen.getByLabelText('Current rotation: 90°')).not.toBeNull();
    fireEvent.click(rotateRight);
    expect(screen.getByLabelText('Current rotation: 180°')).not.toBeNull();
    fireEvent.click(rotateRight);
    expect(screen.getByLabelText('Current rotation: 270°')).not.toBeNull();
    fireEvent.click(rotateRight);
    expect(screen.getByLabelText('Current rotation: 0°')).not.toBeNull();
  });

  it('Rotate Left from 0 goes to 270', () => {
    renderPane();
    fireEvent.click(screen.getByRole('button', { name: 'Rotate left' }));
    expect(screen.getByLabelText('Current rotation: 270°')).not.toBeNull();
  });

  it('Reset returns rotation to 0', () => {
    renderPane();
    fireEvent.click(screen.getByRole('button', { name: 'Rotate right' }));
    fireEvent.click(screen.getByRole('button', { name: 'Rotate right' }));
    expect(screen.getByLabelText('Current rotation: 180°')).not.toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Reset rotation' }));
    expect(screen.getByLabelText('Current rotation: 0°')).not.toBeNull();
    expect(screen.queryByRole('button', { name: 'Reset rotation' })).toBeNull();
  });

  it('suppresses highlight overlay when rotated, shows warning instead', () => {
    renderPane(digitalLocation);
    // At 0° highlight overlay should be visible
    expect(document.querySelector('.pdf-highlight-overlay')).not.toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Rotate right' }));
    // After rotation, overlay should be gone and warning shown
    expect(document.querySelector('.pdf-highlight-overlay')).toBeNull();
    expect(screen.getByRole('status')).toHaveTextContent(
      'Highlight position unavailable while rotated',
    );
  });

  it('restores highlight overlay when rotation is reset to 0', () => {
    renderPane(digitalLocation);
    fireEvent.click(screen.getByRole('button', { name: 'Rotate right' }));
    expect(document.querySelector('.pdf-highlight-overlay')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Reset rotation' }));
    expect(document.querySelector('.pdf-highlight-overlay')).not.toBeNull();
    expect(document.querySelector('.pdf-highlight-unavailable')).toBeNull();
  });

  it('swaps the reserved page layout dimensions at 90 degrees', () => {
    renderPane();
    const image = screen.getByAltText('PDF page 1 preview');
    Object.defineProperty(image, 'naturalWidth', { value: 500, configurable: true });
    Object.defineProperty(image, 'naturalHeight', { value: 700, configurable: true });
    fireEvent.load(image);

    fireEvent.click(screen.getByRole('button', { name: 'Rotate right' }));

    const frame = screen.getByTestId('pdf-page-frame-1');
    expect(frame).toHaveStyle({ width: '140%' });
    expect(frame).toHaveStyle({ aspectRatio: '700 / 500' });
    expect(frame).toHaveAttribute('data-rotation', '90');
  });

  it('reset returns the reserved page layout dimensions to normal', () => {
    renderPane();
    const image = screen.getByAltText('PDF page 1 preview');
    Object.defineProperty(image, 'naturalWidth', { value: 500, configurable: true });
    Object.defineProperty(image, 'naturalHeight', { value: 700, configurable: true });
    fireEvent.load(image);

    fireEvent.click(screen.getByRole('button', { name: 'Rotate right' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reset rotation' }));

    const frame = screen.getByTestId('pdf-page-frame-1');
    expect(frame).toHaveStyle({ width: '100%' });
    expect(frame).toHaveStyle({ aspectRatio: '500 / 700' });
    expect(frame).toHaveAttribute('data-rotation', '0');
  });

  it('renders manual OCR rotation controls and can use the current preview rotation', () => {
    const onOcrRotationPreferenceChange = vi.fn();
    render(
      createElement(PdfPreviewPane, {
        document: baseDocument,
        selectedPage: 1,
        ocrRotationPreference: 'auto',
        onOcrRotationPreferenceChange,
      }),
    );

    expect(screen.getByLabelText('OCR rotation')).toHaveValue('auto');
    fireEvent.change(screen.getByLabelText('OCR rotation'), { target: { value: '180' } });
    expect(onOcrRotationPreferenceChange).toHaveBeenCalledWith(180);

    fireEvent.click(screen.getByRole('button', { name: 'Rotate right' }));
    fireEvent.click(screen.getByRole('button', { name: 'Use current preview rotation for OCR' }));
    expect(onOcrRotationPreferenceChange).toHaveBeenLastCalledWith(90);
  });
});

describe('ExtractedFieldsPanel onFieldClick', () => {
  it('calls onFieldClick with field name when clickable field label is activated', async () => {
    const { ExtractedFieldsPanel } = await import('../extraction/ExtractedFieldsPanel');
    const onClick = vi.fn();
    const docWithFields: BundleDocument = {
      ...baseDocument,
      metadata: {
        ...baseDocument.metadata!,
        extracted_data: { invoice_no: '1ITR2526001878' },
        field_locations: {
          invoice_no: {
            page: 1,
            bbox: [10, 20, 120, 42],
            page_width: 500,
            page_height: 700,
            evidence_text: 'Invoice No',
            source: 'digital_text',
            confidence: 0.9,
          },
        },
      },
    };

    render(
      createElement(ExtractedFieldsPanel, {
        document: docWithFields,
        onEdit: vi.fn(),
        onFieldClick: onClick,
      }),
    );

    const clickableField = document.querySelector('[aria-label^="Jump to"]');
    expect(clickableField).not.toBeNull();
    fireEvent.click(clickableField!);
    expect(onClick).toHaveBeenCalledWith('invoice_no');
  });
});
