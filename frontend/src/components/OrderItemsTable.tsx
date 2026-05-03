import { Plus, X } from 'lucide-react';

export type OrderItemRow = Record<string, string>;

interface OrderItemsTableProps {
  columns: string[];
  rows: OrderItemRow[];
  onChange: (rows: OrderItemRow[]) => void;
  readOnly?: boolean;
}

const COL_LABELS: Record<string, string> = {
  sr_no:            'Sr.No',
  part_no:          'Part No',
  description:      'Description',
  hsn_code:         'HSN',
  qty:              'Qty',
  uom:              'UOM',
  unit_price:       'Unit Price',
  total_price:      'Total',
  serial_numbers:   'Serial Nos',
  // Delivery locations
  region:           'Region',
  unit:             'Unit',
  branch:           'Branch',
  gstin_no:         'GSTIN No',
  asset_description:'Asset Description',
  employee_code:    'Emp Code',
  employee_name:    'Employee Name',
  contact_person:   'Contact Person',
  contact_no:       'Contact No',
  delivery_address: 'Delivery Address',
};

// Tailwind classes — define width per known column; unknown columns get auto width
const COL_WIDTHS: Record<string, string> = {
  sr_no:            'min-w-[2.5rem]',
  part_no:          'min-w-[7rem]',
  description:      'min-w-[14rem]',
  hsn_code:         'min-w-[5rem]',
  qty:              'min-w-[3.5rem]',
  uom:              'min-w-[3.5rem]',
  unit_price:       'min-w-[6rem]',
  total_price:      'min-w-[6rem]',
  serial_numbers:   'min-w-[9rem]',
  // Delivery locations — wider to prevent truncation
  region:           'min-w-[5rem]',
  unit:             'min-w-[4rem]',
  branch:           'min-w-[7rem]',
  gstin_no:         'min-w-[10rem]',
  asset_description:'min-w-[14rem]',
  employee_code:    'min-w-[6rem]',
  employee_name:    'min-w-[12rem]',
  contact_person:   'min-w-[10rem]',
  contact_no:       'min-w-[8rem]',
  delivery_address: 'min-w-[16rem]',
};

export function OrderItemsTable({ columns, rows, onChange, readOnly = false }: OrderItemsTableProps) {
  const addRow = () => {
    const empty: OrderItemRow = {};
    for (const col of columns) empty[col] = '';
    onChange([...rows, empty]);
  };

  const updateCell = (rowIdx: number, col: string, val: string) => {
    onChange(rows.map((r, i) => (i === rowIdx ? { ...r, [col]: val } : r)));
  };

  const deleteRow = (rowIdx: number) => {
    onChange(rows.filter((_, i) => i !== rowIdx));
  };

  if (rows.length === 0 && readOnly) {
    return <p className="text-xs text-gray-400 italic py-2">No data extracted.</p>;
  }

  return (
    <div>
      <div className="overflow-x-auto rounded border border-gray-200">
        <table className="min-w-max w-full text-xs border-collapse">
          <thead>
            <tr className="bg-gray-50">
              {columns.map((col) => (
                <th
                  key={col}
                  className={`px-2 py-1.5 text-left font-medium text-gray-500 border-b border-r border-gray-200 last:border-r-0 whitespace-nowrap ${COL_WIDTHS[col] ?? ''}`}
                >
                  {COL_LABELS[col] ?? col.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </th>
              ))}
              {!readOnly && <th className="w-8 border-b border-gray-200 bg-gray-50" />}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (readOnly ? 0 : 1)}
                  className="px-3 py-4 text-center text-xs text-gray-400 italic"
                >
                  No line items — click &quot;Add Row&quot; to add one.
                </td>
              </tr>
            ) : (
              rows.map((row, rowIdx) => (
                <tr key={rowIdx} className="hover:bg-gray-50/60 border-b border-gray-100 last:border-b-0">
                  {columns.map((col) => (
                    <td key={col} className="px-1 py-0.5 border-r border-gray-100 last:border-r-0">
                      {readOnly ? (
                        <span className="block px-1 py-1 text-gray-700">{row[col] ?? ''}</span>
                      ) : (
                        <input
                          type="text"
                          value={row[col] ?? ''}
                          onChange={(e) => updateCell(rowIdx, col, e.target.value)}
                          className="w-full px-1.5 py-1 rounded text-xs focus:ring-1 focus:ring-blue-400 focus:outline-none bg-transparent hover:bg-white focus:bg-white transition-colors"
                        />
                      )}
                    </td>
                  ))}
                  {!readOnly && (
                    <td className="px-1 py-0.5 text-center">
                      <button
                        type="button"
                        onClick={() => deleteRow(rowIdx)}
                        title="Remove row"
                        className="p-0.5 text-gray-300 hover:text-red-500 rounded transition-colors"
                      >
                        <X size={13} />
                      </button>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {!readOnly && (
        <button
          type="button"
          onClick={addRow}
          className="mt-1.5 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
        >
          <Plus size={13} /> Add Row
        </button>
      )}
    </div>
  );
}
