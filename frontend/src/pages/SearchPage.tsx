import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, FileText, Package, Plus, Loader2, Hash } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useSearchCases } from "../hooks/useCases";
import { useSearchSalesOrders } from "../hooks/useSalesOrders";
import { searchByDocRef } from "../api/extraction";
import { DOCUMENT_TYPE_LABELS } from "../types";
import { FIELD_LABELS } from "../config/fieldLabels";
import Button from "../components/common/Button";
import Modal from "../components/common/Modal";
import { useCreateCase } from "../hooks/useCases";
import type { CaseType } from "../types";

export default function SearchPage() {
  const navigate = useNavigate();
  const [searchType, setSearchType] = useState<"opportunity" | "sales_order" | "doc_ref">(
    "opportunity",
  );
  const [query, setQuery] = useState("");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const { data: caseResults, isLoading: isCaseLoading } = useSearchCases(
    searchType === "opportunity" ? query : "",
  );
  const { data: soResults, isLoading: isSOLoading } = useSearchSalesOrders(
    searchType === "sales_order" ? query : "",
  );
  const { data: docRefResults, isLoading: isDocRefLoading } = useQuery({
    queryKey: ["docRefSearch", query],
    queryFn: () => searchByDocRef(query),
    enabled: searchType === "doc_ref" && query.length >= 2,
  });

  const isLoading =
    searchType === "opportunity"
      ? isCaseLoading
      : searchType === "sales_order"
        ? isSOLoading
        : isDocRefLoading;
  const hasQuery = query.length >= 2;

  const handleCaseClick = (caseId: string) => {
    navigate(`/cases/${caseId}`);
  };

  const handleSOClick = (soNumber: string) => {
    navigate(`/search/so/${soNumber}`);
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Document Platform
        </h1>
        <p className="text-gray-500">
          Search by Opportunity ID, Sales Order number, or Document Reference
        </p>
      </div>

      {/* Search Type Toggle */}
      <div className="flex justify-center mb-6">
        <div className="inline-flex rounded-lg border border-gray-300 p-1">
          <button
            onClick={() => {
              setSearchType("opportunity");
              setQuery("");
            }}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              searchType === "opportunity"
                ? "bg-primary-600 text-white"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            <FileText className="h-4 w-4 inline mr-2" />
            Opportunity ID
          </button>
          <button
            onClick={() => {
              setSearchType("sales_order");
              setQuery("");
            }}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              searchType === "sales_order"
                ? "bg-primary-600 text-white"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            <Package className="h-4 w-4 inline mr-2" />
            Sales Order
          </button>
          <button
            onClick={() => {
              setSearchType("doc_ref");
              setQuery("");
            }}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              searchType === "doc_ref"
                ? "bg-primary-600 text-white"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            <Hash className="h-4 w-4 inline mr-2" />
            Doc Reference
          </button>
        </div>
      </div>

      {/* Search Input */}
      <div className="relative mb-8">
        <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={
            searchType === "opportunity"
              ? "Search by Opportunity ID (e.g., SKY-443)"
              : searchType === "sales_order"
                ? "Search by Sales Order number (e.g., 10TM2526001365)"
                : "Search by Invoice No, PO No, DC No, POD No..."
          }
          className="w-full pl-12 pr-4 py-4 text-lg border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent shadow-sm"
        />
        {isLoading && (
          <Loader2 className="absolute right-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400 animate-spin" />
        )}
      </div>

      {/* Results */}
      <div className="space-y-3">
        {/* Opportunity Results */}
        {searchType === "opportunity" && hasQuery && caseResults && (
          <>
            {caseResults.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-gray-500 mb-4">
                  No cases found for "{query}"
                </p>
                <Button onClick={() => setIsCreateModalOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Create New Case
                </Button>
              </div>
            ) : (
              caseResults.map((caseItem) => (
                <button
                  key={caseItem.id}
                  onClick={() => handleCaseClick(caseItem.caseId)}
                  className="w-full text-left p-4 bg-white rounded-lg border border-gray-200 hover:border-primary-300 hover:shadow-md transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-gray-900">
                          {caseItem.opportunityId}
                        </span>
                        <span className="text-sm text-gray-400">
                          ({caseItem.caseId})
                        </span>
                      </div>
                      <p className="text-gray-600">{caseItem.customerName}</p>
                    </div>
                    <div className="text-right">
                      <span
                        className={`inline-block px-2 py-1 text-xs rounded-full ${
                          caseItem.status === "OPEN"
                            ? "bg-green-100 text-green-700"
                            : caseItem.status === "IN_PROGRESS"
                              ? "bg-yellow-100 text-yellow-700"
                              : "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {caseItem.status}
                      </span>
                      <p className="text-sm text-gray-400 mt-1">
                        {caseItem.caseType}
                      </p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </>
        )}

        {/* SO Results */}
        {searchType === "sales_order" && hasQuery && soResults && (
          <>
            {soResults.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-gray-500">
                  No sales orders found for "{query}"
                </p>
              </div>
            ) : (
              soResults.map((so) => (
                <button
                  key={so.soNumber}
                  onClick={() => handleSOClick(so.soNumber)}
                  className="w-full text-left p-4 bg-white rounded-lg border border-gray-200 hover:border-primary-300 hover:shadow-md transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-gray-900">
                          SO-{so.soNumber}
                        </span>
                        <span className="text-sm text-gray-400">
                          ({formatMonth(so.soMonth)})
                        </span>
                      </div>
                      <p className="text-gray-600">{so.customerName}</p>
                      <p className="text-sm text-gray-400">
                        {so.opportunityId} • {so.caseId}
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="text-sm text-gray-500">
                        {so.documentCount} documents
                      </span>
                      <div className="flex gap-1 mt-1 justify-end">
                        {Object.entries(so.checklist).map(([key, value]) => (
                          <span
                            key={key}
                            className={`w-2 h-2 rounded-full ${
                              value ? "bg-green-500" : "bg-gray-300"
                            }`}
                            title={key}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                </button>
              ))
            )}
          </>
        )}

        {/* Doc Reference Results */}
        {searchType === "doc_ref" && hasQuery && docRefResults && (
          <>
            {docRefResults.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-gray-500">
                  No documents found matching "{query}"
                </p>
              </div>
            ) : (
              docRefResults.map((item) => (
                <button
                  key={item.metadata_id}
                  onClick={() => {
                    if (item.case_id) {
                      navigate(`/cases/${item.case_id}`);
                    } else if (item.so_number) {
                      navigate(`/search/so/${item.so_number}`);
                    }
                  }}
                  className="w-full text-left p-4 bg-white rounded-lg border border-gray-200 hover:border-primary-300 hover:shadow-md transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="inline-block px-2 py-0.5 text-xs font-medium rounded bg-blue-100 text-blue-700">
                          {DOCUMENT_TYPE_LABELS[item.doc_type as keyof typeof DOCUMENT_TYPE_LABELS] || item.doc_type}
                        </span>
                        {item.primary_ref_no && (
                          <span className="font-semibold text-gray-900">
                            {item.primary_ref_no}
                          </span>
                        )}
                        {item.doc_date && (
                          <span className="text-sm text-gray-400">
                            ({item.doc_date})
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 mt-1 truncate">
                        {item.filename}
                      </p>
                      <div className="flex items-center gap-2 mt-1 text-sm text-gray-400">
                        {item.customer_name && <span>{item.customer_name}</span>}
                        {item.opportunity_id && <span>• {item.opportunity_id}</span>}
                        {item.so_number && <span>• SO-{item.so_number}</span>}
                        {item.so_month && <span>• {formatMonth(item.so_month)}</span>}
                      </div>
                      {/* Show matched fields */}
                      {item.matched_fields.length > 0 && (
                        <div className="flex gap-1 mt-2 flex-wrap">
                          {item.matched_fields.map((field) => {
                            const label =
                              FIELD_LABELS[item.doc_type]?.[field] || field;
                            const value =
                              field === "primary_ref_no"
                                ? item.primary_ref_no
                                : String(item.extracted_data[field] || "");
                            return (
                              <span
                                key={field}
                                className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-yellow-50 text-yellow-700 border border-yellow-200"
                                title={`Matched: ${label}`}
                              >
                                <span className="font-medium">{label}:</span>
                                <span>{value}</span>
                              </span>
                            );
                          })}
                        </div>
                      )}
                    </div>
                    <div className="text-right ml-4 flex-shrink-0">
                      <span
                        className={`inline-block px-2 py-1 text-xs rounded-full ${
                          item.status === "VERIFIED"
                            ? "bg-green-100 text-green-700"
                            : item.status === "EXTRACTED"
                              ? "bg-blue-100 text-blue-700"
                              : item.status === "FAILED"
                                ? "bg-red-100 text-red-700"
                                : "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {item.status}
                      </span>
                      {item.confidence_score !== null && (
                        <p className="text-xs text-gray-400 mt-1">
                          {Math.round(item.confidence_score * 100)}% conf
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              ))
            )}
          </>
        )}

        {/* Initial state */}
        {!hasQuery && (
          <div className="text-center py-12">
            <Search className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-6">
              Start typing to search for{" "}
              {searchType === "opportunity"
                ? "cases"
                : searchType === "sales_order"
                  ? "sales orders"
                  : "documents by reference number"}
            </p>
            {searchType === "opportunity" && (
              <Button
                variant="secondary"
                onClick={() => setIsCreateModalOpen(true)}
              >
                <Plus className="h-4 w-4 mr-2" />
                Create New Case
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Create Case Modal */}
      <CreateCaseModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        initialOppId={query}
      />
    </div>
  );
}

function CreateCaseModal({
  isOpen,
  onClose,
  initialOppId,
}: {
  isOpen: boolean;
  onClose: () => void;
  initialOppId?: string;
}) {
  const navigate = useNavigate();
  const [opportunityId, setOpportunityId] = useState(initialOppId || "");
  const [customerName, setCustomerName] = useState("");
  const [caseType, setCaseType] = useState<CaseType>("HARDWARE");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { mutate: createCase, isPending } = useCreateCase();

  const handleSubmit = () => {
    if (!opportunityId.trim()) {
      setError("Please enter an Opportunity ID");
      return;
    }
    if (!customerName.trim()) {
      setError("Please enter a customer name");
      return;
    }

    createCase(
      {
        opportunityId: opportunityId.trim(),
        customerName: customerName.trim(),
        caseType,
        notes: notes.trim() || undefined,
      },
      {
        onSuccess: (newCase) => {
          onClose();
          navigate(`/cases/${newCase.caseId}`);
        },
        onError: (err) => {
          setError(err.message);
        },
      },
    );
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create New Case">
      <div className="space-y-4">
        {error && (
          <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm">
            {error}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Opportunity ID <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={opportunityId}
            onChange={(e) => setOpportunityId(e.target.value)}
            placeholder="e.g., SKY-443"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Customer Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
            placeholder="e.g., ABC Corporation"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Case Type <span className="text-red-500">*</span>
          </label>
          <select
            value={caseType}
            onChange={(e) => setCaseType(e.target.value as CaseType)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="HARDWARE">Hardware</option>
            <option value="SERVICES">Services</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Notes <span className="text-gray-400">(optional)</span>
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} isLoading={isPending}>
            Create Case
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function formatMonth(monthStr: string): string {
  const [year, month] = monthStr.split("-");
  const date = new Date(parseInt(year), parseInt(month) - 1);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}
