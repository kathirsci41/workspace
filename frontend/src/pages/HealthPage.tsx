import { getHealth } from '../api/health';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { StatusBadge } from '../components/common/StatusBadge';
import { AppShell } from '../components/layout/AppShell';
import { useAsyncResource } from '../hooks/useAsyncResource';

export function HealthPage() {
  const health = useAsyncResource(getHealth, []);

  return (
    <AppShell
      title="Health"
      subtitle="Internal backend status and exposed OCR details."
      breadcrumbs={[{ label: 'Health' }]}
    >
      <ErrorState message={health.error} />
      {health.isLoading ? <LoadingState label="Checking backend health..." /> : null}
      {health.data ? (
        <section className="panel">
          <div className="section-header">
            <h2>Backend</h2>
            <StatusBadge status={health.data.status === 'ok' ? 'PASS' : 'BLOCKED'} />
          </div>
          <dl className="detail-list">
            <div>
              <dt>Service</dt>
              <dd>{health.data.service}</dd>
            </div>
            {health.data.ocr ? (
              <>
                <div>
                  <dt>OCR provider</dt>
                  <dd>{String(health.data.ocr.provider ?? '-')}</dd>
                </div>
                <div>
                  <dt>OCR model</dt>
                  <dd>{String(health.data.ocr.model ?? '-')}</dd>
                </div>
                <div>
                  <dt>OCR reachable</dt>
                  <dd>{health.data.ocr.reachable === undefined ? '-' : String(health.data.ocr.reachable)}</dd>
                </div>
              </>
            ) : null}
          </dl>
        </section>
      ) : null}
    </AppShell>
  );
}
