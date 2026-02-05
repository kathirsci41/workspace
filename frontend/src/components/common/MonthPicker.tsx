import { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface MonthPickerProps {
  value: string;
  onChange: (value: string) => void;
}

export default function MonthPicker({ value, onChange }: MonthPickerProps) {
  const currentDate = value ? new Date(value + '-01') : new Date();
  const [viewYear, setViewYear] = useState(currentDate.getFullYear());

  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
  ];

  const handleMonthClick = (monthIndex: number) => {
    const month = String(monthIndex + 1).padStart(2, '0');
    onChange(`${viewYear}-${month}`);
  };

  const selectedMonth = value ? parseInt(value.split('-')[1]) - 1 : -1;
  const selectedYear = value ? parseInt(value.split('-')[0]) : -1;

  return (
    <div className="w-full">
      {/* Year navigation */}
      <div className="flex items-center justify-between mb-4">
        <button
          type="button"
          onClick={() => setViewYear(viewYear - 1)}
          className="p-1 hover:bg-gray-100 rounded-full"
        >
          <ChevronLeft className="h-5 w-5 text-gray-600" />
        </button>
        <span className="font-semibold text-gray-900">{viewYear}</span>
        <button
          type="button"
          onClick={() => setViewYear(viewYear + 1)}
          className="p-1 hover:bg-gray-100 rounded-full"
        >
          <ChevronRight className="h-5 w-5 text-gray-600" />
        </button>
      </div>

      {/* Month grid */}
      <div className="grid grid-cols-4 gap-2">
        {months.map((month, index) => (
          <button
            key={month}
            type="button"
            onClick={() => handleMonthClick(index)}
            className={`px-3 py-2 text-sm rounded-md transition-colors ${
              selectedMonth === index && selectedYear === viewYear
                ? 'bg-primary-600 text-white'
                : 'hover:bg-gray-100 text-gray-700'
            }`}
          >
            {month}
          </button>
        ))}
      </div>

      {/* Display selected value */}
      {value && (
        <div className="mt-4 text-center text-sm text-gray-600">
          Selected: {formatMonth(value)}
        </div>
      )}
    </div>
  );
}

function formatMonth(monthStr: string): string {
  const [year, month] = monthStr.split('-');
  const date = new Date(parseInt(year), parseInt(month) - 1);
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}
