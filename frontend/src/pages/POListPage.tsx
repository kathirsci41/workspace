import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
import { usePurchaseOrders, useCreatePO } from '@/hooks/usePurchaseOrders';
import { useCustomers } from '@/hooks/useCustomers';
import CustomerCombobox from '@/components/CustomerCombobox';
import clsx from 'clsx';

export default function POListPage() {
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [customerFilter, setCustomerFilter] = useState(
    searchParams.get('customer_id') ?? ''
  );
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [showModal, setShowModal] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const cid = searchParams.get('customer_id');
    if (cid) setCustomerFilter(cid);
  }, [searchParams]);

  const filters: Record<string, string> = {};
  if (search) filters.search = search;
  if (customerFilter) filters.customer_id = customerFilter;
  if (statusFilter) filters.status = statusFilter;

  const { data, isLoading } = usePurchaseOrders(page, 20, filters);
  const { data: customers } = useCustomers(1, 100);
  const createMutation = useCreatePO();

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Purchase Orders</h2>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          <Plus size={18} />
          Create PO
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative max-w-xs">
          <Search
            size={18}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="text"
            placeholder="Search PO number..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <CustomerCombobox
          customers={customers?.items ?? []}
          value={customerFilter}
          onChange={(id) => {
            setCustomerFilter(id);
            setPage(1);
          }}
          placeholder="All Customers"
          className="w-56"
        />
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Statuses</option>
          <option value="INITIATED">Initiated</option>
          <option value="IN_PROGRESS">In Progress</option>
          <option value="NEAR_COMPLETE">Near Complete</option>
          <option value="COMPLETE">Complete</option>
          <option value="CANCELLED">Cancelled</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-5 py-3 font-medium">PO Number</th>
              <th className="text-left px-5 py-3 font-medium">Customer</th>
              <th className="text-left px-5 py-3 font-medium">Date</th>
              <th className="text-left px-5 py-3 font-medium">Amount</th>
              <th className="text-left px-5 py-3 font-medium">Chain %</th>
              <th className="text-left px-5 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : data?.items?.length ? (
              data.items.map((po) => (
                <tr
                  key={po.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/purchase-orders/${po.id}`)}
                >
                  <td className="px-5 py-3 font-medium">{po.po_number}</td>
                  <td className="px-5 py-3 text-gray-600">
                    {po.customer_name
                      ? `${po.customer_sky_id ?? ''} ${po.customer_name}`
                      : '—'}
                  </td>
                  <td className="px-5 py-3 text-gray-600">
                    {po.po_date ?? '—'}
                  </td>
                  <td className="px-5 py-3 text-gray-600">
                    {po.total_amount != null
                      ? `₹\u00A0${po.total_amount.toLocaleString('en-IN')}`
                      : '—'}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-gray-200 rounded-full max-w-[80px]">
                        <div
                          className={clsx(
                            'h-full rounded-full',
                            po.chain_completeness === 100
                              ? 'bg-green-500'
                              : po.chain_completeness >= 50
                                ? 'bg-amber-500'
                                : 'bg-blue-500'
                          )}
                          style={{ width: `${po.chain_completeness}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500">
                        {po.chain_completeness}%
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <StatusBadge status={po.status} />
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-gray-400">
                  No purchase orders found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.total > 20 && (
        <div className="flex items-center justify-between mt-4 text-sm">
          <span className="text-gray-500">
            Page {page} of {Math.ceil(data.total / 20)}
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
              disabled={page * 20 >= data.total}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Create PO Modal */}
      {showModal && (
        <CreatePOModal
          customers={customers?.items ?? []}
          onClose={() => {
            setShowModal(false);
            createMutation.reset();
          }}
          onCreate={(body) => {
            createMutation.mutate(body, {
              onSuccess: () => setShowModal(false),
            });
          }}
          isLoading={createMutation.isPending}
          error={createMutation.error}
        />
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    INITIATED: 'bg-gray-100 text-gray-700',
    IN_PROGRESS: 'bg-blue-100 text-blue-700',
    NEAR_COMPLETE: 'bg-amber-100 text-amber-700',
    COMPLETE: 'bg-green-100 text-green-700',
    CANCELLED: 'bg-red-100 text-red-700',
  };
  return (
    <span
      className={clsx(
        'text-xs font-medium px-2 py-1 rounded-full',
        colors[status] ?? 'bg-gray-100 text-gray-700'
      )}
    >
      {status.replace('_', ' ')}
    </span>
  );
}

function CreatePOModal({
  customers,
  onClose,
  onCreate,
  isLoading,
  error,
}: {
  customers: { id: string; customer_id: string; name: string }[];
  onClose: () => void;
  onCreate: (body: {
    po_number: string;
    customer_id: string;
    po_date?: string;
    total_amount?: number;
  }) => void;
  isLoading: boolean;
  error: Error | null;
}) {
  const [form, setForm] = useState({
    po_number: '',
    customer_id: '',
    po_date: '',
    total_amount: '',
  });
  const [validationError, setValidationError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError('');
    const poNum = form.po_number.trim();
    if (!poNum) {
      setValidationError('PO Number is required.');
      return;
    }
    if (!form.customer_id) {
      setValidationError('Please select a customer.');
      return;
    }
    onCreate({
      po_number: poNum,
      customer_id: form.customer_id,
      po_date: form.po_date || undefined,
      total_amount: form.total_amount
        ? parseFloat(form.total_amount)
        : undefined,
    });
  };

  const apiError = error
    ? ((error as any)?.response?.data?.detail?.[0]?.msg ||
       (error as any)?.response?.data?.detail ||
       error.message ||
       'Failed to create PO')
    : '';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h3 className="text-lg font-semibold mb-4">Create Purchase Order</h3>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Customer *
            </label>
            <CustomerCombobox
              customers={customers}
              value={form.customer_id}
              onChange={(id) =>
                setForm((f) => ({ ...f, customer_id: id }))
              }
              placeholder="Type to search customers..."
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              PO Number *
            </label>
            <input
              required
              placeholder="PO-2026-0001"
              value={form.po_number}
              onChange={(e) =>
                setForm((f) => ({ ...f, po_number: e.target.value }))
              }
              className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                PO Date
              </label>
              <input
                type="date"
                value={form.po_date}
                onChange={(e) =>
                  setForm((f) => ({ ...f, po_date: e.target.value }))
                }
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Amount
              </label>
              <input
                type="number"
                step="0.01"
                placeholder="0.00"
                value={form.total_amount}
                onChange={(e) =>
                  setForm((f) => ({ ...f, total_amount: e.target.value }))
                }
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
          </div>
          {(validationError || apiError) && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
              {validationError || (typeof apiError === 'string' ? apiError : JSON.stringify(apiError))}
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
