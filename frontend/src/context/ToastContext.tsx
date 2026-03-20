import { createContext, useContext, useCallback, useState, useRef, useEffect, ReactNode } from 'react';
import { setAxiosToast } from '@/api/client';

export type ToastType = 'success' | 'warn' | 'error' | 'info';

interface ToastItem {
  id: number;
  msg: string;
  type: ToastType;
}

interface ToastContextValue {
  showToast: (msg: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let idCounter = 0;
const DURATION = 4500;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
    const t = timers.current.get(id);
    if (t) { clearTimeout(t); timers.current.delete(id); }
  }, []);

  const showToast = useCallback((msg: string, type: ToastType = 'success') => {
    const id = ++idCounter;
    setToasts(prev => [...prev.slice(-4), { id, msg, type }]); // max 5 visible
    const t = setTimeout(() => dismiss(id), DURATION);
    timers.current.set(id, t);
  }, [dismiss]);

  // Wire axios interceptor to global toast
  useEffect(() => {
    setAxiosToast(showToast);
  }, [showToast]);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <ToastStack toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast(): (msg: string, type?: ToastType) => void {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx.showToast;
}

// ── Toast stack rendered at provider level ────────────────────────────────────

import { CheckCircle2, AlertTriangle, XCircle, Info, X } from 'lucide-react';
import clsx from 'clsx';

const STYLES: Record<ToastType, { bar: string; icon: string; bg: string; text: string }> = {
  success: { bar: 'bg-green-500',  icon: 'text-green-600', bg: 'bg-white', text: 'text-gray-800' },
  warn:    { bar: 'bg-amber-400',  icon: 'text-amber-500', bg: 'bg-white', text: 'text-gray-800' },
  error:   { bar: 'bg-red-500',    icon: 'text-red-600',   bg: 'bg-white', text: 'text-gray-800' },
  info:    { bar: 'bg-blue-500',   icon: 'text-blue-600',  bg: 'bg-white', text: 'text-gray-800' },
};

const ICONS: Record<ToastType, React.ElementType> = {
  success: CheckCircle2,
  warn:    AlertTriangle,
  error:   XCircle,
  info:    Info,
};

function ToastStack({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: number) => void }) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-2 items-end pointer-events-none">
      {toasts.map(t => {
        const s = STYLES[t.type];
        const Icon = ICONS[t.type];
        return (
          <div
            key={t.id}
            className={clsx(
              'pointer-events-auto flex items-start gap-3 rounded-lg shadow-lg border border-gray-200 px-4 py-3 min-w-[280px] max-w-sm transition-all duration-200',
              s.bg,
            )}
          >
            {/* Accent bar */}
            <div className={clsx('w-1 self-stretch rounded-full shrink-0', s.bar)} />
            <Icon size={17} className={clsx('mt-0.5 shrink-0', s.icon)} />
            <p className={clsx('text-sm flex-1 leading-snug', s.text)}>{t.msg}</p>
            <button
              onClick={() => onDismiss(t.id)}
              className="text-gray-400 hover:text-gray-600 transition-colors shrink-0 mt-0.5"
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
