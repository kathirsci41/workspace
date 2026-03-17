import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
import { useCustomers, useCreateCustomer } from '@/hooks/useCustomers';

export default function CustomersPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [showModal, setShowModal] = useState(false);
  const navigate = useNavigate();

  const { data, isLoading, isError, error } = useCustomers(page, 20, search || undefined);
  const createMutation = useCreateCustomer();

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Customers</h2>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          <Plus size={18} />
          Add Customer
        </button>
      </div>

      {/* Search */}
      <div className="mb-4 max-w-sm relative">
        <Search
          size={18}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
        />
        <input
          type="text"
          placeholder="Search customers..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-5 py-3 font-medium">Customer ID</th>
              <th className="text-left px-5 py-3 font-medium">Name</th>
              <th className="text-left px-5 py-3 font-medium">GST</th>
              <th className="text-left px-5 py-3 font-medium">Email</th>
              <th className="text-left px-5 py-3 font-medium">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : isError ? (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-center text-red-500">
                  Failed to load customers{error instanceof Error ? `: ${error.message}` : '.'}
                </td>
              </tr>
            ) : data?.items?.length ? (
              data.items.map((c) => (
                <tr
                  key={c.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() =>
                    navigate(`/purchase-orders?customer_id=${c.id}`)
                  }
                >
                  <td className="px-5 py-3 font-mono font-medium text-blue-600">
                    {c.customer_id}
                  </td>
                  <td className="px-5 py-3">{c.name}</td>
                  <td className="px-5 py-3 text-gray-600">
                    {c.gst_number ?? '—'}
                  </td>
                  <td className="px-5 py-3 text-gray-600">
                    {c.contact_email ?? '—'}
                  </td>
                  <td className="px-5 py-3 text-gray-500 text-xs">
                    {new Date(c.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-center text-gray-400">
                  No customers found.
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

      {/* Add Customer Modal */}
      {showModal && (
        <CreateCustomerModal
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

function CreateCustomerModal({
  onClose,
  onCreate,
  isLoading,
  error,
}: {
  onClose: () => void;
  onCreate: (body: {
    customer_id: string;
    name: string;
    contact_email?: string;
    gst_number?: string;
  }) => void;
  isLoading: boolean;
  error: Error | null;
}) {
  const [form, setForm] = useState({
    customer_id: '',
    name: '',
    contact_email: '',
    gst_number: '',
  });
  const [validationError, setValidationError] = useState('');

  const CUSTOMER_ID_PATTERN = /^[A-Z]{2,5}-[A-Z0-9]+$/;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError('');
    const cid = form.customer_id.toUpperCase().trim();
    if (!CUSTOMER_ID_PATTERN.test(cid)) {
      setValidationError('Customer ID must be 2-5 uppercase letters, a dash, then letters/numbers. E.g. SKY-AB1234');
      return;
    }
    onCreate({
      customer_id: cid,
      name: form.name.trim(),
      contact_email: form.contact_email || undefined,
      gst_number: form.gst_number || undefined,
    });
  };

  const apiError = error
    ? ((error as any)?.response?.data?.detail?.[0]?.msg ||
       (error as any)?.response?.data?.detail ||
       error.message ||
       'Failed to create customer')
    : '';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h3 className="text-lg font-semibold mb-4">Add Customer</h3>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Customer ID *
            </label>
            <input
              required
              placeholder="SKY-XXXXX"
              value={form.customer_id}
              onChange={(e) => {
                setValidationError('');
                setForm((f) => ({ ...f, customer_id: e.target.value.toUpperCase() }));
              }}
              pattern="^[A-Z]{2,5}-[A-Z0-9]+$"
              title="2-5 uppercase letters, dash, then letters/numbers (e.g. SKY-AB1234)"
              className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none font-mono"
            />
            <p className="text-xs text-gray-400 mt-0.5">Format: 2-5 letters + dash + alphanumeric (e.g. SKY-AB1234)</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name *
            </label>
            <input
              required
              placeholder="Company name"
              value={form.name}
              onChange={(e) =>
                setForm((f) => ({ ...f, name: e.target.value }))
              }
              className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              type="email"
              placeholder="contact@example.com"
              value={form.contact_email}
              onChange={(e) =>
                setForm((f) => ({ ...f, contact_email: e.target.value }))
              }
              className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              GST Number
            </label>
            <input
              placeholder="22AAAAA0000A1Z5"
              value={form.gst_number}
              onChange={(e) =>
                setForm((f) => ({ ...f, gst_number: e.target.value }))
              }
              className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          {(validationError || apiError) && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-sm">
              {validationError || apiError}
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
