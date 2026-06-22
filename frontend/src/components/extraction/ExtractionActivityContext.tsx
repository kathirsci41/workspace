import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { getExtractionActivity } from '../../api/documents';
import type { BundleDocument, ExtractionActivityJob, ExtractionActivityResponse } from '../../types/api';

type LocalStage = 'reading' | 'running_ocr' | 'completed' | 'failed';

interface LocalExtractionJob {
  documentId: string;
  filename: string;
  stage: LocalStage;
  startedAt: number;
  error?: string;
}

interface ExtractionActivityContextValue {
  runExtraction: <T>(document: BundleDocument, request: () => Promise<T>) => Promise<T>;
  isExtracting: (documentId: string) => boolean;
  activityLabelForDocument: (documentId: string) => string | null;
  banner: BannerState | null;
}

interface BannerState {
  filename: string;
  label: string;
  elapsedMs: number;
  extraCount: number;
}

const idleActivity: ExtractionActivityResponse = {
  active: false,
  active_count: 0,
  queue_count: 0,
  active_jobs: [],
  queued_jobs: [],
};

const ExtractionActivityContext = createContext<ExtractionActivityContextValue | null>(null);

export function ExtractionActivityProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<LocalExtractionJob[]>([]);
  const [backendActivity, setBackendActivity] = useState<ExtractionActivityResponse>(idleActivity);
  const jobsRef = useRef<Map<string, LocalExtractionJob>>(new Map());
  const cleanupTimers = useRef<Map<string, number>>(new Map());

  const replaceJobs = useCallback(() => {
    setJobs(Array.from(jobsRef.current.values()));
  }, []);

  const removeJob = useCallback((documentId: string) => {
    const timer = cleanupTimers.current.get(documentId);
    if (timer) window.clearTimeout(timer);
    cleanupTimers.current.delete(documentId);
    jobsRef.current.delete(documentId);
    replaceJobs();
  }, [replaceJobs]);

  const setJob = useCallback((job: LocalExtractionJob) => {
    jobsRef.current.set(job.documentId, job);
    replaceJobs();
  }, [replaceJobs]);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const activity = await getExtractionActivity();
        if (!cancelled) setBackendActivity(activity);
      } catch {
        if (!cancelled) setBackendActivity(idleActivity);
      }
    }
    poll();
    const timer = window.setInterval(poll, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      cleanupTimers.current.forEach((cleanupTimer) => window.clearTimeout(cleanupTimer));
      cleanupTimers.current.clear();
    };
  }, []);

  const runExtraction = useCallback(async <T,>(document: BundleDocument, request: () => Promise<T>): Promise<T> => {
    if (jobsRef.current.has(document.id)) {
      throw new Error(`Extraction is already running for ${document.filename}.`);
    }
    setJob({
      documentId: document.id,
      filename: document.filename,
      stage: 'reading',
      startedAt: Date.now(),
    });
    try {
      const result = await request();
      setJob({
        documentId: document.id,
        filename: document.filename,
        stage: 'completed',
        startedAt: Date.now(),
      });
      cleanupTimers.current.set(document.id, window.setTimeout(() => removeJob(document.id), 250));
      return result;
    } catch (err) {
      setJob({
        documentId: document.id,
        filename: document.filename,
        stage: 'failed',
        startedAt: Date.now(),
        error: err instanceof Error ? err.message : String(err),
      });
      cleanupTimers.current.set(document.id, window.setTimeout(() => removeJob(document.id), 2500));
      throw err;
    }
  }, [removeJob, setJob]);

  const backendJobs = useMemo(
    () => [...backendActivity.active_jobs, ...backendActivity.queued_jobs],
    [backendActivity],
  );

  const isExtracting = useCallback((documentId: string) => {
    if (jobsRef.current.has(documentId)) return true;
    return backendJobs.some((job) => job.document_id === documentId && ['queued', 'running'].includes(job.status));
  }, [backendJobs]);

  const activityLabelForDocument = useCallback((documentId: string) => {
    const backendJob = backendJobs.find((job) => job.document_id === documentId);
    if (backendJob?.status === 'queued') return 'Waiting in extraction queue';
    if (backendJob?.status === 'running') return 'Extracting';
    const localJob = jobsRef.current.get(documentId);
    if (!localJob) return null;
    if (localJob.stage === 'failed') return 'Extraction failed';
    if (localJob.stage === 'completed') return 'Extraction completed';
    return 'Extracting';
  }, [backendJobs]);

  const banner = useMemo(() => {
    return buildBannerState(jobs, backendActivity);
  }, [jobs, backendActivity]);

  const value = useMemo<ExtractionActivityContextValue>(() => ({
    runExtraction,
    isExtracting,
    activityLabelForDocument,
    banner,
  }), [activityLabelForDocument, banner, isExtracting, runExtraction]);

  return (
    <ExtractionActivityContext.Provider value={value}>
      {children}
    </ExtractionActivityContext.Provider>
  );
}

export function useExtractionActivity() {
  const context = useContext(ExtractionActivityContext);
  if (!context) {
    throw new Error('useExtractionActivity must be used within ExtractionActivityProvider');
  }
  return context;
}

export function ExtractionActivityBanner() {
  const { banner } = useExtractionActivity();
  if (!banner) return null;
  const suffix = banner.extraCount > 0 ? ` +${banner.extraCount} waiting` : '';
  return (
    <section className="extraction-activity-banner" role="status" aria-label="Extraction activity">
      <div className="extraction-activity-banner__spinner" aria-hidden="true" />
      <div className="extraction-activity-banner__content">
        {`${banner.label}: ${banner.filename}${suffix}`}
        <span>{formatElapsed(banner.elapsedMs)}</span>
      </div>
      <div className="extraction-activity-banner__bar" aria-hidden="true" />
    </section>
  );
}

function buildBannerState(
  localJobs: LocalExtractionJob[],
  backendActivity: ExtractionActivityResponse,
): BannerState | null {
  const backendJob = backendActivity.active_jobs[0] ?? backendActivity.queued_jobs[0] ?? null;
  if (backendJob) {
    return {
      filename: backendJob.filename,
      label: backendJob.status === 'queued' ? 'Waiting in extraction queue' : 'Extracting',
      elapsedMs: backendJob.elapsed_ms,
      extraCount: Math.max(0, backendActivity.active_count + backendActivity.queue_count - 1),
    };
  }
  const activeLocal = localJobs.find((job) => !['completed', 'failed'].includes(job.stage)) ?? localJobs[0] ?? null;
  if (!activeLocal) return null;
  return {
    filename: activeLocal.filename,
    label: stageLabel(activeLocal.stage),
    elapsedMs: Date.now() - activeLocal.startedAt,
    extraCount: Math.max(0, localJobs.length - 1),
  };
}

function stageLabel(stage: LocalStage): string {
  if (stage === 'reading') return 'Extracting';
  if (stage === 'running_ocr') return 'Running OCR';
  if (stage === 'completed') return 'Extraction completed';
  return 'Extraction failed';
}

function formatElapsed(elapsedMs: number): string {
  const seconds = Math.max(0, Math.floor(elapsedMs / 1000));
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes === 0) return `${remainingSeconds}s`;
  return `${minutes}m ${remainingSeconds.toString().padStart(2, '0')}s`;
}
