import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  XCircle,
  RefreshCw,
  Database,
  Server,
  HardDrive,
  Cpu,
  AlertTriangle,
  ArrowRight,
  Users,
} from 'lucide-react';
import client from '@/api/client';
import clsx from 'clsx';

// ─── Types ────────────────────────────────────────────────────────────────────

interface HealthResult {
  database: string;
  redis: string;
  ollama: string;
  storage: string;
}

interface Stats {
  total_customers: number;
  total_purchase_orders: number;
  total_documents: number;
  uploaded: number;
  extracting: number;
  pending_reviews: number;
  verified: number;
  extraction_failures: number;
  rejected: number;
}

interface QueueStatus {
  workers_online: number;
  active_tasks: number;
  queued_tasks: number;
}

interface FailedDoc {
  id: string;
  document_type: string;
  original_filename: string | null;
  filename: string;
  po_number: string | null;
  customer_name: string | null;
  po_id: string | null;
  created_at: string | null;
  metadata?: {
    last_error?: string | null;
    extraction_attempts?: number;
  } | null;
}

interface ActiveDoc {
  id: string;
  document_type: string;
  original_filename: string | null;
  filename: string;
  po_number: string | null;
  status: string;
  created_at: string | null;
  po_id: string | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function isOk(val: string) {
  return val === 'ok';
}

function errorHint(service: string): string {
  const hints: Record<string, string> = {
    database: 'Check PostgreSQL / docker-compose logs',
    redis:    'Check Redis service / restart container',
    ollama:   'Check model endpoint URL in .env (OCR_BASE_URL)',
    storage:  'Check disk mount, permissions, and free space',
  };
  return hints[service] ?? '';
}

function errorCategory(err: string | null | undefined): string | null {
  if (!err) return null;
  const e = err.toLowerCase();
  if (e.includes('timeout') || e.includes('connect')) return 'OCR service may be down';
  if (e.includes('json') || e.includes('parse'))      return 'Model returned bad output — try re-extracting';
  if (e.includes('so number') || e.includes('so_number')) return 'Set SO number on the PO first';
  return null;
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' });
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ServiceCard({ name, value, icon: Icon }: { name: string; value: string; icon: React.ElementType }) {
  const ok = isOk(value);
  return (
    <div className={clsx(
      'rounded-lg border p-4 space-y-2',
      ok ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
    )}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon size={16} className={ok ? 'text-green-600' : 'text-red-600'} />
          <span className="text-sm font-semibold capitalize">{name}</span>
        </div>
        {ok
          ? <CheckCircle2 size={16} className="text-green-500" />
          : <XCircle size={16} className="text-red-500" />
        }
      </div>
      {!ok && (
        <div className="space-y-1">
          <p className="text-xs text-red-700 font-mono break-all">{value.replace('error: ', '')}</p>
          <p className="text-xs text-red-500 italic">{errorHint(name)}</p>
        </div>
      )}
    </div>
  );
}

function PipelineCounter({
  label, count, status, color,
}: { label: string; count: number; status: string; color: string }) {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(`/documents?status=${status}`)}
      className={clsx(
        'flex flex-col items-center px-5 py-3 rounded-lg border transition-colors hover:shadow-sm',
        color
      )}
    >
      <span className="text-2xl font-bold">{count}</span>
      <span className="text-xs font-medium mt-0.5">{label}</span>
    </button>
  );
}

