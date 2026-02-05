import { Link, useLocation } from 'react-router-dom';
import { FileText, Settings } from 'lucide-react';

export default function Header() {
  const location = useLocation();
  
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <FileText className="h-8 w-8 text-primary-600" />
          <span className="text-xl font-bold text-gray-900">Document Platform</span>
          <span className="text-sm text-gray-500 ml-1">v1.1</span>
        </Link>
        
        <nav className="flex items-center gap-4">
          <Link
            to="/"
            className={`px-3 py-2 rounded-md text-sm font-medium ${
              location.pathname === '/'
                ? 'bg-primary-100 text-primary-700'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            Search
          </Link>
          <Link
            to="/admin"
            className={`flex items-center gap-1 px-3 py-2 rounded-md text-sm font-medium ${
              location.pathname === '/admin'
                ? 'bg-primary-100 text-primary-700'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            <Settings className="h-4 w-4" />
            Admin
          </Link>
        </nav>
      </div>
    </header>
  );
}
