import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Search, Users, FileText, File, Loader2, MapPin } from 'lucide-react';
import { useSearch, useAddressSearch } from '@/hooks/useSearch';
import clsx from 'clsx';
import type { SearchResult } from '@/types';

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [input, setInput] = useState(searchParams.get('q') ?? '');
  const [tab, setTab] = useState<'global' | 'address'>('global');
  const [addressInput, setAddressInput] = useState('');
  const [addressQuery, setAddressQuery] = useState('');
  const navigate = useNavigate();

  const query = searchParams.get('q') ?? '';
  const { data, isLoading } = useSearch(query);
  const { data: addrData, isLoading: addrLoading } = useAddressSearch(addressQuery);

  useEffect(() => {
    setInput(searchParams.get('q') ?? '');
  }, [searchParams]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      setSearchParams({ q: input.trim() });
    }
  };

  const handleAddressSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setAddressQuery(addressInput.trim());
  };

  const handleResultClick = (result: SearchResult) => {
    switch (result.result_type) {
      case 'customer':
        navigate(`/purchase-orders?customer_id=${result.id}`);
        break;
      case 'purchase_order':
        navigate(`/purchase-orders/${result.id}`);
        break;
      case 'document':
        if (result.po_id) {
          navigate(`/purchase-orders/${result.po_id}?highlight=${result.id}`);
        }
        break;
    }
  };

  const resultIcon = (type: string) => {
    switch (type) {
      case 'customer':
        return <Users size={20} className="text-blue-500" />;
      case 'purchase_order':
        return <FileText size={20} className="text-green-500" />;
      case 'document':
        return <File size={20} className="text-amber-500" />;
      default:
        return <File size={20} className="text-gray-400" />;
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold mb-4">Search</h2>

      {/* Tab switcher */}
      <div className="flex gap-1 mb-5 bg-gray-100 p-1 rounded-lg w-fit">
        <button
          onClick={() => setTab('global')}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
            tab === 'global' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'
          )}
        >
          <Search size={14} /> Reference Search
        </button>
        <button
          onClick={() => setTab('address')}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
            tab === 'address' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'
          )}
        >
          <MapPin size={14} /> Address Search
        </button>
      </div>

      {tab === 'address' && (
        <>
          <form onSubmit={handleAddressSubmit} className="mb-6">
            <div className="relative">
              <MapPin size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search delivery address across all documents..."
                value={addressInput}
                onChange={(e) => setAddressInput(e.target.value)}
                className="w-full pl-12 pr-24 py-3 border border-gray-300 rounded-xl text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                autoFocus
              />
              <button
                type="submit"
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-blue-600 text-white text-sm px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                disabled={addressInput.length < 3}
              >
                Search
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-1.5 pl-1">Finds documents where the extracted delivery address contains this text.</p>
          </form>

          {addrLoading && (
            <div className="flex justify-center py-8">
              <Loader2 size={28} className="animate-spin text-gray-400" />
            </div>
          )}

          {addrData && !addrLoading && addressQuery && (
            <>
              <p className="text-sm text-gray-500 mb-4">
                Found {addrData.total} result{addrData.total !== 1 ? 's' : ''} for &ldquo;{addressQuery}&rdquo;
              </p>
              {addrData.results.length === 0 ? (
                <div className="text-center py-12 text-gray-400">
                  <MapPin size={48} className="mx-auto mb-3 opacity-50" />
                  <p className="text-sm">No documents with that delivery address found.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {addrData.results.map((result) => (
                    <div
                      key={`${result.result_type}-${result.id}`}
                      onClick={() => handleResultClick(result)}
                      className="flex items-start gap-3 p-4 bg-white rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-sm cursor-pointer transition-all"
                    >
                      <div className="mt-0.5">{resultIcon(result.result_type)}</div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{result.display_name}</p>
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1">
                          <span className="text-xs text-gray-400 uppercase">
                            {result.document_type?.replace(/_/g, ' ') ?? result.result_type}
                          </span>
                          {result.po_number && (
                            <span className="text-xs text-gray-500">PO: {result.po_number}</span>
                          )}
                          {result.customer_name && (
                            <span className="text-xs text-gray-500">{result.customer_name}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}

      {tab === 'global' && (
      <>
      {/* Search input */}
      <form onSubmit={handleSubmit} className="mb-6">
        <div className="relative">
          <Search
            size={20}
            className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="text"
            placeholder="Search by reference number, PO, customer..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-xl text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            autoFocus
          />
        </div>
      </form>

      {/* Hint */}
      {query.length > 0 && query.length < 2 && (
        <p className="text-sm text-gray-400 text-center py-4">
          Type at least 2 characters to search.
        </p>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex justify-center py-8">
          <Loader2 size={28} className="animate-spin text-gray-400" />
        </div>
      )}

      {/* Results */}
      {data && !isLoading && (
        <>
          <p className="text-sm text-gray-500 mb-4">
            Found {data.total} result{data.total !== 1 ? 's' : ''} for &ldquo;
            {data.query}&rdquo;
          </p>

          {data.results.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <Search size={48} className="mx-auto mb-3 opacity-50" />
              <p className="text-sm">
                No results found. Try a different search term.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {data.results.map((result) => (
                <div
                  key={`${result.result_type}-${result.id}`}
                  onClick={() => handleResultClick(result)}
                  className="flex items-start gap-3 p-4 bg-white rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-sm cursor-pointer transition-all"
                >
                  <div className="mt-0.5">{resultIcon(result.result_type)}</div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">
                      {result.display_name}
                    </p>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1">
                      <span className="text-xs text-gray-400 uppercase">
                        {result.result_type.replace('_', ' ')}
                      </span>
                      {result.po_number && (
                        <span className="text-xs text-gray-500">
                          PO: {result.po_number}
                        </span>
                      )}
                      {result.customer_name && (
                        <span className="text-xs text-gray-500">
                          {result.customer_name}
                        </span>
                      )}
                      {result.confidence != null && (
                        <span
                          className={clsx(
                            'text-xs font-medium',
                            result.confidence >= 80
                              ? 'text-green-600'
                              : result.confidence >= 50
                                ? 'text-amber-600'
                                : 'text-red-600'
                          )}
                        >
                          {result.confidence}%
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
      </>
      )}
    </div>
  );
}
