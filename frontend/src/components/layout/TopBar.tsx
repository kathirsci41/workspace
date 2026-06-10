import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

export function TopBar({
  bundleId,
  bundleLabel,
  actions,
}: {
  bundleId?: string;
  bundleLabel?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="topbar">
      <Link className="topbar__brand" to="/bundles" aria-label="Order Assurance bundles">
        <span className="topbar__mark">OA</span>
        <span>
          <strong>Order Assurance</strong>
          <em>Build 1</em>
        </span>
      </Link>
      <div className="topbar__search" role="search">
        <label className="visually-hidden" htmlFor="global-search">Search</label>
        <input id="global-search" type="search" placeholder="Search bundles, documents, references" />
      </div>
      <div className="topbar__meta">
        {bundleId && bundleLabel ? (
          <Link className="topbar__bundle-context" to={`/bundles/${bundleId}/overview`}>
            <span>Current bundle</span>
            <strong>{bundleLabel}</strong>
          </Link>
        ) : null}
        {actions}
        <details className="topbar-more">
          <summary className="button button--ghost button--small">More</summary>
          <div className="topbar-more__items">
            {bundleId ? <Link to={`/bundles/${bundleId}/audit`}>Manual Correction History</Link> : null}
            <Link to="/health">System Health</Link>
          </div>
        </details>
      </div>
    </header>
  );
}
