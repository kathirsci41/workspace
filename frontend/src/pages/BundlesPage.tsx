import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createBundle, deleteBundle, listBundles } from '../api/bundles';
import { BundleTable } from '../components/bundles/BundleTable';
import { CreateBundleModal } from '../components/bundles/CreateBundleModal';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { KpiCard } from '../components/common/KpiCard';
import { LoadingState } from '../components/common/LoadingState';
import { AppShell } from '../components/layout/AppShell';
import { useAsyncResource } from '../hooks/useAsyncResource';
import { bundleQueueMetrics, bundleStatus, isAutomatedTestBundle } from '../lib/build1';
import type { OrderBundle } from '../types/api';

type StatusFilter = 'all' | 'needs_review' | 'verified' | 'mismatch' | 'missing';
type SortMode = 'updated_desc' | 'name_asc' | 'status';
const PAGE_SIZE = 10;

export function BundlesPage() {
  const navigate = useNavigate();
  const bundles = useAsyncResource<OrderBundle[]>(listBundles, []);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [sort, setSort] = useState<SortMode>('updated_desc');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deletingBundleId, setDeletingBundleId] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const queueBundles = useMemo(() => (bundles.data ?? []).filter((bundle) => !isAutomatedTestBundle(bundle)), [bundles.data]);
  const metrics = bundleQueueMetrics(queueBundles);
  const visibleBundles = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return [...queueBundles]
      .filter((bundle) => {
        const status = bundleStatus(bundle);
        const matchesFilter =
          filter === 'all'
          || (filter === 'needs_review' && status === 'REVIEW_REQUIRED')
          || (filter === 'verified' && ['OK', 'PASS', 'VERIFIED'].includes(status))
          || (filter === 'mismatch' && status === 'MISMATCH')
          || (filter === 'missing' && status === 'MISSING_DOCUMENTS');
        const haystack = `${bundle.bundle_number} ${bundle.customer_name ?? ''} ${bundle.customer_po_no ?? ''} ${bundle.so_no ?? ''}`.toLowerCase();
        return matchesFilter && (!normalizedQuery || haystack.includes(normalizedQuery));
      })
      .sort((left, right) => {
        if (sort === 'name_asc') return left.bundle_number.localeCompare(right.bundle_number);
        if (sort === 'status') return bundleStatus(left).localeCompare(bundleStatus(right));
        return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
      });
  }, [filter, query, queueBundles, sort]);
  const pageCount = Math.max(1, Math.ceil(visibleBundles.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageStart = (currentPage - 1) * PAGE_SIZE;
  const pagedBundles = visibleBundles.slice(pageStart, pageStart + PAGE_SIZE);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  async function handleCreate(bundleName: string) {
    if (!bundleName) return;
    setCreateError(null);
    setIsCreating(true);
    try {
      const created = await createBundle({ bundle_number: bundleName });
      setIsCreateOpen(false);
      navigate(`/bundles/${created.id}/overview`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsCreating(false);
    }
  }

  async function handleDelete(bundle: OrderBundle) {
    const confirmed = window.confirm(
      `Delete bundle ${bundle.bundle_number}? This removes the bundle and all uploaded documents. This cannot be undone.`,
    );
    if (!confirmed) return;

    setDeleteError(null);
    setDeletingBundleId(bundle.id);
    try {
      await deleteBundle(bundle.id);
      await bundles.reload();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingBundleId(null);
    }
  }

  return (
    <AppShell
      title="Bundles"
      subtitle="Work queue for document-based order verification cases."
      breadcrumbs={[{ label: 'Bundles' }]}
      actions={<button type="button" className="button button--primary" onClick={() => setIsCreateOpen(true)}>Create Bundle</button>}
    >
      <section className="kpi-grid" aria-label="Bundle KPIs">
        <KpiCard label="Total Bundles" value={metrics.total} tone="info" />
        <KpiCard label="Needs Review" value={metrics.needsReview} tone="warning" />
        <KpiCard label="Verified" value={metrics.verified} tone="success" />
        <KpiCard label="Mismatches" value={metrics.mismatches} tone="danger" />
        <KpiCard label="Missing Documents" value={metrics.missingDocuments} tone="danger" />
      </section>

      <section className="panel">
        <div className="controls-row">
          <label>
            Search bundles
            <input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Bundle, customer, PO, SO" />
          </label>
          <label>
            Filter
            <select value={filter} onChange={(event) => { setFilter(event.target.value as StatusFilter); setPage(1); }}>
              <option value="all">All</option>
              <option value="needs_review">Needs Review</option>
              <option value="verified">Verified</option>
              <option value="mismatch">Mismatch</option>
              <option value="missing">Missing Document</option>
            </select>
          </label>
          <label>
            Sort
            <select value={sort} onChange={(event) => { setSort(event.target.value as SortMode); setPage(1); }}>
              <option value="updated_desc">Recently updated</option>
              <option value="name_asc">Bundle name</option>
              <option value="status">Status</option>
            </select>
          </label>
        </div>

        {bundles.isLoading ? <LoadingState label="Loading bundles..." /> : null}
        <ErrorState message={bundles.error ?? deleteError} />
        {!bundles.isLoading && !bundles.error && visibleBundles.length === 0 ? (
          <EmptyState title="No bundles found" action={<button type="button" className="button button--primary" onClick={() => setIsCreateOpen(true)}>Create Bundle</button>}>
            Create a bundle to upload the five required documents and start verification.
          </EmptyState>
        ) : null}
        {visibleBundles.length > 0 ? (
          <>
            <BundleTable bundles={pagedBundles} deletingBundleId={deletingBundleId} onDelete={handleDelete} />
            <div className="pagination" aria-label="Bundle pagination">
              <span>Showing {pageStart + 1}-{Math.min(pageStart + PAGE_SIZE, visibleBundles.length)} of {visibleBundles.length} bundles</span>
              <div className="button-row">
                <button className="button button--ghost" type="button" aria-label="Previous page" disabled={currentPage === 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button>
                <span>Page {currentPage} of {pageCount}</span>
                <button className="button button--ghost" type="button" aria-label="Next page" disabled={currentPage === pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>Next</button>
              </div>
            </div>
          </>
        ) : null}
      </section>

      <CreateBundleModal
        isOpen={isCreateOpen}
        isCreating={isCreating}
        error={createError}
        onClose={() => setIsCreateOpen(false)}
        onCreate={handleCreate}
      />
    </AppShell>
  );
}
