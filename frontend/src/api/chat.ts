/**
 * Chat API utilities.
 * streamMessage opens a native EventSource for SSE — no axios (it doesn't support streaming).
 */

export interface ChatChunk {
  chunk: string;
  done: boolean;
}

/**
 * Open an SSE stream to the chat endpoint.
 * onChunk is called for every partial response.
 * onDone is called when the stream completes.
 * Returns a cleanup function that closes the EventSource.
 */
export function streamMessage(
  message: string,
  poId: string | null,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError?: (err: Event) => void,
): () => void {
  const params = new URLSearchParams({ message });
  if (poId) params.set('po_id', poId);

  const url = `/api/v1/chat/stream?${params.toString()}`;
  const es = new EventSource(url);

  es.onmessage = (event) => {
    try {
      const data: ChatChunk = JSON.parse(event.data);
      if (data.done) {
        es.close();
        onDone();
      } else if (data.chunk) {
        onChunk(data.chunk);
      }
    } catch {
      // ignore malformed chunks
    }
  };

  es.onerror = (err) => {
    es.close();
    onError?.(err);
    onDone();
  };

  return () => es.close();
}
