export interface ChainSlot {
  docType: string;
  label: string;
  state: 'verified' | 'mismatch' | 'received' | 'waiting' | 'cancelled';
  ref?: string;
  soNumber?: string;
  soExpected?: string;
}

interface Props {
  slots: ChainSlot[];
}

const STATE_CONFIG: Record<string, { icon: string; badgeClass: string; borderClass: string }> = {
  verified:  { icon: '✓', badgeClass: 'text-green-400 bg-green-950',   borderClass: 'border-green-700' },
  mismatch:  { icon: '✗', badgeClass: 'text-red-400 bg-red-950',      borderClass: 'border-red-700' },
  received:  { icon: '●', badgeClass: 'text-yellow-400 bg-yellow-950', borderClass: 'border-yellow-700' },
  waiting:   { icon: '○', badgeClass: 'text-slate-500 bg-slate-900',   borderClass: 'border-slate-700 border-dashed' },
  cancelled: { icon: '—', badgeClass: 'text-slate-600 bg-slate-900',   borderClass: 'border-slate-800' },
};

export function ChainTimeline({ slots }: Props) {
  return (
    <div className="flex flex-col">
      {slots.map((slot, i) => {
        const cfg = STATE_CONFIG[slot.state] ?? STATE_CONFIG.waiting;
        return (
          <div key={slot.docType} className="flex gap-4 relative">
            {i < slots.length - 1 && (
              <div className="absolute left-5 top-10 w-0.5 h-full bg-slate-800 z-0" />
            )}
            <div className={`w-10 h-10 rounded-full border-2 flex items-center justify-center z-10 text-sm font-bold flex-shrink-0 bg-slate-900 ${cfg.borderClass}`}>
              {cfg.icon}
            </div>
            <div className="flex-1 pb-5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-semibold text-slate-200">{slot.label}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${cfg.badgeClass}`}>
                  {slot.state.charAt(0).toUpperCase() + slot.state.slice(1)}
                </span>
              </div>
              {slot.ref ? (
                <div className={`border rounded px-3 py-2 text-xs bg-slate-950 ${cfg.borderClass}`}>
                  <span className="text-slate-200 font-medium">{slot.ref}</span>
                  {slot.soNumber && (
                    <span className="ml-2 text-slate-500">
                      SO:{' '}
                      <span className={slot.soNumber === slot.soExpected ? 'text-green-400' : 'text-red-400'}>
                        {slot.soNumber} {slot.soNumber === slot.soExpected ? '✓' : '✗'}
                      </span>
                    </span>
                  )}
                </div>
              ) : (
                <div className="border border-dashed border-slate-700 rounded px-3 py-2 text-xs text-slate-500 bg-slate-950">
                  Not yet uploaded
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
