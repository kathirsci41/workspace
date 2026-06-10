import { describe, expect, it } from 'vitest';
import { apiUrl, normalizeApiBaseUrl } from './client';

describe('API URL construction', () => {
  it.each([
    ['http://127.0.0.1:8100/api', 'http://127.0.0.1:8100/api'],
    ['http://127.0.0.1:8100/api/', 'http://127.0.0.1:8100/api'],
    ['http://127.0.0.1:8100', 'http://127.0.0.1:8100/api'],
    ['/api', '/api'],
    ['/api/', '/api'],
  ])('normalizes %s to %s', (input, expected) => {
    expect(normalizeApiBaseUrl(input)).toBe(expected);
  });

  it('joins API paths without duplicating the api prefix', () => {
    expect(apiUrl('/bundles', '/api')).toBe('/api/bundles');
    expect(apiUrl('/api/bundles', '/api')).toBe('/api/bundles');
    expect(apiUrl('documents/doc-1', 'http://127.0.0.1:8100/api/')).toBe(
      'http://127.0.0.1:8100/api/documents/doc-1',
    );
  });
});
