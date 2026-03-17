/**
 * Maps a raw last_error string from the backend to an operator-friendly message.
 */
export function friendlyExtractionError(raw: string | null | undefined): string {
  if (!raw) return 'Extraction failed';
  const msg = raw.toLowerCase();
  if (
    msg.includes('unreachable') ||
    msg.includes('offline') ||
    msg.includes('getaddrinfo') ||
    msg.includes('connect')
  )
    return 'Extraction service unavailable. Check endpoint or use Manual Entry.';
  if (
    msg.includes('no data') ||
    msg.includes('no extractable') ||
    msg.includes('returned no data') ||
    msg.includes('returned empty') ||
    msg.includes('produced no fields') ||
    msg.includes('produced no data')
  )
    return 'No data could be extracted from this document. Use Manual Entry.';
  return raw;
}