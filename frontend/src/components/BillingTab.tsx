import { useState } from 'react';
import type { PurchaseOrder, BillingMilestone } from '@/types';
import type { ChainStatusResponse } from '@/api/purchaseOrders';
import clsx from 'clsx';

interface Props {
  po: PurchaseOrder;
  chainValidation: ChainStatusResponse | null;
  onUpdate: (patch: Partial<PurchaseOrder>) => void;
}

const TYPE_LABELS = { full: 'Full', staged: 'Staged', recurring: 'Recurring' };

const STATUS_TAG: Record<string, string> = {
  complete: 'bg-green-100 text-green-700',
  paid:     'bg-green-100 text-green-700',
  partial:  'bg-amber-100 text-amber-700',
  pending:  'bg-gray-100 text-gray-500',
  mismatch: 'bg-red-100 text-red-700',
};

function KpiCard({ label, value, sub, variant }: {
  label: string; value: string; sub: string;
  variant: 'ok' | 'warn' | 'bad' | 'neutral';
}) {
  const cls = {
    ok:      'border-green-300 bg-green-50',
    warn:    'border-amber-300 bg-amber-50',
    bad:     'border-red-300  bg-red-50',
    neutral: 'border-[--veil] bg-white',
  }[variant];
  return (
    <div className={clsx('border rounded-xl p-3', cls)}>
      <div className="text-[9px] font-bold uppercase tracking-wide text-gray-400">{label}</div>
      <div className="text-base font-bold text-[--ink] mt-1">{value}</div>
      <div className="text-[10px] text-gray-500 mt-0.5">{sub}</div>
    </div>
  );
}

