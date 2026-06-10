import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { exportVerificationReport } from './export';

describe('exportVerificationReport', () => {
  let clickedLink: HTMLAnchorElement | null = null;

  beforeEach(() => {
    clickedLink = null;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(new Blob(['xlsx']), {
          status: 200,
          headers: {
            'Content-Disposition': 'attachment; filename="panimalar-report.xlsx"',
          },
        }),
      ),
    );
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:report'),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function click(this: HTMLAnchorElement) {
      clickedLink = this;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('uses the server-provided Content-Disposition filename', async () => {
    await exportVerificationReport('bundle-1');

    expect(clickedLink?.download).toBe('panimalar-report.xlsx');
  });
});
