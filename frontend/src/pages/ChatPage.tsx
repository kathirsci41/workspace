import { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Send, Square, MessageSquare, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { streamMessage } from '@/api/chat';
import { getPurchaseOrders } from '@/api/purchaseOrders';
import type { PurchaseOrder } from '@/types';
import clsx from 'clsx';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
}

const QUICK_CHIPS = [
  'What needs attention today?',
  'Find missing documents',
  'Summarise billing status',
  'What should I do next?',
];

const PO_PATTERN = /\b(PO[-/]?[\w/-]+)/gi;

function linkifyText(text: string): React.ReactNode[] {
  const parts = text.split(PO_PATTERN);
  return parts.map((part, i) => {
    if (i % 2 === 1) {
      return (
        <Link
          key={i}
          to={`/purchase-orders?search=${encodeURIComponent(part)}`}
          className="font-mono underline font-medium hover:opacity-80"
        >
          {part}
        </Link>
      );
    }
    return part;
  });
}

const mdComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{linkifyText(String(children))}</p>,
  ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  code: ({ children }) => (
    <code className="font-mono bg-veil/60 text-ink px-1 py-0.5 rounded text-xs">{children}</code>
  ),
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  a: ({ href, children }) => (
    <a href={href} className="underline hover:opacity-80">{children}</a>
  ),
};

