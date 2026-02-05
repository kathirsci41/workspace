import { X, Filter } from 'lucide-react';
import { DOCUMENT_TYPE_LABELS, SO_DOCUMENT_TYPES } from '../../types';

interface FiltersProps {
  typeFilter: string;
  monthFilter: string;
  onTypeChange: (type: string) => void;
  onMonthChange: (month: string) => void;
  onClear: () => void;
  availableMonths: string[];
}

export default function Filters({
  typeFilter,
  monthFilter,
  onTypeChange,
  onMonthChange,
  onClear,
  availableMonths,
}: FiltersProps) {
  const hasFilters = typeFilter || monthFilter;

  return (
    <div className="bg-gray-50 border-b border-gray-200 px-6 py-3">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Filter className="h-4 w-4" />
          <span>Filters:</span>
        </div>

        {/* Document Type Filter */}
        <select
          value={typeFilter}
          onChange={(e) => onTypeChange(e.target.value)}
          className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          <option value="">All Types</option>
          {SO_DOCUMENT_TYPES.map((type) => (
            <option key={type} value={type}>
              {DOCUMENT_TYPE_LABELS[type]}
            </option>
          ))}
        </select>

        {/* Month Filter */}
        <select
          value={monthFilter}
          onChange={(e) => onMonthChange(e.target.value)}
          className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          <option value="">All Months</option>
          {availableMonths.map((month) => (
            <option key={month} value={month}>
              {formatMonth(month)}
            </option>
          ))}
        </select>

        {/* Clear Filters */}
        {hasFilters && (
          <button
            onClick={onClear}
            className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md"
          >
            <X className="h-4 w-4" />
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

function formatMonth(monthStr: string): string {
  const [year, month] = monthStr.split('-');
  const date = new Date(parseInt(year), parseInt(month) - 1);
  return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}