function SectionHeader({ title, lastRefreshed }: { title: string; lastRefreshed: Date | null }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h3 className="text-base font-semibold text-gray-800">{title}</h3>
      {lastRefreshed && (
        <span className="text-xs text-gray-400">
          Updated {lastRefreshed.toLocaleTimeString('en-IN')}
        </span>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const navigate = useNavigate();

  const [health, setHealth]         = useState<HealthResult | null>(null);
  const [stats, setStats]           = useState<Stats | null>(null);
  const [queue, setQueue]           = useState<QueueStatus | null>(null);
  const [failures, setFailures]     = useState<FailedDoc[]>([]);
  const [active, setActive]         = useState<ActiveDoc[]>([]);

  const [healthTs, setHealthTs]     = useState<Date | null>(null);
  const [statsTs, setStatsTs]       = useState<Date | null>(null);
  const [queueTs, setQueueTs]       = useState<Date | null>(null);
  const [failuresTs, setFailuresTs] = useState<Date | null>(null);
  const [activeTs, setActiveTs]     = useState<Date | null>(null);

  const [refreshing, setRefreshing] = useState(false);

  // ── Fetch functions ──────────────────────────────────────────────────────

  const fetchHealth = useCallback(async () => {
    try {
      const { data } = await client.get('/api/v1/admin/health');
      setHealth(data);
      setHealthTs(new Date());
    } catch { /* keep previous */ }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const { data } = await client.get('/api/v1/admin/stats');
      setStats(data);
      setStatsTs(new Date());
    } catch { /* keep previous */ }
  }, []);

  const fetchQueue = useCallback(async () => {
    try {
      const { data } = await client.get('/api/v1/admin/queue');
      setQueue(data);
      setQueueTs(new Date());
    } catch { /* keep previous */ }
  }, []);

  const fetchFailures = useCallback(async () => {
    try {
      const { data } = await client.get('/api/v1/documents', {
        params: { status: 'EXTRACTION_FAILED', per_page: 20, page: 1 },
      });
      setFailures(data.items ?? []);
      setFailuresTs(new Date());
    } catch { /* keep previous */ }
  }, []);

  const fetchActive = useCallback(async () => {
    try {
      const [extracting, uploaded] = await Promise.all([
        client.get('/api/v1/documents', { params: { status: 'EXTRACTING', per_page: 20, page: 1 } }),
        client.get('/api/v1/documents', { params: { status: 'UPLOADED',   per_page: 20, page: 1 } }),
      ]);
      setActive([...(extracting.data.items ?? []), ...(uploaded.data.items ?? [])]);
      setActiveTs(new Date());
    } catch { /* keep previous */ }
  }, []);

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([fetchHealth(), fetchStats(), fetchQueue(), fetchFailures(), fetchActive()]);
    setRefreshing(false);
  }, [fetchHealth, fetchStats, fetchQueue, fetchFailures, fetchActive]);

  // ── Initial load + intervals ─────────────────────────────────────────────

  useEffect(() => {
    refreshAll();

    const intervals = [
      setInterval(fetchHealth,   30_000),
      setInterval(fetchStats,    30_000),
      setInterval(fetchQueue,    15_000),
      setInterval(fetchFailures, 60_000),
      setInterval(fetchActive,   10_000),
    ];
    return () => intervals.forEach(clearInterval);
  }, [refreshAll, fetchHealth, fetchStats, fetchQueue, fetchFailures, fetchActive]);

  // ─── Render ───────────────────────────────────────────────────────────────

  const anyServiceDown = health && Object.values(health).some((v) => !isOk(v));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Admin Console</h2>
        <button
          onClick={refreshAll}
          disabled={refreshing}
          className="flex items-center gap-2 text-sm px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          Refresh all
        </button>
      </div>

      {/* ── Section 1: System Health ─────────────────────────────────────── */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <SectionHeader title="System Health" lastRefreshed={healthTs} />
        {anyServiceDown && (
          <div className="mb-3 flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700">
            <AlertTriangle size={15} className="flex-shrink-0" />
            One or more services are unhealthy. See details below.
          </div>
        )}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {health ? (
            <>
              <ServiceCard name="database" value={health.database} icon={Database} />
              <ServiceCard name="redis"    value={health.redis}    icon={Server} />
              <ServiceCard name="model endpoint" value={health.ollama} icon={Cpu} />
              <ServiceCard name="storage"  value={health.storage}  icon={HardDrive} />
            </>
          ) : (
            <p className="col-span-4 text-sm text-gray-400 py-4 text-center">Checking services…</p>
          )}
        </div>
      </div>

      {/* ── Section 2: Document Pipeline ─────────────────────────────────── */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <SectionHeader title="Document Pipeline" lastRefreshed={statsTs} />
        <p className="text-xs text-gray-400 mb-4">Click any counter to view those documents.</p>
        {stats ? (
          <div className="flex flex-wrap gap-3 items-center">
            <PipelineCounter label="Uploaded"       count={stats.uploaded}            status="UPLOADED"          color="border-gray-200 bg-gray-50 text-gray-700 hover:border-gray-400" />
            <ArrowRight size={14} className="text-gray-300" />
            <PipelineCounter label="Extracting"     count={stats.extracting}          status="EXTRACTING"        color="border-blue-200 bg-blue-50 text-blue-700 hover:border-blue-400" />
            <ArrowRight size={14} className="text-gray-300" />
            <PipelineCounter label="Pending Review" count={stats.pending_reviews}     status="PENDING_REVIEW"    color="border-amber-200 bg-amber-50 text-amber-700 hover:border-amber-400" />
            <ArrowRight size={14} className="text-gray-300" />
            <PipelineCounter label="Verified"       count={stats.verified}            status="VERIFIED"          color="border-green-200 bg-green-50 text-green-700 hover:border-green-400" />
            <div className="w-px h-10 bg-gray-200 mx-1" />
            <PipelineCounter label="Failed"         count={stats.extraction_failures} status="EXTRACTION_FAILED" color="border-red-200 bg-red-50 text-red-700 hover:border-red-400" />
            <PipelineCounter label="Rejected"       count={stats.rejected}            status="REJECTED"          color="border-orange-200 bg-orange-50 text-orange-700 hover:border-orange-400" />
          </div>
        ) : (
          <p className="text-sm text-gray-400 py-4 text-center">Loading stats…</p>
        )}
        {stats && (
          <div className="mt-4 pt-4 border-t border-gray-100 flex gap-6 text-sm text-gray-500">
            <span><span className="font-medium text-gray-700">{stats.total_documents}</span> total documents</span>
            <span><span className="font-medium text-gray-700">{stats.total_purchase_orders}</span> purchase orders</span>
            <span className="flex items-center gap-1"><Users size={13} /><span className="font-medium text-gray-700">{stats.total_customers}</span> customers</span>
          </div>
        )}
      </div>

      {/* ── Section 3 + 4 side-by-side on wide screens ───────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

        {/* Section 3: Extraction Failures */}
        <div className="bg-white rounded-lg border border-red-200 p-5">
          <SectionHeader title="Extraction Failures" lastRefreshed={failuresTs} />
          {failures.length === 0 ? (
            <div className="flex items-center gap-2 py-6 justify-center text-green-600">
              <CheckCircle2 size={18} />
              <span className="text-sm">No extraction failures</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-red-50 text-gray-600">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Type</th>
                    <th className="text-left px-3 py-2 font-medium">File</th>
                    <th className="text-left px-3 py-2 font-medium">Error</th>
                    <th className="text-left px-3 py-2 font-medium">Attempts</th>
                    <th className="text-left px-3 py-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {failures.map((doc) => {
                    const err = doc.metadata?.last_error;
                    const cat = errorCategory(err);
                    return (
                      <tr key={doc.id} className="hover:bg-red-50">
                        <td className="px-3 py-2 font-medium text-gray-700">
                          {doc.document_type.replace(/_/g, ' ')}
                        </td>
                        <td className="px-3 py-2 text-gray-600 max-w-[120px] truncate" title={doc.original_filename ?? doc.filename}>
                          {doc.original_filename ?? doc.filename}
                        </td>
                        <td className="px-3 py-2 max-w-[200px]">
                          {cat ? (
                            <span className="inline-flex items-center gap-1 bg-red-100 text-red-700 px-1.5 py-0.5 rounded text-xs font-medium">
                              <AlertTriangle size={10} />{cat}
                            </span>
                          ) : (
                            <span className="text-gray-500 truncate block" title={err ?? ''}>
                              {err ?? '—'}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-gray-500 text-center">
                          {doc.metadata?.extraction_attempts ?? '—'}
                        </td>
                        <td className="px-3 py-2">
                          {doc.po_id && (
                            <button
                              onClick={() => navigate(`/purchase-orders/${doc.po_id}`)}
                              className="text-blue-600 hover:underline"
                            >
                              Open PO
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Section 4: Currently Active */}
        <div className="bg-white rounded-lg border border-blue-200 p-5">
          <SectionHeader title="Currently Active" lastRefreshed={activeTs} />
          {active.length === 0 ? (
            <div className="flex items-center gap-2 py-6 justify-center text-gray-400">
              <span className="text-sm">No documents currently processing</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-blue-50 text-gray-600">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Type</th>
                    <th className="text-left px-3 py-2 font-medium">File</th>
                    <th className="text-left px-3 py-2 font-medium">PO</th>
                    <th className="text-left px-3 py-2 font-medium">Status</th>
                    <th className="text-left px-3 py-2 font-medium">Since</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {active.map((doc) => (
                    <tr key={doc.id} className="hover:bg-blue-50">
                      <td className="px-3 py-2 font-medium text-gray-700">
                        {doc.document_type.replace(/_/g, ' ')}
                      </td>
                      <td className="px-3 py-2 text-gray-600 max-w-[140px] truncate" title={doc.original_filename ?? doc.filename}>
                        {doc.original_filename ?? doc.filename}
                      </td>
                      <td className="px-3 py-2 text-gray-600">{doc.po_number ?? '—'}</td>
                      <td className="px-3 py-2">
                        <span className={clsx(
                          'px-1.5 py-0.5 rounded text-xs font-medium',
                          doc.status === 'EXTRACTING'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-gray-100 text-gray-600'
                        )}>
                          {doc.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-gray-400">{fmtTime(doc.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* ── Section 5: Celery Queue ───────────────────────────────────────── */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <SectionHeader title="Celery Queue" lastRefreshed={queueTs} />
        {queue?.workers_online === 0 && (
          <div className="mb-3 flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700">
            <AlertTriangle size={15} className="flex-shrink-0" />
            <div>
              <span className="font-semibold">No Celery workers detected</span>
              {' — '}extraction jobs will not run.
              <span className="ml-2 font-mono text-xs">celery -A celery_app worker --loglevel=info</span>
            </div>
          </div>
        )}
        {queue ? (
          <div className="flex flex-wrap gap-4">
            <div className={clsx(
              'flex flex-col items-center px-6 py-3 rounded-lg border',
              queue.workers_online > 0 ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
            )}>
              <span className={clsx('text-2xl font-bold', queue.workers_online > 0 ? 'text-green-700' : 'text-red-700')}>
                {queue.workers_online}
              </span>
              <span className="text-xs font-medium text-gray-600 mt-0.5">Workers Online</span>
            </div>
            <div className="flex flex-col items-center px-6 py-3 rounded-lg border border-blue-200 bg-blue-50">
              <span className="text-2xl font-bold text-blue-700">{queue.active_tasks}</span>
              <span className="text-xs font-medium text-gray-600 mt-0.5">Active Tasks</span>
            </div>
            <div className="flex flex-col items-center px-6 py-3 rounded-lg border border-gray-200 bg-gray-50">
              <span className="text-2xl font-bold text-gray-700">{queue.queued_tasks}</span>
              <span className="text-xs font-medium text-gray-600 mt-0.5">Queued Tasks</span>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-400 py-4 text-center">Checking workers…</p>
        )}
      </div>
    </div>
  );
}
