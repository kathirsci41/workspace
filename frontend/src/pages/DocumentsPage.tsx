import { useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { ExternalLink, X, Upload } from 'lucide-react';
import { useDocuments } from '@/hooks/useDocuments';
import { useCustomers } from '@/hooks/useCustomers';
import { SkeletonTableRow } from '@/components/Skeleton';
import clsx from 'clsx';

const DOC_TYPE_OPTIONS = [
  { value: 'CUSTOMER_PO',    label: 'Customer PO' },
  { value: 'COMPANY_PO',     label: 'Company PO' },
  { value: 'VENDOR_DC',      label: 'Vendor DC' },
  { value: 'VENDOR_INVOICE', label: 'Vendor Invoice' },
  { value: 'COMPANY_DC',     label: 'Company DC' },
  { value: 'COMPANY_INVOICE', label: 'Company Invoice' },
];

const STATUS_OPTIONS = [
  { value: 'PENDING_REVIEW',    label: 'Pending Review' },
  { value: 'VERIFIED',          label: 'Verified' },
  { value: 'EXTRACTION_FAILED', label: 'Extraction Failed' },
  { value: 'REJECTED',          label: 'Rejected' },
  { value: 'UPLOADED',          label: 'Uploaded' },
  { value: 'EXTRACTING',        label: 'Extracting' },
];

function getPresetDates(preset: string): { date_from: string; date_to: string } {
  const today = new Date();
  const fmt = (d: Date) => d.toISOString().split('T')[0];
  const daysAgo = (n: number) => {
    const d = new Date(today);
    d.setDate(d.getDate() - n);
    return fmt(d);
  };
  if (preset === '7d')  return { date_from: daysAgo(7),  date_to: fmt(today) };
  if (preset === '30d') return { date_from: daysAgo(30), date_to: fmt(today) };
  return { date_from: '', date_to: '' };
}

export default function DocumentsPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [docType,    setDocType]    = useState(searchParams.get('document_type') ?? '');
  const [status,     setStatus]     = useState(searchParams.get('status') ?? '');
  const [customerId, setCustomerId] = useState('');
  const [dateFrom,   setDateFrom]   = useState('');
  const [dateTo,     setDateTo]     = useState('');
  const [datePreset, setDatePreset] = useState('');
  const [page, setPage] = useState(1);

  const { data: customers } = useCustomers(1, 100);

  const filters: Record<string, string> = {};
  if (docType)    filters.document_type = docType;
  if (status)     filters.status        = status;
  if (customerId) filters.customer_id   = customerId;
  if (dateFrom)   filters.date_from     = dateFrom;
  if (dateTo)     filters.date_to       = dateTo;

  const { data, isLoading } = useDocuments(filters, page, 50);

  const activeFilterCount = [docType, status, customerId, dateFrom, dateTo].filter(Boolean).length;

  const resetFilters = () => {
    setDocType(''); setStatus(''); setCustomerId('');
    setDateFrom(''); setDateTo(''); setDatePreset(''); setPage(1);
  };

  const applyPreset = (preset: string) => {
    setDatePreset(preset);
    if (preset === 'custom') return;
    const { date_from, date_to } = getPresetDates(preset);
    setDateFrom(date_from);
    setDateTo(date_to);
    setPage(1);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Documents</h2>
        <div className="flex items-center gap-4">
          <Link
            to="/documents/upload"
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-semibold"
          >
            <Upload size={18} />
            Upload
          </Link>
          {data && (
            <span className="text-sm text-gray-500">{data.total} document{data.total !== 1 ? 's' : ''}</span>
          )}
        </div>
      </div>

      {/* Filter bar */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4 space-y-3">
        <div className="flex flex-wrap gap-3 items-center">
          {/* Document type */}
          <select
            value={docType}
            onChange={(e) => { setDocType(e.target.value); setPage(1); }}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Types</option>
            {DOC_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          {/* Status */}
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          {/* Customer */}
          <select
            value={customerId}
            onChange={(e) => { setCustomerId(e.target.value); setPage(1); }}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Customers</option>
            {customers?.items.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          {activeFilterCount > 0 && (
            <button
              onClick={resetFilters}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-red-600 border border-gray-300 hover:border-red-300 px-3 py-2 rounded-lg"
            >
              <X size={12} />
              Reset ({activeFilterCount})
            </button>
          )}
        </div>

        {/* Date range row */}
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-gray-500 font-medium">Uploaded:</span>
          {[
            { value: '7d',     label: 'Last 7 days' },
            { value: '30d',    label: 'Last 30 days' },
            { value: 'custom', label: 'Custom' },
          ].map((preset) => (
            <button
              key={preset.value}
              onClick={() => applyPreset(datePreset === preset.value ? '' : preset.value)}
              className={clsx(
                'px-3 py-1 text-xs rounded-full border font-medium transition-colors',
                datePreset === preset.value
                  ? 'bg-accent text-white border-accent'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
              )}
            >
              {preset.label}
            </button>
          ))}
          {datePreset === 'custom' && (
            <div className="flex items-center gap-2 ml-1">
              <span className="text-xs text-gray-500">From</span>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-xs text-gray-500">To</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-veil/30 text-ink/60">
            <tr>
              <th className="text-left px-5 py-3 font-medium">Type</th>
              <th className="text-left px-5 py-3 font-medium">Filename</th>
              <th className="text-left px-5 py-3 font-medium">Ref No</th>
              <th className="text-left px-5 py-3 font-medium">PO Number</th>
              <th className="text-left px-5 py-3 font-medium">Customer</th>
              <th className="text-left px-5 py-3 font-medium">Status</th>
              <th className="text-left px-5 py-3 font-medium">Uploaded</th>
              <th className="text-left px-5 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => <SkeletonTableRow key={i} columns={8} />)
              : data?.items?.length ? (
              data.items.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <span className="text-xs font-medium text-gray-700 bg-gray-100 px-2 py-1 rounded">
                      {doc.document_type.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-700 max-w-[200px] truncate" title={doc.original_filename ?? '—'}>
                    {doc.original_filename ?? '—'}
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-gray-600">
                    {doc.metadata?.primary_ref_no ?? '—'}
                  </td>
                  <td className="px-5 py-3 font-mono font-medium text-accent">
                    {doc.po_number || '—'}
                  </td>
                  <td className="px-5 py-3 text-ink/70 max-w-[160px] truncate" title={doc.customer_name || '—'}>
                    {doc.customer_name || '—'}
                  </td>
                  <td className="px-5 py-3">
                    <DocStatusBadge status={doc.status} />
                  </td>
                  <td className="px-5 py-3 text-gray-500 text-xs">
                    {doc.created_at ? new Date(doc.created_at).toLocaleDateString('en-IN') : '—'}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      {doc.status === 'PENDING_REVIEW' && doc.po_id && (
                        <button
                          onClick={() => navigate(`/purchase-orders/${doc.po_id}?highlight=${doc.id}&review=${doc.id}`)}
                          className="flex items-center gap-1 text-xs font-medium text-amber-700 hover:text-amber-900"
                        >
                          Review →
                        </button>
                      )}
                      {doc.po_id && (
                        <button
                          onClick={() => navigate(`/purchase-orders/${doc.po_id}`)}
                          className="flex items-center gap-1 text-xs text-blue-600 hover:underline"
                        >
                          <ExternalLink size={12} />
                          Open PO
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8} className="px-5 py-8 text-center text-gray-400">
                  <p className="mb-2">No documents match these filters.</p>
                  <button
                    onClick={resetFilters}
                    className="text-sm text-blue-600 hover:underline font-medium"
                  >
                    Reset filters
                  </button>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.total > 50 && (
        <div className="flex items-center justify-between mt-4 text-sm">
          <span className="text-gray-500">
            Page {page} of {Math.ceil(data.total / 50)}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Previous
            </button>
            <button
              disabled={page * 50 >= data.total}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function DocStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    VERIFIED:          'bg-green-100 text-green-700',
    PENDING_REVIEW:    'bg-amber-100 text-amber-700',
    EXTRACTION_FAILED: 'bg-red-100 text-red-700',
    REJECTED:          'bg-red-100 text-red-600',
    EXTRACTING:        'bg-blue-100 text-blue-700',
    UPLOADED:          'bg-gray-100 text-gray-600',
  };
  return (
    <span className={clsx('text-xs font-medium px-2 py-1 rounded-full', colors[status] ?? 'bg-gray-100 text-gray-700')}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}
