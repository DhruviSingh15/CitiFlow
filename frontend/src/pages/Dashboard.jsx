import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, TrendingUp, AlertTriangle, Clock, Activity, Droplets, GitBranch } from 'lucide-react';
import { getStats, getTransactions, getLiquidity } from '../api/citiflow';
import TransactionRow from '../components/TransactionRow';

const STATUS_COLORS = {
  SETTLED:            'badge-settled',
  ON_HOLD:            'badge-on-hold',
  FAILED:             'badge-failed',
  ROUTE_SELECTED:     'badge-route',
  SETTLEMENT_PENDING: 'badge-pending',
  INITIATED:          'badge-pending',
};

const RAIL_COLORS = { RAIL_A: '#0ea5e9', RAIL_B: '#10b981', RAIL_C: '#7c3aed' };

export default function Dashboard() {
  const [stats,    setStats]    = useState(null);
  const [txns,     setTxns]     = useState([]);
  const [liquidity,setLiquidity]= useState([]);
  const [loading,  setLoading]  = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);

  const load = useCallback(async () => {
    try {
      const [s, t, l] = await Promise.all([
        getStats(), getTransactions({ limit: 20 }), getLiquidity()
      ]);
      setStats(s.data);
      setTxns(t.data.items || []);
      setLiquidity(l.data.rails || []);
      setLastRefresh(new Date());
    } catch (e) {
      console.error('Dashboard load failed:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  const fmt = (n, prefix = '₹') =>
    n == null ? '—' : `${prefix}${Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  if (loading) return (
    <div className="loading-overlay">
      <div className="spinner" />
      Connecting to CitiFlow...
    </div>
  );

  return (
    <div>
      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Control Tower</h1>
          <p className="page-subtitle">
            Live orchestration dashboard — all values from simulated payment pipeline
          </p>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          <div className="live-indicator">
            <div className="live-dot" /> LIVE
          </div>
          <button className="btn btn-secondary btn-sm" onClick={load}>
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
      </div>

      {/* ── Stats Grid ── */}
      {stats && (
        <div className="stat-grid">
          <StatCard
            label="Active Payments"
            value={stats.active_payments}
            sub="in pipeline"
            color="#0ea5e9"
            icon={<Activity size={16} />}
          />
          <StatCard
            label="Total Volume"
            value={fmt(stats.volume_source)}
            sub="processed today"
            color="#7c3aed"
            icon={<TrendingUp size={16} />}
          />
          <StatCard
            label="Avg Settlement"
            value={`${stats.avg_settlement_sec}s`}
            sub="end-to-end"
            color="#10b981"
            icon={<Clock size={16} />}
          />
          <StatCard
            label="High Risk"
            value={stats.high_risk_count}
            sub="flagged transactions"
            color="#ef4444"
            icon={<AlertTriangle size={16} />}
          />
          <StatCard
            label="On Hold"
            value={stats.on_hold_count}
            sub="awaiting review"
            color="#f59e0b"
            icon={<AlertTriangle size={16} />}
          />
          <StatCard
            label="Route Changes"
            value={stats.route_changes}
            sub="liquidity reroutes"
            color="#06b6d4"
            icon={<GitBranch size={16} />}
          />
          <StatCard
            label="Cost Saved"
            value={fmt(stats.cost_saved_source)}
            sub="vs max-cost rail"
            color="#10b981"
            icon={<TrendingUp size={16} />}
          />
          <StatCard
            label="Liq. Alerts"
            value={stats.liquidity_alerts}
            sub="rails below threshold"
            color={stats.liquidity_alerts > 0 ? '#ef4444' : '#10b981'}
            icon={<Droplets size={16} />}
          />
        </div>
      )}

      <div style={{ display:'grid', gridTemplateColumns:'1fr 280px', gap:20, alignItems:'start' }}>
        {/* ── Live Transactions ── */}
        <div className="card" style={{ padding:0, overflow:'hidden' }}>
          <div style={{ padding:'20px 24px', borderBottom:'1px solid var(--border)', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <h3>Live Transactions</h3>
            <span style={{ fontSize:'0.75rem', color:'var(--text-muted)' }}>
              {lastRefresh ? `Updated ${lastRefresh.toLocaleTimeString()}` : ''}
            </span>
          </div>

          {txns.length === 0 ? (
            <div className="loading-overlay" style={{ padding:40 }}>
              No transactions yet — submit a payment to get started
            </div>
          ) : (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Reference</th>
                    <th>Corridor</th>
                    <th>Amount</th>
                    <th>Risk</th>
                    <th>Rail</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {txns.map(t => (
                    <TransactionRow key={t.ref} txn={t} statusColors={STATUS_COLORS} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Right Panel ── */}
        <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
          {/* Rail Distribution */}
          {stats?.rail_distribution && Object.keys(stats.rail_distribution).length > 0 && (
            <div className="card">
              <div className="section-title">Rail Usage</div>
              {Object.entries(stats.rail_distribution).map(([rail, count]) => {
                const total = Object.values(stats.rail_distribution).reduce((a,b)=>a+b,0);
                const pct   = Math.round((count / total) * 100);
                return (
                  <div key={rail} style={{ marginBottom:10 }}>
                    <div style={{ display:'flex', justifyContent:'space-between', fontSize:'0.8rem', marginBottom:4 }}>
                      <span style={{ color:'var(--text-secondary)', fontWeight:600 }}>{rail}</span>
                      <span style={{ color:'var(--text-muted)' }}>{count} ({pct}%)</span>
                    </div>
                    <div style={{ height:5, background:'var(--bg-input)', borderRadius:100, overflow:'hidden' }}>
                      <div style={{ height:'100%', width:`${pct}%`, background: RAIL_COLORS[rail] || 'var(--accent-blue)', borderRadius:100, transition:'width 0.6s ease' }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Liquidity State */}
          <div className="card">
            <div className="section-title">Rail Liquidity</div>
            {liquidity.map(pool => {
              const pct = Math.min((pool.net_available / pool.available) * 100, 100);
              return (
                <div key={pool.rail_id} style={{ marginBottom:12 }}>
                  <div style={{ display:'flex', justifyContent:'space-between', fontSize:'0.8rem', marginBottom:4 }}>
                    <span style={{ color: pool.alert ? 'var(--accent-red)' : 'var(--text-secondary)', fontWeight:600 }}>
                      {pool.rail_id} {pool.alert ? '⚠' : ''}
                    </span>
                    <span style={{ color:'var(--text-muted)', fontFamily:'monospace', fontSize:'0.72rem' }}>
                      ₹{(pool.net_available/100000).toFixed(1)}L
                    </span>
                  </div>
                  <div style={{ height:5, background:'var(--bg-input)', borderRadius:100, overflow:'hidden' }}>
                    <div style={{
                      height:'100%', width:`${pct}%`,
                      background: pool.alert ? 'var(--accent-red)' : 'var(--accent-green)',
                      borderRadius:100, transition:'width 0.6s ease'
                    }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, color, icon }) {
  return (
    <div className="stat-card" style={{ '--accent-color': color }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:8 }}>
        <div className="stat-label">{label}</div>
        <span style={{ color, opacity:0.7 }}>{icon}</span>
      </div>
      <div className="stat-value" style={{ color }}>{value}</div>
      <div className="stat-sub">{sub}</div>
    </div>
  );
}
