import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  FileText,
  Files,
  Search,
  Settings2,
  Menu,
  X,
  ChevronRight,
  ChevronLeft,
} from 'lucide-react';
import clsx from 'clsx';
import InlineSearch from './InlineSearch';

const navLinks = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/purchase-orders', label: 'Purchase Orders', icon: FileText },
  { to: '/documents', label: 'Documents', icon: Files },
  { to: '/search', label: 'Search', icon: Search },
  { to: '/admin',  label: 'System',  icon: Settings2 },
];

const STORAGE_KEY = 'sidebar-collapsed';

function getInitialCollapsed(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === null ? false : stored === 'true';
  } catch {
    return true;
  }
}

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(getInitialCollapsed);

  const toggleCollapsed = () => {
    setCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem(STORAGE_KEY, String(next)); } catch {}
      return next;
    });
  };

  return (
    <div className="min-h-screen flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed top-0 left-0 z-40 h-full bg-gray-900 text-white flex flex-col transition-all duration-200 lg:translate-x-0',
          collapsed ? 'w-14' : 'w-64',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between h-16 px-3 border-b border-gray-700 shrink-0">
          {!collapsed && (
            <h1 className="text-xl font-bold tracking-tight truncate">DocPlatform</h1>
          )}
          {/* Mobile close button */}
          <button
            className="lg:hidden p-1 hover:bg-gray-700 rounded ml-auto"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={20} />
          </button>
        </div>

        {/* Nav links */}
        <nav className="flex-1 py-4 space-y-1 px-2 overflow-y-auto">
          {navLinks.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setSidebarOpen(false)}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                clsx(
                  'flex items-center rounded-lg text-sm font-medium transition-colors',
                  collapsed ? 'justify-center p-2.5' : 'gap-3 px-3 py-2.5',
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                )
              }
            >
              <Icon size={20} className="shrink-0" />
              {!collapsed && label}
            </NavLink>
          ))}
        </nav>

        {/* Footer: version + collapse toggle */}
        <div className="border-t border-gray-700 shrink-0">
          {/* Collapse toggle — desktop only */}
          <button
            onClick={toggleCollapsed}
            className="hidden lg:flex w-full items-center justify-center gap-2 py-3 text-xs text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight size={16} /> : (
              <>
                <ChevronLeft size={16} />
                <span>Collapse</span>
              </>
            )}
          </button>
          {!collapsed && (
            <div className="px-4 pb-3 text-xs text-gray-500">
              DocPlatform V3.0 — Dev Build
            </div>
          )}
        </div>
      </aside>

      {/* Main content — offset matches sidebar width */}
      <div
        className={clsx(
          'flex-1 flex flex-col overflow-hidden transition-all duration-200',
          collapsed ? 'lg:ml-14' : 'lg:ml-64'
        )}
        style={{ height: '100vh' }}
      >
        {/* Top header */}
        <header className="shrink-0 sticky top-0 z-20 h-16 bg-white border-b border-gray-200 flex items-center px-4 gap-4">
          <button
            className="lg:hidden p-2 hover:bg-gray-100 rounded"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={20} />
          </button>
          <InlineSearch />
        </header>

        {/* Page content */}
        <main className="flex-1 min-h-0 p-6 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
