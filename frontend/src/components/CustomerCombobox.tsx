import { useState, useRef, useEffect, useMemo } from 'react';
import { ChevronDown, X } from 'lucide-react';
import clsx from 'clsx';

interface Customer {
  id: string;
  customer_id: string;
  name: string;
}

interface Props {
  customers: Customer[];
  value: string;            // selected customer UUID (or '')
  onChange: (id: string) => void;
  placeholder?: string;
  className?: string;
}

export default function CustomerCombobox({
  customers,
  value,
  onChange,
  placeholder = 'Type to search customers...',
  className,
}: Props) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Resolve selected customer for display
  const selected = useMemo(
    () => customers.find((c) => c.id === value) ?? null,
    [customers, value]
  );

  // Filter customers by query against customer_id and name
  const filtered = useMemo(() => {
    if (!query.trim()) return customers;
    const q = query.toLowerCase();
    return customers.filter(
      (c) =>
        c.customer_id.toLowerCase().includes(q) ||
        c.name.toLowerCase().includes(q)
    );
  }, [customers, query]);

  // Reset highlight when filtered list changes
  useEffect(() => setHighlightIdx(0), [filtered]);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery('');
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // Scroll highlighted item into view
  useEffect(() => {
    if (!open || !listRef.current) return;
    const item = listRef.current.children[highlightIdx] as HTMLElement | undefined;
    item?.scrollIntoView({ block: 'nearest' });
  }, [highlightIdx, open]);

  const handleSelect = (id: string) => {
    onChange(id);
    setQuery('');
    setOpen(false);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange('');
    setQuery('');
    setOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setOpen(true);
        e.preventDefault();
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightIdx((i) => Math.min(i + 1, filtered.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightIdx((i) => Math.max(i - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (filtered[highlightIdx]) {
          handleSelect(filtered[highlightIdx].id);
        }
        break;
      case 'Escape':
        setOpen(false);
        setQuery('');
        inputRef.current?.blur();
        break;
    }
  };

  return (
    <div ref={containerRef} className={clsx('relative', className)}>
      <div
        className={clsx(
          'flex items-center border rounded-lg text-sm transition-colors',
          open
            ? 'border-blue-500 ring-2 ring-blue-500'
            : 'border-gray-300 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500'
        )}
      >
        <input
          ref={inputRef}
          type="text"
          value={open ? query : selected ? `${selected.customer_id} — ${selected.name}` : ''}
          readOnly={!open}
          placeholder={selected ? `${selected.customer_id} — ${selected.name}` : placeholder}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => {
            setOpen(true);
            setQuery('');
          }}
          onKeyDown={handleKeyDown}
          className={clsx(
            'flex-1 px-3 py-2 bg-transparent outline-none text-sm min-w-0',
            !open && selected && 'text-gray-800',
            !open && !selected && 'text-gray-400'
          )}
        />
        {value && (
          <button
            type="button"
            onClick={handleClear}
            className="px-1 text-gray-400 hover:text-gray-600"
            tabIndex={-1}
          >
            <X size={14} />
          </button>
        )}
        <button
          type="button"
          onClick={() => {
            setOpen((o) => !o);
            if (!open) inputRef.current?.focus();
          }}
          className="px-2 text-gray-400 hover:text-gray-600"
          tabIndex={-1}
        >
          <ChevronDown size={14} className={clsx('transition-transform', open && 'rotate-180')} />
        </button>
      </div>

      {/* Dropdown */}
      {open && (
        <ul
          ref={listRef}
          className="absolute z-50 mt-1 w-full max-h-52 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-gray-400">No customers found</li>
          ) : (
            filtered.map((c, idx) => (
              <li
                key={c.id}
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSelect(c.id);
                }}
                onMouseEnter={() => setHighlightIdx(idx)}
                className={clsx(
                  'px-3 py-2 text-sm cursor-pointer flex items-center justify-between',
                  idx === highlightIdx && 'bg-blue-50',
                  c.id === value && 'font-medium text-blue-700'
                )}
              >
                <span>
                  <span className="font-mono text-xs text-gray-500 mr-2">{c.customer_id}</span>
                  {c.name}
                </span>
                {c.id === value && (
                  <span className="text-blue-500 text-xs">✓</span>
                )}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
