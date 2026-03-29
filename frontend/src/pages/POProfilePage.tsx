import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Download, Loader2 } from 'lucide-react';
import { usePOProfile } from '@/hooks/usePurchaseOrders';
import { exportPOAsExcel } from '@/api/purchaseOrders';
import { useToast } from '@/context/ToastContext';
import { ProfileDocumentSection } from '@/components/ProfileDocumentSection';
import { ProfileTimeline } from '@/components/ProfileTimeline';
import { ProfileDiscrepancyPanel } from '@/components/ProfileDiscrepancyPanel';
import ChainStatusBar from '@/components/ChainStatusBar';
import type { POProfile, ChainSlot } from '@/types';

function buildChainFromProfile(profile: POProfile): Record<string, ChainSlot[]> {
  const result: Record<string, ChainSlot[]> = {};
  for (const slot of profile.slots) {
    if (slot.status === 'empty' || slot.documents.length === 0) {
      result[slot.document_type] = [];
    } else {
      result[slot.document_type] = slot.documents.map((doc) => ({
        status: doc.status,
        document_id: doc.document_id,
        ref_no: doc.primary_ref_no,
        uploaded_at: doc.uploaded_at,
        confidence: doc.confidence_score,
      }));
    }
  }
  return result;
}

export function POProfilePage() {
  const { id } = useParams<{ id: string }>();
  const { data: profile, isLoading, isError } = usePOProfile(id!);
  const [exporting, setExporting] = useState(false);
  const showToast = useToast();

  const handleExport = async () => {
    if (!profile) return;
    setExporting(true);
    try {
      await exportPOAsExcel(id!, profile.po_number, 'separate');
    } catch {
      showToast('Export failed. Please try again.', 'error');
    } finally {
      setExporting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={28} className="animate-spin text-gray-400" />
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <div className="p-8 text-sm text-red-600">
        Failed to load profile. <Link to={`/purchase-orders/${id}`} className="underline">Go back</Link>
      </div>
    );
  }

  const chain = buildChainFromProfile(profile);

  const statusColour: Record<string, string> = {
    INITIATED: 'bg-gray-100 text-gray-600',
    IN_PROGRESS: 'bg-blue-100 text-blue-700',
    NEAR_COMPLETE: 'bg-amber-100 text-amber-700',
    COMPLETE: 'bg-green-100 text-green-700',
    CANCELLED: 'bg-red-100 text-red-700',
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-5">
      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <Link
            to={`/purchase-orders/${id}`}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft size={15} /> Back
          </Link>
          <span className="text-lg font-semibold text-gray-800">{profile.po_number}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColour[profile.status] ?? 'bg-gray-100 text-gray-600'}`}>
            {profile.status.replace(/_/g, ' ')}
          </span>
          <span className="text-sm text-gray-500">{Math.round(profile.chain_completeness)}% complete</span>
          <button
            onClick={handleExport}
            disabled={exporting}
            title="Export to Excel (7 sheets)"
            className="inline-flex items-center gap-1.5 text-sm text-gray-600 border border-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-50 disabled:opacity-50 ml-auto"
          >
            <Download size={14} className={exporting ? 'animate-bounce' : ''} />
            {exporting ? 'Exporting…' : 'Export Excel'}
          </button>
        </div>

        <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-xs text-gray-600">
          <div><span className="text-gray-400">Customer</span> &nbsp;{profile.customer_name} ({profile.customer_sky_id})</div>
          {profile.so_number && <div><span className="text-gray-400">SO Number</span> &nbsp;{profile.so_number}</div>}
          {profile.po_date && <div><span className="text-gray-400">PO Date</span> &nbsp;{new Date(profile.po_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</div>}
          {profile.total_amount != null && <div><span className="text-gray-400">Amount</span> &nbsp;₹{profile.total_amount.toLocaleString('en-IN')}</div>}
        </div>

        <ChainStatusBar chain={chain} />
      </div>

      {/* Discrepancy panel */}
      <ProfileDiscrepancyPanel
        discrepancies={profile.discrepancies}
        crossReferences={profile.cross_references}
      />

      {/* Document sections */}
      {profile.slots.map((slot) => (
        <ProfileDocumentSection key={slot.document_type} slot={slot} poId={id!} />
      ))}

      {/* Timeline */}
      <ProfileTimeline events={profile.timeline} />
    </div>
  );
}
