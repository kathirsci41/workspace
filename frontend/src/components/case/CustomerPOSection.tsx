import { FileText, Upload, Eye } from 'lucide-react';
import Button from '../common/Button';
import type { Document } from '../../types';

interface CustomerPOSectionProps {
  customerPo: Document | null;
  onView: (doc: Document) => void;
  onUpload: () => void;
}

export default function CustomerPOSection({
  customerPo,
  onView,
  onUpload,
}: CustomerPOSectionProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${customerPo ? 'bg-green-100' : 'bg-gray-100'}`}>
            <FileText className={`h-5 w-5 ${customerPo ? 'text-green-600' : 'text-gray-400'}`} />
          </div>
          <div>
            <h3 className="font-medium text-gray-900">Customer PO</h3>
            {customerPo ? (
              <p className="text-sm text-gray-500">
                {customerPo.originalFilename}
                {customerPo.referenceNumber && (
                  <span className="ml-2 text-gray-400">• {customerPo.referenceNumber}</span>
                )}
              </p>
            ) : (
              <p className="text-sm text-gray-400">No Customer PO uploaded</p>
            )}
          </div>
        </div>

        {customerPo ? (
          <Button variant="secondary" size="sm" onClick={() => onView(customerPo)}>
            <Eye className="h-4 w-4 mr-1" />
            View
          </Button>
        ) : (
          <Button variant="secondary" size="sm" onClick={onUpload}>
            <Upload className="h-4 w-4 mr-1" />
            Upload
          </Button>
        )}
      </div>
    </div>
  );
}