export default function BillingTab({ po, chainValidation, onUpdate }: Props) {
  const billingType = po.billing_type ?? 'full';
  const milestones: BillingMilestone[] = po.billing_milestones ?? [];
  const stages = chainValidation?.billing.stages ?? [];
  const total = Number(po.total_amount ?? 0);

  const billedSoFar = stages.reduce((sum, s) => sum + (s.invoiced_amount ?? 0), 0);
  const outstanding = Math.max(0, total - billedSoFar);
  const billedPct   = total > 0 ? Math.round((billedSoFar / total) * 100) : 0;

  const [editingMilestones, setEditingMilestones] = useState(false);
  type DraftMilestone = BillingMilestone & { _id: number };
  const toDraft = (m: BillingMilestone, i: number): DraftMilestone => ({ ...m, _id: i });
  const [draftMilestones, setDraftMilestones] = useState<DraftMilestone[]>(milestones.map(toDraft));

  function saveMilestones() {
    onUpdate({ billing_milestones: draftMilestones.map(({ _id: _, ...m }) => m) });
    setEditingMilestones(false);
  }

  function addMilestone() {
    setDraftMilestones(prev => [
      ...prev,
      { name: '', percentage: 0, trigger: '', due_date: null, _id: Date.now() },
    ]);
  }

  function updateDraft(id: number, field: keyof BillingMilestone, value: string | number | null) {
    setDraftMilestones(prev => prev.map(m => m._id === id ? { ...m, [field]: value } : m));
  }

  function removeDraft(id: number) {
    setDraftMilestones(prev => prev.filter(m => m._id !== id));
  }

  return (
    <div>
      {/* Type selector */}
      <div className="bg-white border border-[--veil] rounded-xl p-4 mb-4 flex items-center gap-4">
        <span className="text-xs font-bold text-gray-500">Billing Type:</span>
        <div className="flex gap-1.5">
          {(['full', 'staged', 'recurring'] as const).map(t => (
            <button
              key={t}
              onClick={() => onUpdate({ billing_type: t })}
              className={clsx(
                'text-xs font-semibold px-4 py-2 rounded-lg border transition-colors',
                billingType === t
                  ? 'bg-[--accent] text-white border-[--accent]'
                  : 'bg-white text-gray-600 border-[--veil] hover:border-[--accent]',
              )}
            >
              {TYPE_LABELS[t]}
            </button>
          ))}
        </div>
        <span className="ml-auto text-[10px] text-gray-400">
          Billing type affects chain completion rules
        </span>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <KpiCard
          label="PO Total"
          value={`₹${total.toLocaleString('en-IN')}`}
          sub={billingType === 'staged' ? `${milestones.length} milestones` : 'Single invoice expected'}
          variant="neutral"
        />
        <KpiCard
          label="Billed So Far"
          value={`₹${billedSoFar.toLocaleString('en-IN')}`}
          sub={`${billedPct}% · ${stages.length} invoice${stages.length !== 1 ? 's' : ''}`}
          variant={billedPct >= 100 ? 'ok' : billedPct > 0 ? 'warn' : 'neutral'}
        />
        <KpiCard
          label="Outstanding"
          value={`₹${outstanding.toLocaleString('en-IN')}`}
          sub={outstanding === 0 ? 'Fully billed ✓' : 'Remaining to bill'}
          variant={outstanding === 0 ? 'ok' : outstanding === total ? 'bad' : 'warn'}
        />
      </div>

      {/* Progress bar */}
      <div className="mb-5">
        <div className="h-2 bg-[--veil] rounded-full overflow-hidden">
          <div
            className={clsx('h-full rounded-full transition-all', billedPct >= 100 ? 'bg-green-500' : 'bg-[--accent]')}
            style={{ width: `${Math.min(100, billedPct)}%` }}
          />
        </div>
        <div className="text-[10px] text-gray-400 mt-1 text-right">
          ₹{billedSoFar.toLocaleString('en-IN')} of ₹{total.toLocaleString('en-IN')} billed
        </div>
      </div>

      {/* FULL view */}
      {billingType === 'full' && (
        <div className="bg-white border border-[--veil] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-[--veil]">
                {['Document', 'Ref Number', 'Amount', 'Stage', 'Status'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wide text-gray-500">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stages.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-sm text-gray-400">
                    No invoices uploaded yet
                  </td>
                </tr>
              )}
              {stages.map((s, i) => (
                <tr key={i} className="border-b border-gray-50 last:border-0">
                  <td className="px-4 py-3 text-gray-700">Invoice {s.stage}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">—</td>
                  <td className="px-4 py-3 font-semibold">₹{s.invoiced_amount.toLocaleString('en-IN')}</td>
                  <td className="px-4 py-3 text-gray-500">Stage {s.stage}</td>
                  <td className="px-4 py-3">
                    <span className={clsx('text-[9px] font-bold px-2 py-1 rounded-full', STATUS_TAG[s.status] ?? STATUS_TAG.pending)}>
                      {s.status.charAt(0).toUpperCase() + s.status.slice(1)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* STAGED view */}
      {billingType === 'staged' && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-gray-500 uppercase tracking-wide">
              Milestones ({milestones.length})
            </span>
            {!editingMilestones && (
              <button
                onClick={() => { setDraftMilestones(milestones.map(toDraft)); setEditingMilestones(true); }}
                className="text-xs font-semibold text-[--accent] hover:underline"
              >
                ✏ Edit milestones
              </button>
            )}
          </div>

          {editingMilestones && (
            <div className="bg-[#eef2ff] border border-[#c7d2fe] rounded-xl p-4 mb-4">
              <div className="space-y-2 mb-3">
                {draftMilestones.map(m => (
                  <div key={m._id} className="grid grid-cols-[2fr_1fr_2fr_auto] gap-2 items-center">
                    <input
                      className="border border-[--veil] rounded-lg px-2 py-1.5 text-xs"
                      placeholder="Milestone name"
                      value={m.name}
                      onChange={e => updateDraft(m._id, 'name', e.target.value)}
                    />
                    <input
                      className="border border-[--veil] rounded-lg px-2 py-1.5 text-xs"
                      placeholder="% e.g. 30"
                      type="number"
                      min={0}
                      max={100}
                      value={m.percentage}
                      onChange={e => updateDraft(m._id, 'percentage', Number(e.target.value))}
                    />
                    <input
                      className="border border-[--veil] rounded-lg px-2 py-1.5 text-xs"
                      placeholder="Trigger (e.g. On delivery)"
                      value={m.trigger}
                      onChange={e => updateDraft(m._id, 'trigger', e.target.value)}
                    />
                    <button onClick={() => removeDraft(m._id)} className="text-red-400 hover:text-red-600 px-1 text-sm">✕</button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={addMilestone}
                  className="text-xs font-semibold text-[--accent] border border-[--accent] px-3 py-1.5 rounded-lg hover:bg-[--accent] hover:text-white transition-colors"
                >
                  + Add milestone
                </button>
                <button
                  onClick={saveMilestones}
                  className="text-xs font-semibold bg-[--accent] text-white px-3 py-1.5 rounded-lg hover:bg-[--accent]/90 transition-colors"
                >
                  Save
                </button>
                <button onClick={() => setEditingMilestones(false)} className="text-xs text-gray-500 px-3 py-1.5">
                  Cancel
                </button>
              </div>
            </div>
          )}

          {milestones.length === 0 && !editingMilestones && (
            <div className="bg-white border border-[--veil] rounded-xl p-6 text-center text-sm text-gray-400">
              No milestones defined yet.{' '}
              <button
                onClick={() => { setDraftMilestones([]  ); setEditingMilestones(true); }}
                className="text-[--accent] font-semibold hover:underline"
              >
                Set up milestones
              </button>
            </div>
          )}

          {milestones.length > 0 && !editingMilestones && (
            <div className="bg-white border border-[--veil] rounded-xl overflow-hidden">
              <div className="grid grid-cols-[2fr_1fr_1fr_1.5fr_1fr] gap-0 bg-gray-50 border-b border-[--veil] px-4 py-2.5">
                {['Milestone', '% / Amount', 'Expected', 'Invoice Ref', 'Status'].map(h => (
                  <div key={h} className="text-[10px] font-bold uppercase tracking-wide text-gray-500">{h}</div>
                ))}
              </div>
              {milestones.map((m, i) => {
                const stage  = stages[i];
                const amt    = total * (m.percentage / 100);
                const status = stage?.status ?? 'pending';
                return (
                  <div
                    key={i}
                    className={clsx(
                      'grid grid-cols-[2fr_1fr_1fr_1.5fr_1fr] gap-0 px-4 py-3 border-b border-gray-50 last:border-0',
                      status === 'mismatch' && 'bg-red-50',
                      status === 'pending'  && 'bg-amber-50/30',
                    )}
                  >
                    <div>
                      <div className="text-sm font-semibold text-[--ink]">{m.name || `Milestone ${i + 1}`}</div>
                      <div className="text-[10px] text-gray-400">{m.trigger}</div>
                    </div>
                    <div>
                      <div className="font-mono text-xs font-semibold">₹{Math.round(amt).toLocaleString('en-IN')}</div>
                      <div className="text-[9px] text-gray-400">{m.percentage}%</div>
                    </div>
                    <div className="text-xs text-gray-500">{m.due_date ?? '—'}</div>
                    <div className="font-mono text-[10px] text-gray-600">
                      {stage ? `Stage ${stage.stage}` : '— Not uploaded'}
                    </div>
                    <div>
                      <span className={clsx('text-[9px] font-bold px-2 py-1 rounded-full', STATUS_TAG[status] ?? STATUS_TAG.pending)}>
                        {status.charAt(0).toUpperCase() + status.slice(1)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <p className="text-[10px] text-gray-400 mt-2">
            💡 Milestone amounts are calculated as PO total × percentage.
          </p>
        </div>
      )}

      {/* RECURRING view */}
      {billingType === 'recurring' && (
        <div className="bg-white border border-[--veil] rounded-xl p-8 text-center text-gray-400">
          <div className="text-2xl mb-2">📅</div>
          <div className="text-sm font-semibold text-gray-500 mb-1">Recurring billing</div>
          <div className="text-xs">Monthly / quarterly invoice cadence for AMC and service contracts. Configure in a future release.</div>
        </div>
      )}
    </div>
  );
}
