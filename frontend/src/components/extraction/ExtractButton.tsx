import { useState } from 'react';
import { Loader2, Sparkles, RefreshCw, AlertTriangle } from 'lucide-react';
import { triggerExtraction } from '../../api/extraction';
import type { ExtractionResponse, ExtractionStatus } from '../../api/extraction';

interface ExtractButtonProps {
  documentId: number;
  currentStatus?: ExtractionStatus | null;
  onExtractionComplete: (result: ExtractionResponse) => void;
}

export default function ExtractButton({
  documentId,
  currentStatus,
  onExtractionComplete,
}: ExtractButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExtract = async () => {
    setLoading(true);
    setError(null);

    try {
      const forceReExtract =
        currentStatus === 'EXTRACTED' ||
        currentStatus === 'FAILED' ||
        currentStatus === 'VERIFIED';
      const result = await triggerExtraction(documentId, forceReExtract);
      onExtractionComplete(result);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Extraction failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const getButtonLabel = () => {
    if (loading) return 'Extracting…';
    if (currentStatus === 'VERIFIED') return 'Re-Extract';
    if (currentStatus === 'EXTRACTED') return 'Re-Extract';
    if (currentStatus === 'FAILED') return 'Retry Extract';
    return 'Extract Metadata';
  };

  const getButtonIcon = () => {
    if (loading)
      return <Loader2 className="h-4 w-4 animate-spin" />;
    if (currentStatus === 'FAILED')
      return <AlertTriangle className="h-4 w-4" />;
    if (currentStatus === 'EXTRACTED' || currentStatus === 'VERIFIED')
      return <RefreshCw className="h-4 w-4" />;
    return <Sparkles className="h-4 w-4" />;
  };

  const getButtonColor = () => {
    if (currentStatus === 'VERIFIED')
      return 'bg-green-600 hover:bg-green-700';
    if (currentStatus === 'FAILED')
      return 'bg-red-600 hover:bg-red-700';
    return 'bg-blue-600 hover:bg-blue-700';
  };

  return (
    <div>
      <button
        onClick={handleExtract}
        disabled={loading}
        className={`${getButtonColor()} text-white px-3 py-1.5 rounded-md
          text-sm flex items-center gap-2 disabled:opacity-50 transition-colors`}
      >
        {getButtonIcon()}
        {getButtonLabel()}
      </button>

      {error && (
        <p className="text-red-500 text-xs mt-1.5">{error}</p>
      )}
    </div>
  );
}
