import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import SearchPage from './pages/SearchPage'
import CasePage from './pages/CasePage'
import SOSearchResults from './pages/SOSearchResults'
import AdminPage from './pages/AdminPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/cases/:caseId" element={<CasePage />} />
        <Route path="/search/so/:soNumber" element={<SOSearchResults />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </Layout>
  )
}

export default App
