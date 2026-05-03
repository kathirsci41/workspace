import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Download, Loader2, CheckCircle2, Lock } from 'lucide-react';
import { useQueryClient, useMutation } from '@tanstack/react-query';
import { usePOProfile } from '@/hooks/usePurchaseOrders';
import { exportPOAsExcel, closeOrder } from '@/api/purchaseOrders';
import { useToast } from '@/context/ToastContext';
import { ProfileDocumentSection } from '@/components/ProfileDocumentSection';
import { ProfileTimeline } from '@/components/ProfileTimeline';
import { ProfileDiscrepancyPanel } from '@/components/ProfileDiscrepancyPanel';
import { ProfileFieldComparison } from '@/components/ProfileFieldComparison';
import { ProfileItemComparison } from '@/components/ProfileItemComparison';
import ChainStatusBar from '@/components/ChainStatusBar';
import Breadcrumb from '@/components/Breadcrumb';
import type { POProfile, ChainSlot } from '@/types';

function buildChainFromProfile(profile: POProfile): Record<string, ChainSlot[]> {
  const result: Record<string, ChainSlot[]> = {};
  for (const slot of profile.slots) {
    if (slot.status === 'not_applicable') {
      // Mark as single sentinel slot so ChainStatusBar can render N/A
      result[slot.document_type] = [{
        status: 'not_applicable',
        document_id: null,
        ref_no: null,
        uploaded_at: null,
        confidence: null,
        required: false,
        optional: false,
      }];
    } else if (slot.status === 'empty' || slot.documents.length === 0) {
      result[slot.document_type] = [{
        status: 'empty',
        document_id: null,
        ref_no: null,
        uploaded_at: null,
        confidence: null,
        required: slot.required,
        optional: slot.optional,
      }];
    } else {
      result[slot.document_type] = slot.documents.map((doc) => ({
        status: doc.status,
        document_id: doc.document_id,
        ref_no: doc.primary_ref_no,
        uploaded_at: doc.uploaded_at,
        confidence: doc.confidence_score,
        required: slot.required,
        optional: slot.optional,
      }));
    }
  }
  return result;
}

