import type { ReactNode } from 'react';

export function DataTable({ children, label, className = '' }: { children: ReactNode; label: string; className?: string }) {
  return (
    <div className="data-table-wrap">
      <table className={`data-table ${className}`.trim()} aria-label={label}>
        {children}
      </table>
    </div>
  );
}
