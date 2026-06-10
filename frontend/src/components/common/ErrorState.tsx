export function ErrorState({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return <div className="state-message state-message--error" role="alert">{message}</div>;
}
