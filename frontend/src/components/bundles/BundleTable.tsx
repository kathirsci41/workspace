import { Link } from 'react-router-dom';
import { DataTable } from '../common/DataTable';
import { StatusBadge } from '../common/StatusBadge';
import { bundleStatus } from '../../lib/build1';
import { formatDateTime } from '../../lib/format';
import type { OrderBundle } from '../../types/api';

export function BundleTable({
  bundles,
  deletingBundleId = null,
  confirmDeleteId = null,
  onDelete,
  onConfirmDelete,
  onCancelDelete,
}: {
  bundles: OrderBundle[];
  deletingBundleId?: string | null;
  confirmDeleteId?: string | null;
  onDelete?: (bundle: OrderBundle) => void;
  onConfirmDelete?: (bundle: OrderBundle) => void;
  onCancelDelete?: () => void;
}) {
  return (
    <DataTable label="Orders table" className="bundles-table">
      <thead>
        <tr>
          <th>Order</th>
          <th>Customer</th>
          <th>Customer PO</th>
          <th>SO No</th>
          <th>Status</th>
          <th>Customer</th>
          <th>Vendor</th>
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
            <td><StatusBadge status={bundle.customer_delivery_status} /></td>
            <td><StatusBadge status={bundle.vendor_procurement_status} /></td>
            <td>{formatDateTime(bundle.updated_at)}</td>
            <td>
              <div className="button-row">
                <Link className="button button--ghost" to={`/bundles/${bundle.id}/overview`} aria-label={`Open Order ${bundle.bundle_number}`}>
                  Open
                </Link>
                {onDelete && confirmDeleteId === bundle.id ? (
                  <span className="inline-confirm">
                    <span className="inline-confirm__label">Delete {bundle.bundle_number}?</span>
                    <button className="button button--danger button--small" type="button" disabled={deletingBundleId === bundle.id} onClick={() => onConfirmDelete?.(bundle)}>
                      {deletingBundleId === bundle.id ? 'Deleting…' : 'Yes, delete'}
                    </button>
                    <button className="button button--ghost button--small" type="button" onClick={() => onCancelDelete?.()}>Cancel</button>
                  </span>
                ) : onDelete ? (
                  <button
                    className="button button--danger"
                    type="button"
                    aria-label={`Delete Bundle ${bundle.bundle_number}`}
                    disabled={deletingBundleId === bundle.id}
                    onClick={() => onDelete(bundle)}
                  >
                    Delete
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
