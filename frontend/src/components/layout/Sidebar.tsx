import { useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  Plus,
  Search,
} from "lucide-react";
import type { SalesOrderWithDocuments } from "../../types";

interface SidebarProps {
  salesOrders: SalesOrderWithDocuments[];
  onAddSO: () => void;
  onSelectSO: (soId: number) => void;
  selectedSOId?: number;
}

export default function Sidebar({
  salesOrders,
  onAddSO,
  onSelectSO,
  selectedSOId,
}: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const filteredSOs = salesOrders.filter((so) =>
    so.soNumber.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  if (isCollapsed) {
    return (
      <div className="w-12 bg-gray-50 border-r border-gray-200 flex flex-col items-center py-4">
        <button
          onClick={() => setIsCollapsed(false)}
          className="p-2 hover:bg-gray-200 rounded-md"
          title="Expand sidebar"
        >
          <ChevronRight className="h-5 w-5 text-gray-600" />
        </button>
      </div>
    );
  }

  return (
    <div className="w-64 bg-gray-50 border-r border-gray-200 flex flex-col">
      {/* SO Search */}
      <div className="p-4 border-b border-gray-200">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search SO..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        </div>
      </div>

      {/* Sales Orders List */}
      <div className="flex-1 overflow-y-auto p-4">
        <h3 className="text-sm font-medium text-gray-500 mb-2">Sales Orders</h3>
        <div className="space-y-2">
          {filteredSOs.length === 0 ? (
            <p className="text-sm text-gray-400 italic">No sales orders</p>
          ) : (
            filteredSOs.map((so) => (
              <button
                key={so.id}
                onClick={() => onSelectSO(so.id)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                  selectedSOId === so.id
                    ? "bg-primary-100 border-primary-300 text-primary-700"
                    : "bg-white border-gray-200 hover:border-primary-300 hover:bg-primary-50"
                } border`}
              >
                <div className="flex items-center gap-2">
                  <FolderOpen className="h-4 w-4 flex-shrink-0" />
                  <div className="truncate">
                    <div className="font-medium truncate">
                      SO-{so.soNumber.slice(-6)}
                    </div>
                    <div className="text-xs text-gray-500">
                      {formatMonth(so.soMonth)}
                    </div>
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Add SO Button */}
      <div className="p-4 border-t border-gray-200">
        <button
          onClick={onAddSO}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors text-sm font-medium"
        >
          <Plus className="h-4 w-4" />
          Add New SO
        </button>
      </div>

      {/* Collapse Button */}
      <div className="p-4 border-t border-gray-200">
        <button
          onClick={() => setIsCollapsed(true)}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-200 rounded-md transition-colors text-sm"
        >
          <ChevronLeft className="h-4 w-4" />
          Collapse
        </button>
      </div>
    </div>
  );
}

function formatMonth(monthStr: string): string {
  const [year, month] = monthStr.split("-");
  const date = new Date(parseInt(year), parseInt(month) - 1);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}
