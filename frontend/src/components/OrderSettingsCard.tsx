import { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import type { PurchaseOrder } from '@/types';
import clsx from 'clsx';

type Scenario    = PurchaseOrder['order_scenario'];
type BillingType = NonNullable<PurchaseOrder['billing_type']>;
type GstType     = PurchaseOrder['gst_type'];

interface Props {
  scenario: Scenario;
  billingType: BillingType;
  billedSoFar: number;
  milestoneCount: number;
  poTotal: number | null;
  gstType: GstType;
  invoiceSplit: boolean;
  itemsVerified: boolean;
  onScenarioChange: (val: Scenario) => void;
  onBillingTypeChange: (val: BillingType) => void;
  onGstTypeChange: (val: GstType) => void;
  onInvoiceSplitChange: (val: boolean) => void;
  onItemsVerifiedChange: (val: boolean) => void;
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

const GST_OPTIONS: Array<{ value: GstType; label: string }> = [
  { value: 'unknown',   label: '—'         },
  { value: 'igst',      label: 'IGST'      },
  { value: 'cgst_sgst', label: 'CGST+SGST' },
];

export default function OrderSettingsCard({
  scenario, billingType, billedSoFar, milestoneCount, poTotal,
  gstType, invoiceSplit, itemsVerified,
  onScenarioChange, onBillingTypeChange, onGstTypeChange,
  onInvoiceSplitChange, onItemsVerifiedChange,
}: Props) {
  const [scenarioOpen, setScenarioOpen] = useState(false);

  const currentScenario = SCENARIOS.find(s => s.value === scenario);
  const billedPct = poTotal && poTotal > 0
    ? Math.round((billedSoFar / poTotal) * 100)
    : 0;

  const handleBillingTypeChange = (newType: BillingType) => {
    if (newType === billingType) return;
    const hasInvoices = billedSoFar > 0;
    if (hasInvoices) {
      const ok = window.confirm(
        `Changing billing type from "${billingType}" to "${newType}" will recalculate chain completeness using a different formula. This may change the displayed completion percentage. Continue?`
      );
      if (!ok) return;
    }
    onBillingTypeChange(newType);
  };

  return (
    <div className="bg-white border border-[--veil] rounded-xl p-4 mb-5 space-y-4">

      {/* ── Row 1: Scenario + Billing Type ── */}
      <div className="grid grid-cols-2 gap-6">

        {/* Scenario */}
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

        {/* Billing Type */}
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2">
            Billing Type
          </div>
          <div className="flex gap-1.5 mb-2">
            {BILLING_TYPES.map(bt => (
              <button
                key={bt.value}
                onClick={() => handleBillingTypeChange(bt.value)}
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

      {/* ── Row 2: GST + Invoice Split + Items Verified ── */}
      <div className="flex items-center gap-6 pt-3 border-t border-[--veil] flex-wrap">

        {/* GST type */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wide text-gray-400">GST</span>
          {GST_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => onGstTypeChange(value)}
              className={clsx(
                'text-xs px-2.5 py-0.5 rounded-full font-medium border transition-colors',
                gstType === value
                  ? 'bg-indigo-100 text-indigo-700 border-indigo-300'
                  : 'bg-white text-gray-400 border-gray-200 hover:border-gray-300',
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Invoice split */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wide text-gray-400">Invoices</span>
          <button
            onClick={() => onInvoiceSplitChange(!invoiceSplit)}
            className={clsx(
              'text-xs px-2.5 py-0.5 rounded-full font-medium border transition-colors',
              invoiceSplit
                ? 'bg-orange-100 text-orange-700 border-orange-300'
                : 'bg-white text-gray-400 border-gray-200 hover:border-gray-300',
            )}
          >
            {invoiceSplit ? 'Split billing' : 'Single invoice'}
          </button>
        </div>

        {/* Items verified */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wide text-gray-400">Items</span>
          <button
            onClick={() => onItemsVerifiedChange(!itemsVerified)}
            className={clsx(
              'flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full font-medium border transition-colors',
              itemsVerified
                ? 'bg-green-100 text-green-700 border-green-300 hover:bg-green-200'
                : 'bg-gray-100 text-gray-500 border-gray-300 hover:bg-gray-200',
            )}
          >
            {itemsVerified && <CheckCircle2 size={11} />}
            {itemsVerified ? 'Items Verified' : 'Mark Verified'}
          </button>
        </div>
      </div>

    </div>
  );
}
