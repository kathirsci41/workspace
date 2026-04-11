interface Stage {
  stage: number;
  expected_amount: number;
  invoiced_amount: number;
  status: string;
}

interface Props {
  billing: { overall: string; stages?: Stage[] };
  poTotal?: number | null;
  billingType: string;
  currency?: string;
}

const BAR_COLOR: Record<string, string> = {
  complete: 'bg-green-600',
  paid:     'bg-green-600',
  partial:  'bg-yellow-500',
  pending:  'bg-slate-700',
  mismatch: 'bg-red-600',
};

const OVERALL_CLASS: Record<string, string> = {
  complete: 'bg-green-950 text-green-400',
  partial:  'bg-yellow-950 text-yellow-400',
  pending:  'bg-slate-900 text-slate-400',
  mismatch: 'bg-red-950 text-red-400',
};

export function BillingCompletenessPanel({ billing, poTotal, billingType, currency = '₹' }: Props) {
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-400 uppercase tracking-wide">
          {billingType} Billing
        </span>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${OVERALL_CLASS[billing.overall] ?? OVERALL_CLASS.pending}`}>
          {(billing.overall ?? 'pending').toUpperCase()}
        </span>
      </div>

      {billing.stages?.map((s) => (
        <div key={s.stage} className="mb-3">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-slate-400">Stage {s.stage}</span>
            <span className="text-slate-300">
              {currency}{s.invoiced_amount.toLocaleString('en-IN')} / {currency}{s.expected_amount.toLocaleString('en-IN')}
            </span>
          </div>
          <div className="h-1.5 bg-slate-800 rounded overflow-hidden">
            <div
              className={`h-full rounded ${BAR_COLOR[s.status] ?? BAR_COLOR.pending}`}
              style={{
                width: s.expected_amount > 0
                  ? `${Math.min(100, (s.invoiced_amount / s.expected_amount) * 100)}%`
                  : '0%'
              }}
            />
          </div>
        </div>
      ))}

      {poTotal != null && (
        <div className="flex justify-between text-xs pt-2 border-t border-slate-800 mt-2">
          <span className="text-slate-500">PO Total</span>
          <span className="text-slate-200 font-semibold">
            {currency}{poTotal.toLocaleString('en-IN')}
          </span>
        </div>
      )}
    </div>
  );
}
