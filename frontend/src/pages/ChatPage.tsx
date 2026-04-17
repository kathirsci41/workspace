import { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Send, Loader2, MessageSquare, X } from 'lucide-react';
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

// Matches PO-style references: PO-2024-123, PO/24/001, PO2024001, etc.
const PO_PATTERN = /\b(PO[-/]?[\w/-]+)/gi;

function renderMessageText(text: string): React.ReactNode {
  const parts = text.split(PO_PATTERN);
  return parts.map((part, i) => {
    if (i % 2 === 1) {
      // Odd indexes are the captured PO references
      return (
        <Link
          key={i}
          to={`/purchase-orders?search=${encodeURIComponent(part)}`}
          className="underline font-medium hover:opacity-80"
        >
          {part}
        </Link>
      );
    }
    return part;
  });
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';
  return (
    <div className={clsx('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={clsx(
          'max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words',
          isUser
            ? 'bg-blue-600 text-white rounded-br-sm'
            : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm'
        )}
      >
        {isUser ? msg.text : renderMessageText(msg.text)}
        {msg.streaming && (
          <span className="inline-block w-1.5 h-3.5 bg-gray-400 ml-0.5 animate-pulse rounded-sm align-text-bottom" />
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

  // Fetch recent POs for context selector
  useEffect(() => {
    getPurchaseOrders(1, 50)
      .then(res => setPoList(res.items))
      .catch(() => {});
  }, []);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Cleanup SSE on unmount
  useEffect(() => () => { cleanupRef.current?.(); }, []);

  const filteredPos = poSearch
    ? poList.filter(po =>
        po.po_number.toLowerCase().includes(poSearch.toLowerCase()) ||
        (po.customer_name ?? '').toLowerCase().includes(poSearch.toLowerCase())
      )
    : poList.slice(0, 8);

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
          <MessageSquare size={20} className="text-blue-600" />
          <h1 className="text-lg font-semibold text-gray-800">Assistant</h1>
        </div>

        {/* PO Context selector */}
        <div className="relative">
          {selectedPo ? (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
              <span className="font-medium">{selectedPo.po_number}</span>
              <button
                onClick={() => setSelectedPo(null)}
                className="hover:text-blue-900"
                title="Remove PO context"
              >
                <X size={14} />
              </button>
            </div>
          ) : (
            <div>
              <button
                onClick={() => setShowPoDropdown(v => !v)}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50"
              >
                + Add PO context
              </button>
              {showPoDropdown && (
                <div className="absolute right-0 mt-1 w-72 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
                  <div className="p-2 border-b">
                    <input
                      autoFocus
                      type="text"
                      placeholder="Search PO number or customer…"
                      value={poSearch}
                      onChange={e => setPoSearch(e.target.value)}
                      className="w-full text-sm px-2 py-1.5 border border-gray-200 rounded outline-none focus:border-blue-400"
                    />
                  </div>
                  <ul className="max-h-48 overflow-y-auto py-1">
                    {filteredPos.length === 0 && (
                      <li className="px-3 py-2 text-sm text-gray-400">No orders found</li>
                    )}
                    {filteredPos.map(po => (
                      <li key={po.id}>
                        <button
                          className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50"
                          onClick={() => {
                            setSelectedPo(po);
                            setShowPoDropdown(false);
                            setPoSearch('');
                          }}
                        >
                          <div className="font-medium text-gray-800">{po.po_number}</div>
                          {po.customer_name && (
                            <div className="text-xs text-gray-400">{po.customer_name}</div>
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
              className="px-3 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-full transition-colors disabled:opacity-50"
            >
              {chip}
            </button>
          ))}
        </div>
      )}

      {/* Input area */}
      <form onSubmit={handleSubmit} className="mt-2 flex items-end gap-2 border-t pt-3">
        <textarea
          ref={inputRef}
          rows={1}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder={selectedPo ? `Ask about ${selectedPo.po_number}…` : 'Type your question…'}
          className={clsx(
            'flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'disabled:bg-gray-50 disabled:text-gray-400',
            'max-h-32 overflow-y-auto'
          )}
          style={{ minHeight: '42px' }}
        />
        <button
          type="submit"
          disabled={!input.trim() || isStreaming}
          className={clsx(
            'flex items-center justify-center w-10 h-10 rounded-xl transition-colors shrink-0',
            input.trim() && !isStreaming
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'
          )}
        >
          {isStreaming ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </form>
    </div>
  );
}
