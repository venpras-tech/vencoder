import { useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import BottomBar from './BottomBar';
import HistoryPanel from './HistoryPanel';
import StatusBanners from './StatusBanners';
import GlobalShortcuts from './GlobalShortcuts';
import '../styles/layout.css';

function Layout({ children }) {
  const location = useLocation();
  const showChatBar = location.pathname === '/chat';

  return (
    <div className="app">
      <GlobalShortcuts />
      <a href="#page-main" className="skip-link">
        Skip to main content
      </a>
      <header className="app-top-status" aria-label="Connection status">
        <StatusBanners />
      </header>
      <div className="app-body">
        <Sidebar />
        <HistoryPanel />
        <main id="page-main" className="main" tabIndex={-1}>
          <div className="page-content">
            {children}
          </div>
          {showChatBar ? <BottomBar /> : null}
        </main>
      </div>
    </div>
  );
}

export default Layout;
