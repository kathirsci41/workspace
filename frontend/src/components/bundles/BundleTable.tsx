import { Link } from 'react-router-dom';
import { DataTable } from '../common/DataTable';
import { StatusBadge } from '../common/StatusBadge';
import { bundleStatus } from '../../lib/build1';
import { formatDateTime } from '../../lib/format';
import type { OrderBundle } from '../../types/api';

export function BundleTable({
  bundles,
  deletingBundleId = null,
  onDelete,
}: {
  bundles: OrderBundle[];
  deletingBundleId?: string | null;
  onDelete?: (bundle: OrderBundle) => void;
}) {
  return (
    <DataTable label="Bundles table" className="bundles-table">
      <thead>
        <tr>
          <th>Bundle</th>
          <th>Customer</th>
          <th>Customer PO</th>
          <th>SO No</th>
          <th>Status</th>
          <th>Updated</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {bundles.map((bundle) => (
          <tr key={bundle.id}>
            <td>
              <strong>{bundle.bundle_number}</strong>
            </td>
            <td>{bundle.customer_name || '-'}</td>
            <td>{bundle.customer_po_no || '-'}</td>
            <td>{bundle.so_no || '-'}</td>
            <td><StatusBadge status={bundleStatus(bundle)} /></td>
            <td>{formatDateTime(bundle.updated_at)}</td>
            <td>
              <div className="button-row">
                <Link className="button button--ghost" to={`/bundles/${bundle.id}/overview`} aria-label={`Open Bundle ${bundle.bundle_number}`}>
                  Open
                </Link>
                {onDelete ? (
                  <button
                    className="button button--danger"
                    type="button"
                    aria-label={`Delete Bundle ${bundle.bundle_number}`}
                    disabled={deletingBundleId === bundle.id}
                    onClick={() => onDelete(bundle)}
                  >
                    {deletingBundleId === bundle.id ? 'Deleting...' : 'Delete'}
                  </button>
                ) : null}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