export function POProfilePage() {
  const { id } = useParams<{ id: string }>();
  const { data: profile, isLoading, isError } = usePOProfile(id!);
  const [exporting, setExporting] = useState(false);
  const [showCloseDialog, setShowCloseDialog] = useState(false);
  const [closeNote, setCloseNote] = useState('');
  const showToast = useToast();
  const queryClient = useQueryClient();

  const closeOrderMutation = useMutation({
    mutationFn: () => closeOrder(id!, closeNote.trim() || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['poProfile', id] });
      queryClient.invalidateQueries({ queryKey: ['purchaseOrders'] });
      setShowCloseDialog(false);
      setCloseNote('');
      showToast('Order closed successfully.', 'success');
    },
    onError: () => showToast('Failed to close order. Please try again.', 'error'),
  });

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
      <Breadcrumb items={[
        { label: 'Purchase Orders', to: '/purchase-orders' },
        { label: profile.po_number, to: `/purchase-orders/${id}` },
        { label: 'Profile' },
      ]} />

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
          <span className="text-sm text-gray-500">
            {profile.chain_completeness_display ?? `${Math.min(Math.round(profile.chain_completeness), 100)}%`} complete
          </span>
          <button
            onClick={handleExport}
            disabled={exporting}
            title="Export to Excel (7 sheets)"
            className="inline-flex items-center gap-1.5 text-sm text-gray-600 border border-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-50 disabled:opacity-50 ml-auto"
          >
            <Download size={14} className={exporting ? 'animate-bounce' : ''} />
            {exporting ? 'Exporting…' : 'Export Excel'}
          </button>

          {/* Close Order button */}
          {!profile.manually_completed ? (
            <button
              onClick={() => setShowCloseDialog(true)}
              className="inline-flex items-center gap-1.5 text-sm text-white bg-green-600 border border-green-700 px-3 py-1.5 rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              <Lock size={14} />
              Close Order
            </button>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-sm text-green-700 bg-green-50 border border-green-200 px-3 py-1.5 rounded-lg">
              <CheckCircle2 size={14} />
              Closed {profile.completed_at
                ? new Date(profile.completed_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
                : ''}
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-xs text-gray-600">
          <div><span className="text-gray-400">Customer</span> &nbsp;{profile.customer_name} ({profile.customer_sky_id})</div>
          {profile.so_number && <div><span className="text-gray-400">SO Number</span> &nbsp;{profile.so_number}</div>}
          {profile.customer_po_ref && <div><span className="text-gray-400">Customer PO Ref</span> &nbsp;{profile.customer_po_ref}</div>}
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

      {/* Cross-document field comparisons */}
      <ProfileFieldComparison comparisons={profile.field_comparisons ?? []} />

      {/* Item-level qty + part number verification */}
      <ProfileItemComparison
        comparisons={profile.item_comparisons ?? []}
        matches={profile.item_matches ?? []}
      />

      {/* Vendor breakdown (procurement only, when at least one COMPANY_PO uploaded) */}
      {profile.vendor_groups && profile.vendor_groups.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Vendor Breakdown
          </h3>
          {profile.vendor_groups.map((group) => {
            const pct = group.completeness_pct;
            const barColour =
              pct === 100 ? 'bg-green-500' :
              pct >= 67  ? 'bg-amber-400' :
              pct >= 33  ? 'bg-orange-400' : 'bg-red-400';
            return (
              <div key={group.vendor_po_ref} className="border border-gray-100 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-medium text-gray-800 truncate">
                      {group.vendor_name ?? group.vendor_po_ref}
                    </span>
                    {group.vendor_name && (
                      <span className="text-xs text-gray-400 shrink-0">{group.vendor_po_ref}</span>
                    )}
                  </div>
                  <span className="text-xs font-semibold text-gray-600 shrink-0">{pct}%</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-1.5">
                  <div className={`${barColour} h-1.5 rounded-full transition-all`} style={{ width: `${pct}%` }} />
                </div>
                <div className="flex gap-2 flex-wrap">
                  {group.slots.map((slot) => {
                    const dotColour =
                      slot.status === 'VERIFIED'      ? 'bg-green-500' :
                      slot.status === 'PENDING_REVIEW'? 'bg-amber-400' :
                      slot.status === 'empty'         ? 'bg-gray-300'  : 'bg-blue-400';
                    return (
                      <span key={slot.document_type} className="inline-flex items-center gap-1 text-xs text-gray-500">
                        <span className={`w-2 h-2 rounded-full ${dotColour}`} />
                        {slot.document_type.replace(/_/g, ' ')}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Document sections */}
      {profile.slots.map((slot) => (
        <ProfileDocumentSection key={slot.document_type} slot={slot} poId={id!} />
      ))}

      {/* Timeline */}
      <ProfileTimeline events={profile.timeline} />

      {/* Completed-by-manual note banner */}
      {profile.manually_completed && profile.completion_note && (
        <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-800">
          <span className="font-medium">Completion note:</span> {profile.completion_note}
        </div>
      )}

      {/* Close Order confirmation dialog */}
      {showCloseDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6 space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                <Lock size={18} className="text-green-700" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-gray-900">Close this order?</h2>
                <p className="text-sm text-gray-500 mt-1">
                  This marks all goods as received and the order as complete.
                  This action cannot be undone from the UI.
                </p>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-600">
                Completion note <span className="text-gray-400">(optional)</span>
              </label>
              <textarea
                value={closeNote}
                onChange={(e) => setCloseNote(e.target.value)}
                placeholder="e.g. All items received, vendor DC not issued"
                rows={3}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 resize-none"
              />
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={() => { setShowCloseDialog(false); setCloseNote(''); }}
                disabled={closeOrderMutation.isPending}
                className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => closeOrderMutation.mutate()}
                disabled={closeOrderMutation.isPending}
                className="px-4 py-2 text-sm text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-1.5"
              >
                {closeOrderMutation.isPending
                  ? <><Loader2 size={14} className="animate-spin" /> Closing…</>
                  : <><CheckCircle2 size={14} /> Confirm Close</>
                }
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
