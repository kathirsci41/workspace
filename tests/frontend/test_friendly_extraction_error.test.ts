import { describe, it, expect } from 'vitest';
import { friendlyExtractionError } from '../../frontend/src/utils/extractionErrors';

describe('friendlyExtractionError', () => {

  // ── Null / empty inputs ──────────────────────────────────────────────────
  it('returns default message for null', () => {
    expect(friendlyExtractionError(null)).toBe('Extraction failed');
  });

  it('returns default message for undefined', () => {
    expect(friendlyExtractionError(undefined)).toBe('Extraction failed');
  });

  it('returns default message for empty string', () => {
    expect(friendlyExtractionError('')).toBe('Extraction failed');
  });

  // ── Connection / service unavailable ────────────────────────────────────
  it('maps "unreachable" error to service unavailable message', () => {
    const raw = 'Extraction service unreachable (HTTP 404) — check OCR_BASE_URL in .env';
    expect(friendlyExtractionError(raw)).toBe(
      'Extraction service unavailable. Check endpoint or use Manual Entry.'
    );
  });

  it('maps "offline" error to service unavailable message', () => {
    const raw = 'Extraction service offline — could not connect to the extraction server.';
    expect(friendlyExtractionError(raw)).toBe(
      'Extraction service unavailable. Check endpoint or use Manual Entry.'
    );
  });

  it('maps "getaddrinfo" (DNS failure) to service unavailable message', () => {
    const raw = 'GLM-OCR generate call failed after 3 retries: [Errno 11001] getaddrinfo failed';
    expect(friendlyExtractionError(raw)).toBe(
      'Extraction service unavailable. Check endpoint or use Manual Entry.'
    );
  });

  it('maps ConnectionError to service unavailable message', () => {
    const raw = 'ConnectError: [Errno 111] Connection refused';
    expect(friendlyExtractionError(raw)).toBe(
      'Extraction service unavailable. Check endpoint or use Manual Entry.'
    );
  });

  // ── No data extracted ────────────────────────────────────────────────────
  it('maps new "returned no data" message to no-data message', () => {
    const raw = 'Extraction service returned no data — all pages failed or were empty';
    expect(friendlyExtractionError(raw)).toBe(
      'No data could be extracted from this document. Use Manual Entry.'
    );
  });

  it('maps "returned empty" message to no-data message', () => {
    const raw = 'Extraction produced no data — all pages returned empty output';
    expect(friendlyExtractionError(raw)).toBe(
      'No data could be extracted from this document. Use Manual Entry.'
    );
  });

  it('maps "no extractable" (legacy) to no-data message', () => {
    const raw = 'Two-layer OCR produced no extractable fields — all pages failed or returned empty';
    expect(friendlyExtractionError(raw)).toBe(
      'No data could be extracted from this document. Use Manual Entry.'
    );
  });

  // ── Unknown errors pass through unchanged ────────────────────────────────
  it('passes through unknown error strings unchanged', () => {
    const raw = 'Unexpected internal error: division by zero';
    expect(friendlyExtractionError(raw)).toBe(raw);
  });

});