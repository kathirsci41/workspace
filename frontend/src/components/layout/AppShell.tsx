import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { TopBar } from './TopBar';

export interface Breadcrumb {
  label: string;
  href?: string;
}

export function AppShell({
  bundleId,
  title,
  subtitle,
  breadcrumbs = [],
  actions,
  children,
}: {
  bundleId?: string;
  title: string;
  subtitle?: ReactNode;
  breadcrumbs?: Breadcrumb[];
  actions?: ReactNode;
  children: ReactNode;
}) {
  const bundleLabel = bundleId ? breadcrumbs.find((crumb) => crumb.label !== 'Bundles')?.label ?? title : undefined;

  return (
    <div className="app-shell">
      <TopBar bundleId={bundleId} bundleLabel={bundleLabel} />
      <main className="main-content">
        <nav className="breadcrumbs" aria-label="Breadcrumb">
          {breadcrumbs.map((crumb, index) => (
            crumb.href ? (
              <Link key={`${crumb.label}-${index}`} to={crumb.href}>{crumb.label}</Link>
            ) : (
              <span key={`${crumb.label}-${index}`}>{crumb.label}</span>
            )
          ))}
        </nav>
        <header className={`page-header ${bundleId ? 'workspace-header' : ''}`}>
          <div>
            <h1>{title}</h1>
            {subtitle ? <div className="page-header__subtitle">{subtitle}</div> : null}
          </div>
          {actions ? <div className="page-header__actions">{actions}</div> : null}
        </header>
        {children}
      </main>
    </div>
  );
}
