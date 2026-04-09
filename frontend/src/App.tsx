import { BrowserRouter, Routes, Route } from 'react-router-dom';
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

function App() {
  return (
    <BrowserRouter>
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
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