function TypingDots() {
  return (
    <span className="flex items-center gap-1 h-5 px-1">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-ink/40"
          style={{ animation: `typing-bounce 1.2s ease-in-out ${i * 0.15}s infinite` }}
        />
      ))}
    </span>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';
  return (
    <div className={clsx('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={clsx(
          'max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-relaxed break-words',
          isUser
            ? 'bg-accent text-white rounded-br-sm'
            : 'bg-white border border-veil text-ink rounded-bl-sm shadow-sm'
        )}
      >
        {isUser ? (
          msg.text
        ) : msg.streaming && msg.text === '' ? (
          <TypingDots />
        ) : (
          <>
            <ReactMarkdown components={mdComponents}>{msg.text}</ReactMarkdown>
            {msg.streaming && (
              <span className="inline-block w-1.5 h-3.5 bg-ink/30 ml-0.5 animate-pulse rounded-sm align-text-bottom" />
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { id: 'welcome', role: 'assistant', text: 'Hello! I can help you with order status, missing documents, billing queries, and more. You can attach a specific order using the PO selector above, or ask me a general question.' },
  ]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedPo, setSelectedPo] = useState<PurchaseOrder | null>(null);
  const [poList, setPoList] = useState<PurchaseOrder[]>([]);
  const [poSearch, setPoSearch] = useState('');
  const [showPoDropdown, setShowPoDropdown] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    getPurchaseOrders(1, 50)
      .then(res => setPoList(res.items))
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => () => { cleanupRef.current?.(); }, []);

  // Auto-resize textarea up to ~5 lines
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 140) + 'px';
  }, [input]);

  const filteredPos = poSearch
    ? poList.filter(po =>
        po.po_number.toLowerCase().includes(poSearch.toLowerCase()) ||
        (po.customer_name ?? '').toLowerCase().includes(poSearch.toLowerCase())
      )
    : poList.slice(0, 8);

  const stopStreaming = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setMessages(prev =>
      prev.map(m => m.streaming ? { ...m, streaming: false } : m)
    );
    setIsStreaming(false);
  }, []);

  const sendUserMessage = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;

    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', text: trimmed };
    const assistantId = crypto.randomUUID();
    const assistantMsg: Message = { id: assistantId, role: 'assistant', text: '', streaming: true };

    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setInput('');
    setIsStreaming(true);

    cleanupRef.current = streamMessage(
      trimmed,
      selectedPo?.id ?? null,
      (chunk) => {
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId ? { ...m, text: m.text + chunk } : m
          )
        );
      },
      () => {
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId ? { ...m, streaming: false } : m
          )
        );
        setIsStreaming(false);
        cleanupRef.current = null;
      },
      () => {
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId
              ? { ...m, text: m.text || 'Unable to reach the assistant. Check that Ollama is running.', streaming: false }
              : m
          )
        );
        setIsStreaming(false);
        cleanupRef.current = null;
      },
    );
  }, [isStreaming, selectedPo]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendUserMessage(input);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendUserMessage(input);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <MessageSquare size={20} className="text-accent" />
          <h1 className="text-lg font-semibold font-display tracking-tight text-ink">Assistant</h1>
        </div>

        {/* PO Context selector */}
        <div className="relative">
          {selectedPo ? (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-accent/10 border border-accent/30 rounded-lg text-sm text-accent">
              <span className="font-mono font-medium">{selectedPo.po_number}</span>
              <button
                onClick={() => setSelectedPo(null)}
                className="hover:text-accent/70"
                title="Remove PO context"
              >
                <X size={14} />
              </button>
            </div>
          ) : (
            <div>
              <button
                onClick={() => setShowPoDropdown(v => !v)}
                className="px-3 py-1.5 text-sm border border-veil rounded-lg text-ink/60 hover:bg-veil/40 transition-colors"
              >
                + Add PO context
              </button>
              {showPoDropdown && (
                <div className="absolute right-0 mt-1 w-72 bg-white border border-veil rounded-lg shadow-lg z-10">
                  <div className="p-2 border-b border-veil">
                    <input
                      autoFocus
                      type="text"
                      placeholder="Search PO number or customer…"
                      value={poSearch}
                      onChange={e => setPoSearch(e.target.value)}
                      className="w-full text-sm px-2 py-1.5 border border-veil rounded outline-none focus:border-accent"
                    />
                  </div>
                  <ul className="max-h-48 overflow-y-auto py-1">
                    {filteredPos.length === 0 && (
                      <li className="px-3 py-2 text-sm text-ink/40">No orders found</li>
                    )}
                    {filteredPos.map(po => (
                      <li key={po.id}>
                        <button
                          className="w-full text-left px-3 py-2 text-sm hover:bg-paper"
                          onClick={() => {
                            setSelectedPo(po);
                            setShowPoDropdown(false);
                            setPoSearch('');
                          }}
                        >
                          <div className="font-mono font-medium text-ink">{po.po_number}</div>
                          {po.customer_name && (
                            <div className="text-xs text-ink/40">{po.customer_name}</div>
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1 pb-2">
        {messages.map(msg => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Quick chips */}
      {messages.length <= 1 && (
        <div className="flex flex-wrap gap-2 py-2">
          {QUICK_CHIPS.map(chip => (
            <button
              key={chip}
              onClick={() => sendUserMessage(chip)}
              disabled={isStreaming}
              className="px-3 py-1.5 text-xs bg-veil/60 hover:bg-veil text-ink/70 rounded-full transition-colors disabled:opacity-50"
            >
              {chip}
            </button>
          ))}
        </div>
      )}

      {/* Input area */}
      <form onSubmit={handleSubmit} className="mt-2 flex items-end gap-2 border-t border-veil pt-3">
        <textarea
          ref={inputRef}
          rows={1}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder={selectedPo ? `Ask about ${selectedPo.po_number}…` : 'Type your question…'}
          className={clsx(
            'flex-1 resize-none rounded-xl border border-veil px-4 py-2.5 text-sm bg-white text-ink',
            'focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent',
            'disabled:bg-paper disabled:text-ink/40',
            'overflow-y-auto [&::-webkit-scrollbar]:hidden'
          )}
        />
        {isStreaming ? (
          <button
            type="button"
            onClick={stopStreaming}
            className="flex items-center justify-center w-10 h-10 rounded-xl bg-signal text-white hover:bg-signal/90 transition-all shrink-0"
            title="Stop generating"
          >
            <Square size={16} />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className={clsx(
              'flex items-center justify-center w-10 h-10 rounded-xl transition-all shrink-0',
              input.trim()
                ? 'bg-accent text-white hover:bg-accent/90'
                : 'bg-veil text-ink/30 cursor-not-allowed'
            )}
          >
            <Send size={18} />
          </button>
        )}
      </form>
    </div>
  );
}
