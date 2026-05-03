import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Component, type ReactNode } from 'react';
import AppShell from './components/layout/AppShell';
import DashboardPage from './pages/DashboardPage';
import CustomersPage from './pages/CustomersPage';
import POListPage from './pages/POListPage';
import PODetailPage from './pages/PODetailPage';
import SearchPage from './pages/SearchPage';
import DocumentsPage from './pages/DocumentsPage';
import DocumentDetailPage from './pages/DocumentDetailPage';
import AdminPage from './pages/AdminPage';
import { POProfilePage } from './pages/POProfilePage';
import ChatPage from './pages/ChatPage';

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center p-8 max-w-md">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">Something went wrong</h2>
            <p className="text-sm text-gray-500 mb-4">{(this.state.error as Error).message}</p>
            <button
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
              onClick={() => { this.setState({ error: null }); window.location.href = '/'; }}
            >
              Return to Dashboard
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/purchase-orders" element={<POListPage />} />
            <Route path="/purchase-orders/:id/profile" element={<POProfilePage />} />
            <Route path="/purchase-orders/:id" element={<PODetailPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/documents/:id" element={<DocumentDetailPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
