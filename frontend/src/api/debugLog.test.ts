import { afterEach, describe, expect, it, vi } from 'vitest';
import { debugLog } from './debugLog';

describe('debugLog', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('logs only when VITE_DEBUG_LOGS is enabled', () => {
    const spy = vi.spyOn(console, 'debug').mockImplementation(() => undefined);

    debugLog('upload_started', { document_id: 'doc-1' });
    expect(spy).not.toHaveBeenCalled();

    vi.stubEnv('VITE_DEBUG_LOGS', 'true');
    debugLog('upload_started', { document_id: 'doc-1' });

    expect(spy).toHaveBeenCalledWith('[order-assurance] upload_started', { document_id: 'doc-1' });
  });
});
