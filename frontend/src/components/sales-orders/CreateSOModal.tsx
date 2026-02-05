import { useState } from 'react';
import { AlertCircle, Info } from 'lucide-react';
import Modal from '../common/Modal';
import Button from '../common/Button';
import MonthPicker from '../common/MonthPicker';
import { useCreateSalesOrder } from '../../hooks/useSalesOrders';

interface CreateSOModalProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  onSuccess: () => void;
}

export default function CreateSOModal({
  isOpen,
  onClose,
  caseId,
  onSuccess,
}: CreateSOModalProps) {
  const [soNumber, setSoNumber] = useState('');
  const [soMonth, setSoMonth] = useState('');
  const [error, setError] = useState<string | null>(null);

  const { mutate: createSO, isPending } = useCreateSalesOrder(caseId);

  const handleSubmit = () => {
    if (!soNumber.trim()) {
      setError('Please enter a Sales Order number');
      return;
    }

    if (!soMonth) {
      setError('Please select a month');
      return;
    }

    createSO(
      {
        soNumber: soNumber.trim(),
        soMonth,
      },
      {
        onSuccess: () => {
          resetForm();
          onSuccess();
        },
        onError: (err) => {
          setError(err.message);
        },
      }
    );
  };

  const resetForm = () => {
    setSoNumber('');
    setSoMonth('');
    setError(null);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Create Sales Order" size="md">
      <div className="space-y-4">
        {/* Error message */}
        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-md">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* SO Number */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Sales Order Number <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={soNumber}
            onChange={(e) => setSoNumber(e.target.value)}
            placeholder="e.g., 10TM2526001365"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <p className="text-xs text-gray-500 mt-1">
            This must be globally unique across all cases
          </p>
        </div>

        {/* Month Picker */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Month <span className="text-red-500">*</span>
          </label>
          <div className="border border-gray-300 rounded-md p-4">
            <MonthPicker value={soMonth} onChange={setSoMonth} />
          </div>
        </div>

        {/* Info message */}
        <div className="flex items-start gap-2 p-3 bg-blue-50 text-blue-700 rounded-md">
          <Info className="h-5 w-5 flex-shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-medium">Important</p>
            <p className="mt-1">
              All documents uploaded to this Sales Order will be stored in the{' '}
              <strong>{soMonth || '[Selected Month]'}</strong> folder. This cannot be
              changed later.
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t">
          <Button variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} isLoading={isPending}>
            Create Sales Order
          </Button>
        </div>
      </div>
    </Modal>
  );
}
