import { FormEvent, useState } from 'react';
import { REQUIRED_DOCUMENT_SLOTS } from '../../lib/build1';

export function CreateBundleModal({
  isOpen,
  isCreating,
  error,
  onClose,
  onCreate,
}: {
  isOpen: boolean;
  isCreating: boolean;
  error: string | null;
  onClose: () => void;
  onCreate: (bundleName: string) => Promise<void>;
}) {
  const [bundleName, setBundleName] = useState('');

  if (!isOpen) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onCreate(bundleName.trim());
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="create-bundle-title">
        <div className="modal__header">
          <h2 id="create-bundle-title">Create Bundle</h2>
          <button className="icon-button" type="button" aria-label="Close create bundle modal" onClick={onClose}>x</button>
        </div>
        <form className="form-grid" onSubmit={submit}>
          <label>
            Bundle name
            <input value={bundleName} onChange={(event) => setBundleName(event.target.value)} required autoFocus />
          </label>
          <div className="required-preview">
            <h3>Required documents after creation</h3>
            <ul>
              {REQUIRED_DOCUMENT_SLOTS.map((slot) => <li key={slot.type}>{slot.label}</li>)}
            </ul>
          </div>
          {error ? <p role="alert">{error}</p> : null}
          <div className="modal__actions">
            <button type="button" className="button button--ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="button button--primary" disabled={isCreating || !bundleName.trim()}>
              {isCreating ? 'Creating...' : 'Create verification bundle'}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
