import { useState } from 'react';
import type { PurchaseOrder } from '@/types';
import clsx from 'clsx';

type Scenario    = PurchaseOrder['order_scenario'];
type BillingType = NonNullable<PurchaseOrder['billing_type']>;

interface Props {
  scenario: Scenario;
  billingType: BillingType;
  billedSoFar: number;
  milestoneCount: number;
  poTotal: number | null;
  onScenarioChange: (val: Scenario) => void;
  onBillingTypeChange: (val: BillingType) => void;
}

const SCENARIOS: Array<{ value: Scenario; icon: string; label: string; desc: string }> = [
  { value: 'stock',       icon: '🏭', label: 'STOCK',       desc: 'From warehouse inventory' },
  { value: 'procurement', icon: '📦', label: 'PROCUREMENT',  desc: 'Vendor order on demand'   },
  { value: 'drop_ship',   icon: '🚚', label: 'DROP-SHIP',    desc: 'Vendor ships direct'       },
  { value: 'service_amc', icon: '🔧', label: 'SERVICE/AMC',  desc: 'Service contract'          },
];

const BILLING_TYPES: Array<{ value: BillingType; label: string }> = [
  { value: 'full',      label: 'Full'      },
  { value: 'staged',    label: 'Staged'    },
  { value: 'recurring', label: 'Recurring' },
];

export default function OrderSettingsCard({
  scenario, billingType, billedSoFar, milestoneCount, poTotal,
  onScenarioChange, onBillingTypeChange,
}: Props) {
  const [scenarioOpen, setScenarioOpen] = useState(false);

  const currentScenario = SCENARIOS.find(s => s.value === scenario);
  const billedPct = poTotal && poTotal > 0
    ? Math.round((billedSoFar / poTotal) * 100)
    : 0;

  return (
    <div className="bg-white border border-[--veil] rounded-xl p-4 mb-5 grid grid-cols-2 gap-6">

      {/* ── Scenario ── */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2">
          Order Scenario
        </div>
        <div className="flex items-center gap-2">
          <div className="flex-1 flex items-center gap-2 bg-gray-50 border border-[--veil] rounded-lg px-3 py-2 text-sm font-semibold text-[--ink]">
            {currentScenario?.icon ?? '❓'} {currentScenario?.label ?? scenario.toUpperCase()}
            <span className="ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
              AUTO
            </span>
          </div>
          <button
            onClick={() => setScenarioOpen(v => !v)}
            className="text-xs font-semibold text-[--accent] whitespace-nowrap hover:underline"
          >
            Change ▾
          </button>
        </div>
        {scenarioOpen && (
          <div className="grid grid-cols-2 gap-1.5 mt-2">
            {SCENARIOS.map(s => (
              <button
                key={s.value}
                onClick={() => { onScenarioChange(s.value); setScenarioOpen(false); }}
                className={clsx(
                  'text-left border rounded-lg px-3 py-2 text-xs transition-colors',
                  scenario === s.value
                    ? 'border-[--accent] bg-[#eef2ff] font-semibold text-[--accent]'
                    : 'border-[--veil] bg-white hover:border-[--accent] hover:bg-[#eef2ff]',
                )}
              >
                <div className="font-bold">{s.icon} {s.label}</div>
                <div className="text-[9px] text-gray-400 mt-0.5">{s.desc}</div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Billing Type ── */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2">
          Billing Type
        </div>
        <div className="flex gap-1.5 mb-2">
          {BILLING_TYPES.map(bt => (
            <button
              key={bt.value}
              onClick={() => onBillingTypeChange(bt.value)}
              className={clsx(
                'flex-1 text-xs font-semibold py-2 rounded-lg border transition-colors',
                billingType === bt.value
                  ? 'bg-[--accent] text-white border-[--accent]'
                  : 'bg-white text-gray-600 border-[--veil] hover:border-[--accent]',
              )}
            >
              {bt.label}
            </button>
          ))}
        </div>
        <div className="text-[10px] text-gray-400">
          {billingType === 'staged' && milestoneCount > 0
            ? `${milestoneCount} milestones · ₹${billedSoFar.toLocaleString('en-IN')} billed (${billedPct}%)`
            : billingType === 'staged'
            ? 'No milestones defined — go to Billing tab to set up'
            : `₹${billedSoFar.toLocaleString('en-IN')} billed so far`}
        </div>
      </div>

    </div>
  );
}
