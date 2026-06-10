export function debugLog(event: string, details: Record<string, unknown> = {}) {
  if (import.meta.env.VITE_DEBUG_LOGS !== 'true') {
    return;
  }
  console.debug(`[order-assurance] ${event}`, details);
}
