import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Search, Users, FileText, File, Loader2, ArrowRight } from 'lucide-react';
import { useSearch } from '@/hooks/useSearch';
import type { SearchResult } from '@/types';
import clsx from 'clsx';

export default function InlineSearch() {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Debounce: only search after 300ms of no typing
  const [debouncedQuery, setDebouncedQuery] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);

  const { data, isLoading } = useSearch(debouncedQuery);
  const results = data?.results ?? [];

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Open dropdown when results come in — suppress on /search (that page handles its own search)
  useEffect(() => {
    if (debouncedQuery.length >= 2 && pathname !== '/search') setOpen(true);
    setActiveIdx(-1);
  }, [debouncedQuery, data, pathname]);

  const handleResultClick = useCallback(
    (result: SearchResult) => {
      setOpen(false);
      setQuery('');
      switch (result.result_type) {
        case 'customer':
          navigate(`/purchase-orders?customer_id=${result.id}`);
          break;
        case 'purchase_order':
          navigate(`/purchase-orders/${result.id}`);
          break;
        case 'document':
          if (result.po_id) navigate(`/purchase-orders/${result.po_id}`);
          break;
      }
    },
    [navigate],
  );

  const goToFullSearch = useCallback(() => {
    if (query.trim()) {
      setOpen(false);
      setQuery('');
      navigate(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  }, [navigate, query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, results.length)); // last = "View all"
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIdx >= 0 && activeIdx < results.length) {
        handleResultClick(results[activeIdx]);
      } else {
        goToFullSearch();
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
      inputRef.current?.blur();
    }
  };

  const resultIcon = (type: string) => {
    switch (type) {
      case 'customer':
        return <Users size={16} className="text-blue-500 shrink-0" />;
      case 'purchase_order':
        return <FileText size={16} className="text-green-500 shrink-0" />;
      case 'document':
        return <File size={16} className="text-amber-500 shrink-0" />;
      default:
        return <File size={16} className="text-gray-400 shrink-0" />;
    }
  };

  const typeLabel = (r: SearchResult) => {
    if (r.result_type === 'document' && r.document_type) {
      return r.document_type.replace(/_/g, ' ');
    }
    return r.result_type.replace('_', ' ');
  };

  const showDropdown = open && debouncedQuery.length >= 2;

  return (
    <div ref={containerRef} className="relative flex-1 max-w-xl">
      <div className="relative">
        <Search
          size={18}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
        />
        <input
          ref={inputRef}
          type="text"
          placeholder="Search invoice, DC, PO, customer..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => {
            if (debouncedQuery.length >= 2 && pathname !== '/search') setOpen(true);
          }}
          onKeyDown={handleKeyDown}
          className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        {isLoading && (
          <Loader2
            size={16}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 animate-spin"
          />
        )}
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-xl shadow-xl border border-gray-200 overflow-hidden z-50 max-h-[420px] flex flex-col">
          {results.length === 0 && !isLoading && (
            <p className="px-4 py-6 text-sm text-gray-400 text-center">
              No results for &ldquo;{debouncedQuery}&rdquo;
            </p>
          )}

          {results.length > 0 && (
            <div className="overflow-y-auto divide-y divide-gray-100">
              {results.slice(0, 8).map((result, idx) => (
                <div
                  key={`${result.result_type}-${result.id}`}
                  onClick={() => handleResultClick(result)}
                  className={clsx(
                    'flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors',
                    activeIdx === idx
                      ? 'bg-blue-50'
                      : 'hover:bg-gray-50',
                  )}
                >
                  {resultIcon(result.result_type)}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      {result.display_name}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[11px] uppercase text-gray-400">
                        {typeLabel(result)}
                      </span>
                      {result.po_number && result.result_type === 'document' && (
                        <span className="text-[11px] text-gray-400">
                          PO: {result.po_number}
                        </span>
                      )}
                      {result.customer_name && result.result_type !== 'customer' && (
                        <span className="text-[11px] text-gray-400">
                          {result.customer_name}
                        </span>
                      )}
                    </div>
                  </div>
                  {result.confidence != null && (
                    <span
                      className={clsx(
                        'text-xs font-medium tabular-nums',
                        result.confidence >= 80
                          ? 'text-green-600'
                          : result.confidence >= 50
                            ? 'text-amber-600'
                            : 'text-red-500',
                      )}
                    >
                      {result.confidence}%
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Footer: View all */}
          {(results.length > 0 || (!isLoading && results.length === 0)) && (
            <div
              onClick={goToFullSearch}
              className={clsx(
                'flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-medium text-blue-600 border-t border-gray-100 cursor-pointer transition-colors',
                activeIdx === results.length
                  ? 'bg-blue-50'
                  : 'hover:bg-gray-50',
              )}
            >
              View all results
              <ArrowRight size={14} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
