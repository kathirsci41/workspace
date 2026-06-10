import { FormEvent, useEffect, useState } from 'react';
import { fieldLabel, formatValue } from '../../lib/format';

export function ManualCorrectionModal({
  field,
  currentValue,
  isSaving,
  error,
  onClose,
  onSave,
}: {
  field: string | null;
  currentValue: unknown;
  isSaving: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (field: string, value: string, reason: string) => Promise<void>;
}) {
  const [value, setValue] = useState('');
  const [reason, setReason] = useState('corrected wrong value');

  useEffect(() => {
    setValue(currentValue === null || currentValue === undefined ? '' : String(currentValue));
  }, [currentValue, field]);

  if (!field) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!field) return;
    await onSave(field, value, reason);
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="manual-correction-title">
        <div className="modal__header">
          <h2 id="manual-correction-title">Manual Correction</h2>
          <button className="icon-button" type="button" aria-label="Close manual correction modal" onClick={onClose}>x</button>
        </div>
        <form className="form-grid" onSubmit={submit}>
          <div className="field-summary">
            <span className="muted">Field</span>
            <strong>{fieldLabel(field)}</strong>
            <span className="muted">Current value</span>
            <span>{formatValue(currentValue, field)}</span>
          </div>
          <label>
            Corrected value
            <input value={value} onChange={(event) => setValue(event.target.value)} />
          </label>
          <label>
            Correction reason
            <select value={reason} onChange={(event) => setReason(event.target.value)}>
              <option value="corrected wrong value">corrected wrong value</option>
              <option value="field missing">field missing</option>
              <option value="OCR failed">OCR failed</option>
              <option value="scanned document unreadable">scanned document unreadable</option>
              <option value="other">other</option>
            </select>
          </label>
          {error ? <p role="alert">{error}</p> : null}
          <div className="modal__actions">
            <button className="button button--ghost" type="button" onClick={onClose}>Cancel</button>
            <button className="button button--primary" type="submit" disabled={isSaving}>{isSaving ? 'Saving...' : 'Save manual correction'}</button>
          </div>
        </form>
      </section>
    </div>
  );
}
