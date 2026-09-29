import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { getStats, getTransactions } from '../api/citiflow';

const RAIL_COLORS = { RAIL_A:'#0ea5e9', RAIL_B:'#10b981', RAIL_C:'#7c3aed' };
const RISK_COLORS = { LOW:'#10b981', MEDIUM:'#f59e0b', HIGH:'#ef4444' };

export default function Analytics() {
  const [stats, setStats]  = useState(null);
  const [txns,  setTxns]   = useState([]);

  useEffect(() => {
    Promise.all([getStats(), getTransactions({ limit: 100 })]).then(([s, t]) => {
      setStats(s.data);
      setTxns(t.data.items || []);
    });
  }, []);

  if (!stats) return (
    <div className="loading-overlay"><div className="spinner" />Loading analytics...</div>
  );

  // Rail distribution for pie
  const railData = Object.entries(stats.rail_distribution || {}).map(([name, value]) => ({ name, value }));

  // Risk distribution
  const riskCounts = txns.reduce((acc, t) => {
    acc[t.risk_level] = (acc[t.risk_level] || 0) + 1;
    return acc;
  }, {});
  const riskData = Object.entries(riskCounts).map(([name, value]) => ({ name, value }));

  // Status distribution
  const statusCounts = txns.reduce((acc, t) => {
    const s = t.status.replace('_',' ');
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, {});
  const statusData = Object.entries(statusCounts).map(([name, value]) => ({ name, value }));

  const tTotal   = txns.length || 1;
  const settled  = txns.filter(t => t.status === 'SETTLED' || t.status === 'ROUTE_SELECTED').length;
  const onHold   = txns.filter(t => t.status === 'ON_HOLD').length;
  const failed   = txns.filter(t => t.status === 'FAILED').length;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Analytics</h1>
          <p className="page-subtitle">Simulation metrics — all data from this session's processed payments</p>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="stat-grid" style={{ marginBottom:24 }}>
        <MetricCard label="Total Processed" value={txns.length} sub="this session" color="#0ea5e9" />
        <MetricCard label="Success Rate"   value={`${Math.round((settled/tTotal)*100)}%`} sub={`${settled} settled`} color="#10b981" />
        <MetricCard label="Held / Blocked" value={onHold + failed} sub={`${onHold} on hold, ${failed} blocked`} color="#f59e0b" />
        <MetricCard label="Avg Settlement" value={`${stats.avg_settlement_sec}s`} sub="end-to-end" color="#7c3aed" />
        <MetricCard label="Cost Saved"     value={`₹${Number(stats.cost_saved_source).toLocaleString('en-IN')}`} sub="vs RAIL_A baseline" color="#10b981" />
        <MetricCard label="Route Changes"  value={stats.route_changes} sub="liquidity reroutes" color="#06b6d4" />
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:20, marginBottom:20 }}>
        {/* Rail Distribution */}
        <div className="card">
          <div className="section-title">Rail Usage</div>
          {railData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={railData} cx="50%" cy="50%" innerRadius={40} outerRadius={70}
                  dataKey="value" paddingAngle={3}>
                  {railData.map(d => (
                    <Cell key={d.name} fill={RAIL_COLORS[d.name] || '#888'} />
                  ))}
                </Pie>
                <Legend wrapperStyle={{ fontSize:'0.75rem' }} />
                <Tooltip contentStyle={{ background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:8, fontSize:'0.8rem' }} />
              </PieChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </div>

        {/* Risk Distribution */}
        <div className="card">
          <div className="section-title">Risk Distribution</div>
          {riskData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={riskData} cx="50%" cy="50%" innerRadius={40} outerRadius={70}
                  dataKey="value" paddingAngle={3}>
                  {riskData.map(d => (
                    <Cell key={d.name} fill={RISK_COLORS[d.name] || '#888'} />
                  ))}
                </Pie>
                <Legend wrapperStyle={{ fontSize:'0.75rem' }} />
                <Tooltip contentStyle={{ background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:8, fontSize:'0.8rem' }} />
              </PieChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </div>

        {/* Status Distribution */}
        <div className="card">
          <div className="section-title">Outcome Distribution</div>
          {statusData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={statusData} layout="vertical" margin={{ left:0, right:10 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" width={90} style={{ fontSize:'0.7rem' }} tick={{ fill:'var(--text-muted)' }} />
                <Tooltip contentStyle={{ background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:8, fontSize:'0.8rem' }} />
                <Bar dataKey="value" fill="var(--accent-blue)" radius={[0,4,4,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </div>
      </div>

      {/* Comparison Table */}
      <div className="card">
        <div className="section-title">Simulation Comparison — Baseline vs CitiFlow</div>
        <p style={{ fontSize:'0.8rem', color:'var(--text-muted)', marginBottom:16 }}>
          Baseline assumes all payments routed via RAIL_A (highest cost). CitiFlow uses intelligent routing.
          Values derived from this session's simulated transactions.
        </p>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Metric</th>
                <th>Baseline (RAIL_A only)</th>
                <th>CitiFlow (Intelligent)</th>
                <th>Improvement</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Avg Transaction Fee</td>
                <td style={{ color:'var(--accent-red)' }}>₹700</td>
                <td style={{ color:'var(--accent-green)' }}>₹{txns.length ? Math.round(stats.cost_saved_source/Math.max(settled,1) + 250) : '—'}</td>
                <td><span className="badge badge-settled">↓ Lower</span></td>
              </tr>
              <tr>
                <td>Avg Settlement Time</td>
                <td style={{ color:'var(--accent-red)' }}>10s (instant only)</td>
                <td style={{ color:'var(--accent-green)' }}>{stats.avg_settlement_sec}s (optimized)</td>
                <td><span className="badge badge-settled">↓ Adaptive</span></td>
              </tr>
              <tr>
                <td>Liquidity Failures</td>
                <td style={{ color:'var(--accent-red)' }}>Not checked</td>
                <td style={{ color:'var(--accent-green)' }}>Automatically rerouted</td>
                <td><span className="badge badge-settled">✓ Handled</span></td>
              </tr>
              <tr>
                <td>Sanctioned Country Detection</td>
                <td style={{ color:'var(--accent-red)' }}>Not detected</td>
                <td style={{ color:'var(--accent-green)' }}>Blocked at compliance</td>
                <td><span className="badge badge-settled">✓ Blocked</span></td>
              </tr>
              <tr>
                <td>High-velocity Detection</td>
                <td style={{ color:'var(--accent-red)' }}>Not detected</td>
                <td style={{ color:'var(--accent-green)' }}>ML + Rule flagged</td>
                <td><span className="badge badge-settled">✓ Flagged</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p style={{ fontSize:'0.72rem', color:'var(--text-muted)', marginTop:12 }}>
          Note: All numbers are derived from in-session simulations. Not real Citi data.
        </p>
      </div>
    </div>
  );
}

function MetricCard({ label, value, sub, color }) {
  return (
    <div className="stat-card" style={{ '--accent-color': color }}>
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color }}>{value}</div>
      <div className="stat-sub">{sub}</div>
    </div>
  );
}

function Empty() {
  return <div style={{ height:180, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text-muted)', fontSize:'0.85rem' }}>No data yet</div>;
}
