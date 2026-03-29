import type { POProfileTimelineEvent } from '@/types';
import { DOC_TYPE_LABELS } from '@/types';

interface Props {
  events: POProfileTimelineEvent[];
}

const DOT_COLOURS: Record<string, string> = {
  uploaded: 'bg-blue-500',
  extracted: 'bg-amber-500',
  verified: 'bg-green-500',
  rejected: 'bg-red-500',
};

const EVENT_LABELS: Record<string, string> = {
  uploaded: 'Uploaded',
  extracted: 'Extracted',
  verified: 'Verified',
  rejected: 'Rejected',
};

function formatDateTime(ts: string): string {
  return new Date(ts).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function ProfileTimeline({ events }: Props) {
  if (events.length === 0) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Order Timeline</h3>
        <p className="text-xs text-gray-400">No events recorded yet.</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Order Timeline</h3>
      <div className="relative">
        {events.map((event, idx) => {
          const dotClass = DOT_COLOURS[event.event_type] ?? 'bg-gray-400';
          const label = EVENT_LABELS[event.event_type] ?? event.event_type;
          const docLabel = DOC_TYPE_LABELS[event.doc_type as keyof typeof DOC_TYPE_LABELS] ?? event.doc_type;
          const isLast = idx === events.length - 1;

          return (
            <div key={idx} className="flex gap-3">
              {/* Dot + connector */}
              <div className="flex flex-col items-center">
                <div className={`w-2.5 h-2.5 rounded-full shrink-0 mt-0.5 ${dotClass}`} />
                {!isLast && <div className="w-px flex-1 bg-gray-200 my-1" />}
              </div>
              {/* Content */}
              <div className={`pb-3 ${isLast ? '' : ''}`}>
                <p className="text-xs text-gray-700">
                  <span className="font-medium">{docLabel}</span>
                  {' — '}
                  <span>{label}</span>
                </p>
                <p className="text-xs text-gray-400">{formatDateTime(event.timestamp)}</p>
                {event.detail && <p className="text-xs text-gray-500 mt-0.5">{event.detail}</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
