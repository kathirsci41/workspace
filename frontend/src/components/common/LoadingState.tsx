export function LoadingState({ label = 'Loading...' }: { label?: string }) {
  return <div className="state-message state-message--loading" role="status">{label}</div>;
}
