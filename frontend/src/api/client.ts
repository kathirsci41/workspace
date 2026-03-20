import axios from 'axios';
import type { ToastType } from '@/context/ToastContext';

const client = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Toast bridge ──────────────────────────────────────────────────────────────
// Axios lives outside React — we can't call hooks here.
// ToastProvider calls setAxiosToast() once on mount to wire up the function.

type ToastFn = (msg: string, type?: ToastType) => void;
let _toast: ToastFn | null = null;

export function setAxiosToast(fn: ToastFn) {
  _toast = fn;
}

// ── Response interceptor ──────────────────────────────────────────────────────

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (!_toast) return Promise.reject(error);

    // Aborted requests (AbortController on page unmount) — silent
    if (axios.isCancel(error) || error.name === 'CanceledError') {
      return Promise.reject(error);
    }

    const status = error?.response?.status;

    if (!error.response) {
      // No response at all — network down or DNS failure
      _toast('Connection lost — check your network.', 'error');
    } else if (status === 503 || status === 502 || status === 504) {
      const detail = error.response?.data?.detail;
      _toast(
        detail ?? 'Extraction service unreachable — document queued for retry.',
        'error',
      );
    } else if (status >= 500) {
      _toast('Server error — please try again.', 'error');
    }
    // 4xx errors are handled inline by each component — no global toast

    return Promise.reject(error);
  }
);

export default client;
