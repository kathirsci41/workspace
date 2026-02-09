import type { ExtractionStatus } from '../../api/extraction';

const STATUS_CONFIG: Record<
  ExtractionStatus,
  { label: string; bg: string; text: string; dot: string }
> = {
  PENDING: {
    label: 'Pending',
    bg: 'bg-gray-100',
    text: 'text-gray-600',
    dot: 'bg-gray-400',
  },
  EXTRACTED: {
    label: 'Needs Review',
    bg: 'bg-yellow-100',
    text: 'text-yellow-700',
    dot: 'bg-yellow-500',
  },
  VERIFIED: {
    label: 'Verified',
    bg: 'bg-green-100',
    text: 'text-green-700',
    dot: 'bg-green-500',
  },
  FAILED: {
    label: 'Failed',
    bg: 'bg-red-100',
    text: 'text-red-700',
    dot: 'bg-red-500',
  },
};

interface StatusBadgeProps {
  status: ExtractionStatus | null | undefined;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  if (!status) return null;

  const config = STATUS_CONFIG[status];
  if (!config) return null;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5
        rounded-full text-xs font-medium ${config.bg} ${config.text}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  );
}
