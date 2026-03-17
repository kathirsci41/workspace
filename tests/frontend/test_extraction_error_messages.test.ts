/**
 * Tests for friendlyExtractionError utility.
 * Covers all error categories and edge cases.
 */
import { describe, it, expect } from 'vitest';
import { friendlyExtractionError } from '../../frontend/src/utils/extractionErrors';

const SERVICE_MSG = 'Extraction service unavailable. Check endpoint or use Manual Entry.';
const NO_DATA_MSG = 'No data could be extracted from this document. Use Manual Entry.';
const DEFAULT_MSG  = 'Extraction failed';

describe('friendlyExtractionError — null/empty inputs', () => {
  it('returns default for null',      () => expect(friendlyExtractionError(null)).toBe(DEFAULT_MSG));
  it('returns default for undefined', () => expect(friendlyExtractionError(undefined)).toBe(DEFAULT_MSG));
  it('returns default for ""',        () => expect(friendlyExtractionError('')).toBe(DEFAULT_MSG));
});

describe('friendlyExtractionError — service unavailable', () => {
  it('maps HTTP 404 unreachable error', () =>
    expect(friendlyExtractionError(
      'Extraction service unreachable (HTTP 404) — check OCR_BASE_URL in .env'
    )).toBe(SERVICE_MSG));

  it('maps offline error', () =>
    expect(friendlyExtractionError(
      'Extraction service offline — could not connect to the extraction server.'
    )).toBe(SERVICE_MSG));

  it('maps getaddrinfo (DNS failure)', () =>
    expect(friendlyExtractionError(
      'GLM-OCR generate call failed after 3 retries: [Errno 11001] getaddrinfo failed'
    )).toBe(SERVICE_MSG));

  it('maps ConnectError', () =>
    expect(friendlyExtractionError(
      'ConnectError: [Errno 111] Connection refused'
    )).toBe(SERVICE_MSG));

  it('maps connection timeout', () =>
    expect(friendlyExtractionError(
      'connect timeout after 120s'
    )).toBe(SERVICE_MSG));
});

describe('friendlyExtractionError — no data extracted', () => {
  it('maps new "returned no data" message', () =>
    expect(friendlyExtractionError(
      'Extraction service returned no data — all pages failed or were empty'
    )).toBe(NO_DATA_MSG));

  it('maps "returned empty" message', () =>
    expect(friendlyExtractionError(
      'Extraction produced no data — all pages returned empty output'
    )).toBe(NO_DATA_MSG));

  it('maps legacy "no extractable fields" message', () =>
    expect(friendlyExtractionError(
      'Two-layer OCR produced no extractable fields — all pages failed or returned empty'
    )).toBe(NO_DATA_MSG));

  it('maps "no data" substring', () =>
    expect(friendlyExtractionError('no data found in document')).toBe(NO_DATA_MSG));
});

describe('friendlyExtractionError — pass-through', () => {
  it('passes unknown error unchanged', () => {
    const raw = 'Unexpected internal error: division by zero';
    expect(friendlyExtractionError(raw)).toBe(raw);
  });

  it('passes validation error unchanged', () => {
    const raw = 'Field validation failed: po_number is required';
    expect(friendlyExtractionError(raw)).toBe(raw);
  });
});