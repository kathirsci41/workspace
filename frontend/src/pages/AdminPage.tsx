import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart3,
  FileText,
  FolderOpen,
  HardDrive,
  Clock,
  Activity,
  RefreshCw,
} from 'lucide-react';
import apiClient from '../api/client';
import Button from '../components/common/Button';
import type { StatsResponse, AuditLogsResponse } from '../types';

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<'stats' | 'logs'>('stats');

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Admin Dashboard</h1>

      {/* Tabs */}
      <div className="flex gap-4 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('stats')}
          className={`pb-3 px-1 border-b-2 transition-colors ${
            activeTab === 'stats'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <BarChart3 className="h-4 w-4 inline mr-2" />
          Statistics
        </button>
        <button
          onClick={() => setActiveTab('logs')}
          className={`pb-3 px-1 border-b-2 transition-colors ${
            activeTab === 'logs'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Activity className="h-4 w-4 inline mr-2" />
          Audit Logs
        </button>
      </div>

      {activeTab === 'stats' ? <StatsPanel /> : <AuditLogsPanel />}
    </div>
  );
}

function StatsPanel() {
  const {
    data: stats,
    isLoading,
    refetch,
  } = useQuery<StatsResponse>({
    queryKey: ['admin', 'stats'],
    queryFn: async () => {
      const response = await apiClient.get('/admin/stats');
      return response.data;
    },
  });

  if (isLoading) {
    return <div className="text-center py-8 text-gray-500">Loading statistics...</div>;
  }

  if (!stats) {
    return <div className="text-center py-8 text-gray-500">Failed to load statistics</div>;
  }

  return (
    <div className="space-y-6">
      {/* Refresh button */}
      <div className="flex justify-end">
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          icon={<FileText className="h-6 w-6 text-blue-600" />}
          label="Total Cases"
          value={stats.cases.total}
          bgColor="bg-blue-50"
        />
        <StatCard
          icon={<FolderOpen className="h-6 w-6 text-purple-600" />}
          label="Sales Orders"
          value={stats.sales_orders.total}
          bgColor="bg-purple-50"
        />
        <StatCard
          icon={<FileText className="h-6 w-6 text-green-600" />}
          label="Documents"
          value={stats.documents.total}
          bgColor="bg-green-50"
        />
        <StatCard
          icon={<HardDrive className="h-6 w-6 text-orange-600" />}
          label="Storage Used"
          value={`${stats.documents.total_size_mb} MB`}
          bgColor="bg-orange-50"
        />
      </div>

      {/* Case Status Breakdown */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Cases by Status</h2>
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <p className="text-2xl font-bold text-green-700">{stats.cases.open}</p>
            <p className="text-sm text-green-600">Open</p>
          </div>
          <div className="text-center p-4 bg-yellow-50 rounded-lg">
            <p className="text-2xl font-bold text-yellow-700">{stats.cases.in_progress}</p>
            <p className="text-sm text-yellow-600">In Progress</p>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <p className="text-2xl font-bold text-gray-700">{stats.cases.closed}</p>
            <p className="text-sm text-gray-600">Closed</p>
          </div>
        </div>
      </div>

      {/* Documents by Type */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Documents by Type</h2>
        <div className="space-y-3">
          {Object.entries(stats.documents.by_type).map(([type, count]) => (
            <div key={type} className="flex items-center justify-between">
              <span className="text-gray-700">{formatDocType(type)}</span>
              <div className="flex items-center gap-4">
                <div className="w-48 bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-primary-600 h-2 rounded-full"
                    style={{
                      width: `${(count / stats.documents.total) * 100}%`,
                    }}
                  />
                </div>
                <span className="text-gray-500 w-12 text-right">{count}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-2">
          <Clock className="h-5 w-5 text-gray-400" />
          <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
        </div>
        <p className="text-gray-600">
          <span className="text-2xl font-bold text-primary-600">
            {stats.documents.recent_uploads_7d}
          </span>{' '}
          documents uploaded in the last 7 days
        </p>
      </div>
    </div>
  );
}

function AuditLogsPanel() {
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);

  const { data, isLoading } = useQuery<AuditLogsResponse>({
    queryKey: ['admin', 'audit-logs', limit, offset],
    queryFn: async () => {
      const response = await apiClient.get('/admin/audit-logs', {
        params: { limit, offset },
      });
      return response.data;
    },
  });

  if (isLoading) {
    return <div className="text-center py-8 text-gray-500">Loading logs...</div>;
  }

  if (!data) {
    return <div className="text-center py-8 text-gray-500">Failed to load logs</div>;
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <span className="text-sm text-gray-500">
          Showing {offset + 1}-{Math.min(offset + limit, data.total)} of {data.total} logs
        </span>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0}
          >
            Previous
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setOffset(offset + limit)}
            disabled={offset + limit >= data.total}
          >
            Next
          </Button>
        </div>
      </div>

      <table className="min-w-full">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Timestamp
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Action
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Actor
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Details
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {data.logs.map((log) => (
            <tr key={log.id} className="hover:bg-gray-50">
              <td className="px-4 py-3 text-sm text-gray-500">
                {formatDateTime(log.createdAt)}
              </td>
              <td className="px-4 py-3">
                <span
                  className={`inline-flex px-2 py-1 text-xs rounded-full ${getActionColor(
                    log.action
                  )}`}
                >
                  {log.action}
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-gray-700">{log.actor}</td>
              <td className="px-4 py-3 text-sm text-gray-500">
                {JSON.stringify(log.details).slice(0, 100)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  bgColor,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  bgColor: string;
}) {
  return (
    <div className={`${bgColor} rounded-lg p-6`}>
      <div className="flex items-center gap-4">
        {icon}
        <div>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-600">{label}</p>
        </div>
      </div>
    </div>
  );
}

function formatDocType(type: string): string {
  const labels: Record<string, string> = {
    CUSTOMER_PO: 'Customer PO',
    VENDOR_INVOICE: 'Vendor Invoice',
    VENDOR_DC: 'Vendor DC',
    COMPANY_INVOICE: 'Company Invoice',
    COMPANY_DC: 'Company DC',
    POD: 'Proof of Delivery',
  };
  return labels[type] || type;
}

function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getActionColor(action: string): string {
  if (action.includes('CREATED')) return 'bg-green-100 text-green-700';
  if (action.includes('DELETED')) return 'bg-red-100 text-red-700';
  if (action.includes('UPDATED') || action.includes('ROTATED')) return 'bg-blue-100 text-blue-700';
  return 'bg-gray-100 text-gray-700';
}
