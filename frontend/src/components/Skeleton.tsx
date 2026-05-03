import clsx from 'clsx';

const shimmer =
  'bg-[linear-gradient(90deg,#E8E1D3_0%,#F4EEDF_50%,#E8E1D3_100%)] bg-[length:200%_100%] animate-[shimmer-sweep_1.6s_ease-in-out_infinite] rounded';

export function SkeletonBar({
  width = 'w-full',
  height = 'h-4',
  className,
}: {
  width?: string;
  height?: string;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={clsx(shimmer, width, height, className)}
    />
  );
}

const COL_WIDTHS = ['w-[30%]', 'w-[80%]', 'w-[55%]', 'w-[40%]', 'w-[70%]', 'w-[50%]', 'w-[65%]', 'w-[45%]'];

export function SkeletonTableRow({ columns }: { columns: number }) {
  return (
    <tr aria-hidden="true">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <span className={clsx(shimmer, 'h-4 block', COL_WIDTHS[i % COL_WIDTHS.length])} />
        </td>
      ))}
    </tr>
  );
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={clsx('bg-white rounded-xl border border-veil p-5', className)}>
      <div className="flex items-start gap-3">
        <span className={clsx(shimmer, 'w-9 h-9 shrink-0 rounded-lg')} />
        <div className="flex-1 space-y-2 pt-0.5">
          <span className={clsx(shimmer, 'h-3 block w-[60%]')} />
          <span className={clsx(shimmer, 'h-6 block w-[40%]')} />
        </div>
      </div>
    </div>
  );
}
