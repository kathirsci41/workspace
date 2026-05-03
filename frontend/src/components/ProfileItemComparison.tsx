import { CheckCircle2, XCircle, MinusCircle, AlertTriangle, Sparkles } from 'lucide-react';
import type { ItemComparison, ItemMatch } from '@/types';

interface Props {
  comparisons: ItemComparison[];
  matches?: ItemMatch[];
}

function MatchIcon({ match }: { match: boolean | null }) {
  if (match === true)  return <CheckCircle2 size={14} className="text-green-500 shrink-0" />;
  if (match === false) return <XCircle       size={14} className="text-red-500   shrink-0" />;
  return               <MinusCircle          size={14} className="text-gray-300   shrink-0" />;
}

function docLabel(raw: string) {
  return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatQty(v: number | null | undefined): string {
  if (v == null) return '—';
  return v % 1 === 0 ? String(v) : v.toFixed(2);
}

function ConfidenceBadge({ confidence, matchType }: { confidence: number; matchType: string }) {
  if (matchType === 'exact') {
    return <span className="text-green-600 text-xs font-medium">Exact</span>;
  }
  if (matchType === 'unmatched') {
    return <span className="text-gray-400 text-xs italic">No match</span>;
  }
  const pct = Math.round(confidence * 100);
  const colour = pct >= 80 ? 'text-blue-600' : pct >= 50 ? 'text-amber-600' : 'text-red-500';
  return (
    <span className={`flex items-center gap-0.5 text-xs font-medium ${colour}`}>
      <Sparkles size={10} />
      {pct}%
    </span>
  );
}

function groupByPair(comparisons: ItemComparison[]): Map<string, ItemComparison[]> {
  const map = new Map<string, ItemComparison[]>();
  for (const c of comparisons) {
    const key = `${c.source_doc}→${c.compared_doc}`;
    const group = map.get(key) ?? [];
    group.push(c);
    map.set(key, group);
  }
  return map;
}

export function ProfileItemComparison({ comparisons, matches = [] }: Props) {
  const hasComparisons = comparisons && comparisons.length > 0;
  const hasMatches = matches && matches.length > 0;
  if (!hasComparisons && !hasMatches) return null;

  const mismatches = comparisons.filter((c) => c.qty_match === false).length;
  const matchCount = comparisons.filter((c) => c.qty_match === true).length;
  const groups = groupByPair(comparisons);

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Item-Level Verification
        </h3>
        <div className="flex items-center gap-3 text-xs">
          {matchCount > 0 && (
            <span className="flex items-center gap-1 text-green-600">
              <CheckCircle2 size={12} /> {matchCount} match
            </span>
          )}
          {mismatches > 0 && (
            <span className="flex items-center gap-1 text-red-600">
              <XCircle size={12} /> {mismatches} mismatch
            </span>
          )}
        </div>
      </div>

      {/* Qty comparison tables grouped by doc pair */}
      {hasComparisons && Array.from(groups.entries()).map(([pairKey, rows]) => {
        const [srcDoc, cmpDoc] = pairKey.split('→');
        return (
          <div key={pairKey} className="space-y-1">
            <div className="text-xs font-medium text-gray-500 pb-1 border-b border-gray-100">
              {docLabel(srcDoc)} → {docLabel(cmpDoc)}
            </div>

            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-400 text-left">
                  <th className="py-1 pr-2 font-medium w-10">#</th>
                  <th className="py-1 pr-2 font-medium">Description</th>
                  <th className="py-1 pr-2 font-medium">Part No</th>
                  <th className="py-1 pr-2 font-medium text-right">{docLabel(srcDoc)} Qty</th>
                  <th className="py-1 pr-2 font-medium text-right">{docLabel(cmpDoc)} Qty</th>
                  <th className="py-1 font-medium text-center w-8">OK</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {rows.map((row, i) => {
                  const isWarning = row.sr_no === null && row.qty_match === false;
                  if (isWarning) {
                    return (
                      <tr key={i} className="bg-amber-50">
                        <td colSpan={6} className="py-2 px-1">
                          <span className="flex items-center gap-1.5 text-amber-700">
                            <AlertTriangle size={13} />
                            {row.description}
                          </span>
                        </td>
                      </tr>
                    );
                  }
                  return (
                    <tr key={i} className={row.qty_match === false ? 'bg-red-50' : ''}>
                      <td className="py-1.5 pr-2 text-gray-400 font-mono">{row.sr_no ?? i + 1}</td>
                      <td className="py-1.5 pr-2 text-gray-700 max-w-[200px] truncate">
                        {row.description ?? '—'}
                      </td>
                      <td className="py-1.5 pr-2 text-gray-500 font-mono">{row.part_no ?? '—'}</td>
                      <td className="py-1.5 pr-2 text-right font-mono text-gray-700">
                        {formatQty(row.source_qty)}
                      </td>
                      <td className={`py-1.5 pr-2 text-right font-mono ${row.qty_match === false ? 'text-red-600 font-semibold' : 'text-gray-700'}`}>
                        {formatQty(row.compared_qty)}
                      </td>
                      <td className="py-1.5 text-center">
                        <MatchIcon match={row.qty_match} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })}

      {/* AI part-number matching section */}
      {hasMatches && (
        <div className="space-y-1">
          <div className="text-xs font-medium text-gray-500 pb-1 border-b border-gray-100 flex items-center gap-1">
            <Sparkles size={11} className="text-blue-500" />
            Customer PO → Company PO Part Match (AI)
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-400 text-left">
                <th className="py-1 pr-2 font-medium w-10">#</th>
                <th className="py-1 pr-2 font-medium">Customer Description</th>
                <th className="py-1 pr-2 font-medium">Matched Part No</th>
                <th className="py-1 font-medium text-right">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {matches.map((m, i) => (
                <tr key={i} className={m.match_type === 'unmatched' ? 'bg-gray-50' : ''}>
                  <td className="py-1.5 pr-2 text-gray-400 font-mono">{m.sr_no ?? i + 1}</td>
                  <td className="py-1.5 pr-2 text-gray-700 max-w-[220px] truncate">
                    {m.description ?? '—'}
                  </td>
                  <td className="py-1.5 pr-2 font-mono text-gray-600">
                    {m.matched_part_no ?? <span className="text-gray-300 italic">—</span>}
                  </td>
                  <td className="py-1.5 text-right">
                    <ConfidenceBadge confidence={m.confidence} matchType={m.match_type} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
