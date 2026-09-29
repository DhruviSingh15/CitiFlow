import { useState } from 'react';
import { LayoutDashboard, Send, Activity, Zap, Shield } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import NewPayment from './pages/NewPayment';
import Analytics  from './pages/Analytics';
import './index.css';

const NAV = [
  { id: 'dashboard', label: 'Control Tower',  icon: LayoutDashboard },
  { id: 'payment',   label: 'New Payment',     icon: Send },
  { id: 'analytics', label: 'Analytics',        icon: Activity },
];

export default function App() {
  const [page, setPage] = useState('dashboard');

  const Page =
    page === 'dashboard' ? Dashboard :
    page === 'payment'   ? NewPayment :
    Analytics;

  return (
    <div className="app-layout">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-mark">
            <span className="logo-dot" />
            CitiFlow
          </div>
          <div className="logo-sub">Intelligent Payment Orchestration</div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">Navigation</div>
          {NAV.map(({ id, label, icon: Icon }) => (
            <div
              key={id}
              className={`nav-item ${page === id ? 'active' : ''}`}
              onClick={() => setPage(id)}
            >
              <Icon size={16} />
              {label}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:4 }}>
            <Shield size={11} />
            <span style={{ color:'var(--accent-green)', fontWeight:600 }}>All systems operational</span>
          </div>
          <div>API: localhost:8001</div>
          <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: '0.62rem' }}>
            Prototype — simulated rails only
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main-content">
        <Page />
      </main>
    </div>
  );
}
