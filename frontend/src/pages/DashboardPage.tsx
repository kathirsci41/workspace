import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, FileText, Clock, CheckCircle } from 'lucide-react';
import client from '@/api/client';
import { usePurchaseOrders } from '@/hooks/usePurchaseOrders';
import clsx from 'clsx';

interface Stats {
  total_customers: number;
  total_purchase_orders: number;
  total_documents: number;
  pending_review: number;
  verified: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const navigate = useNavigate();
  const { data: poData } = usePurchaseOrders(1, 10);

  useEffect(() => {
    client.get('/api/v1/admin/stats').then((res) => setStats(res.data));
  }, []);

  const cards = stats
    ? [
        {
          label: 'Total Customers',
          value: stats.total_customers,
          icon: Users,
          color: 'bg-blue-100 text-blue-600',
        },
        {
          label: 'Total POs',
          value: stats.total_purchase_orders,
          icon: FileText,
          color: 'bg-green-100 text-green-600',
        },
        {
          label: 'Pending Reviews',
          value: stats.pending_review,
          icon: Clock,
          color: 'bg-amber-100 text-amber-600',
        },
        {
          label: 'Verified Documents',
          value: stats.verified,
          icon: CheckCircle,
          color: 'bg-emerald-100 text-emerald-600',
        },
      ]
    : [];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {cards.map((card) => (
          <div
            key={card.label}
            className="bg-white rounded-lg border border-gray-200 p-5 flex items-center gap-4"
          >
            <div className={clsx('p-3 rounded-lg', card.color)}>
              <card.icon size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500">{card.label}</p>
              <p className="text-2xl font-bold">{card.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Recent POs */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold">Recent Purchase Orders</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left px-5 py-3 font-medium">PO Number</th>
                <th className="text-left px-5 py-3 font-medium">Customer</th>
                <th className="text-left px-5 py-3 font-medium">Date</th>
                <th className="text-left px-5 py-3 font-medium">Chain %</th>
                <th className="text-left px-5 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {poData?.items?.map((po) => (
                <tr
                  key={po.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/purchase-orders/${po.id}`)}
                >
                  <td className="px-5 py-3 font-medium">{po.po_number}</td>
                  <td className="px-5 py-3 text-gray-600">
                    {po.customer_name ?? po.customer_sky_id ?? '—'}
                  </td>
                  <td className="px-5 py-3 text-gray-600">
                    {po.po_date ?? '—'}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-gray-200 rounded-full max-w-[100px]">
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
              ))}
              {(!poData?.items || poData.items.length === 0) && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-gray-400">
                    No purchase orders yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
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
