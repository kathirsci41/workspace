import { ChevronDown } from 'lucide-react';
import type { SalesOrder } from '../../types';

interface SOSelectorProps {
  salesOrders: SalesOrder[];
  selectedId?: number;
  onChange: (id: number | undefined) => void;
  placeholder?: string;
}

export default function SOSelector({
  salesOrders,
  selectedId,
  onChange,
  placeholder = 'Select a Sales Order...',
}: SOSelectorProps) {
  const selectedSO = salesOrders.find((so) => so.id === selectedId);

  return (
    <div className="relative">
      <select
        value={selectedId || ''}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : undefined)}
        className="w-full appearance-none px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
      >
        <option value="">{placeholder}</option>
        {salesOrders.map((so) => (
          <option key={so.id} value={so.id}>
            SO-{so.soNumber} ({formatMonth(so.soMonth)})
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
    </div>
  );
}

function formatMonth(monthStr: string): string {
  const [year, month] = monthStr.split('-');
  const date = new Date(parseInt(year), parseInt(month) - 1);
  return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}
