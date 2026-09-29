import { useState } from 'react';
import { Send, AlertCircle, CheckCircle, XCircle, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import { processPayment, updateLiquidity } from '../api/citiflow';

const CURRENCIES = ['INR','USD','SGD','GBP','AED','EUR','AUD','JPY','CAD'];
const COUNTRIES  = [
  { code:'IN', name:'India' },    { code:'SG', name:'Singapore' },
  { code:'US', name:'USA' },      { code:'GB', name:'UK' },
  { code:'AE', name:'UAE' },      { code:'DE', name:'Germany' },
  { code:'AU', name:'Australia'}, { code:'JP', name:'Japan' },
  { code:'CA', name:'Canada' },   { code:'FR', name:'France' },
  { code:'RU', name:'Russia' },   { code:'NG', name:'Nigeria' },
  { code:'IR', name:'Iran' },     { code:'KP', name:'North Korea' },
];

const DEMOS = [
  {
    label: 'Scenario A — Normal',
    body: { sender_id:'CORP_001', sender_country:'IN', receiver_id:'VENDOR_SG', receiver_country:'SG', amount:100000, source_currency:'INR', target_currency:'SGD', priority:'NORMAL', account_age_days:730, transaction_velocity_24h:2, recipient_history_days:180 },
  },
  {
    label: 'Scenario B — Suspicious',
    body: { sender_id:'CORP_002', sender_country:'IN', receiver_id:'UNKNOWN', receiver_country:'SG', amount:2500000, source_currency:'INR', target_currency:'SGD', priority:'URGENT', account_age_days:30, transaction_velocity_24h:18, recipient_history_days:0 },
  },
  {
    label: 'Scenario C — Sanctioned',
    body: { sender_id:'CORP_003', sender_country:'IN', receiver_id:'REC_IR', receiver_country:'IR', amount:50000, source_currency:'INR', target_currency:'USD', priority:'NORMAL', account_age_days:500, transaction_velocity_24h:1, recipient_history_days:100 },
  },
  {
    label: 'Scenario D — Bulk RAIL_C',
    body: { sender_id:'CORP_004', sender_country:'IN', receiver_id:'VENDOR_AE', receiver_country:'AE', amount:500000, source_currency:'INR', target_currency:'AED', priority:'BULK', account_age_days:900, transaction_velocity_24h:4, recipient_history_days:200 },
  },
];

export default function NewPayment() {
  const [form, setForm] = useState({
    sender_id: 'CORP_001', sender_country: 'IN',
    receiver_id: 'VENDOR_SG', receiver_country: 'SG',
    amount: 100000, source_currency: 'INR', target_currency: 'SGD',
    priority: 'NORMAL', account_age_days: 730,
    transaction_velocity_24h: 2, recipient_history_days: 180,
  });
  const [loading,  setLoading]  = useState(false);
  const [result,   setResult]   = useState(null);
  const [error,    setError]    = useState(null);
  const [showAdv,  setShowAdv]  = useState(false);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const submit = async (body = null) => {
    setLoading(true); setError(null); setResult(null);
    try {
      const payload = body || form;
      const res = await processPayment(payload);
      setResult(res.data);
      if (body) setForm(body);   // update form to match demo
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  const simulateLiquidityFailure = async () => {
    await updateLiquidity('RAIL_C', { available_amount: 10000, currency: 'INR' });
    alert('RAIL_C liquidity set to ₹10,000 — next payment will reroute!');
  };

  const resetLiquidity = async () => {
    await updateLiquidity('RAIL_C', { available_amount: 1500000, currency: 'INR' });
    alert('RAIL_C liquidity restored to ₹15L');
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">New Payment</h1>
          <p className="page-subtitle">Submit a cross-border payment through the CitiFlow orchestration pipeline</p>
        </div>
      </div>

      {/* ── Demo Scenarios ── */}
      <div className="card" style={{ marginBottom:20 }}>
        <div className="section-title">Quick Demo Scenarios</div>
        <div style={{ display:'flex', flexWrap:'wrap', gap:8 }}>
          {DEMOS.map(d => (
            <button key={d.label} className="btn btn-secondary btn-sm"
              onClick={() => submit(d.body)} disabled={loading}>
              <Zap size={12} /> {d.label}
            </button>
          ))}
          <div style={{ marginLeft:'auto', display:'flex', gap:8 }}>
            <button className="btn btn-danger btn-sm" onClick={simulateLiquidityFailure}>
              Drain RAIL_C Liquidity
            </button>
            <button className="btn btn-secondary btn-sm" onClick={resetLiquidity}>
              Restore RAIL_C
            </button>
          </div>
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, alignItems:'start' }}>
        {/* ── Payment Form ── */}
        <div className="card">
          <h3 style={{ marginBottom:20 }}>Payment Details</h3>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">Sender ID</label>
              <input className="form-input" value={form.sender_id}
                onChange={e => set('sender_id', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Receiver ID</label>
              <input className="form-input" value={form.receiver_id}
                onChange={e => set('receiver_id', e.target.value)} />
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">From Country</label>
              <select className="form-select" value={form.sender_country}
                onChange={e => set('sender_country', e.target.value)}>
                {COUNTRIES.map(c => <option key={c.code} value={c.code}>{c.name} ({c.code})</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">To Country</label>
              <select className="form-select" value={form.receiver_country}
                onChange={e => set('receiver_country', e.target.value)}>
                {COUNTRIES.map(c => <option key={c.code} value={c.code}>{c.name} ({c.code})</option>)}
              </select>
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">Amount</label>
              <input className="form-input" type="number" value={form.amount}
                onChange={e => set('amount', Number(e.target.value))} min={1} />
            </div>
            <div className="form-group">
              <label className="form-label">Priority</label>
              <select className="form-select" value={form.priority}
                onChange={e => set('priority', e.target.value)}>
                <option value="NORMAL">Normal</option>
                <option value="URGENT">Urgent</option>
                <option value="BULK">Bulk</option>
              </select>
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">Source Currency</label>
              <select className="form-select" value={form.source_currency}
                onChange={e => set('source_currency', e.target.value)}>
                {CURRENCIES.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Target Currency</label>
              <select className="form-select" value={form.target_currency}
                onChange={e => set('target_currency', e.target.value)}>
                {CURRENCIES.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
          </div>

          {/* Advanced */}
          <div style={{ marginBottom:16 }}>
            <button className="btn btn-secondary btn-sm" style={{ width:'100%' }}
              onClick={() => setShowAdv(v => !v)}>
              {showAdv ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              Risk Parameters (Advanced)
            </button>
          </div>

          {showAdv && (
            <div style={{ marginBottom:16, padding:16, background:'var(--bg-input)', borderRadius:'var(--radius-sm)', border:'1px solid var(--border)' }}>
              <div className="form-grid-3">
                <div className="form-group">
                  <label className="form-label">Account Age (days)</label>
                  <input className="form-input" type="number" value={form.account_age_days}
                    onChange={e => set('account_age_days', Number(e.target.value))} min={0} />
                </div>
                <div className="form-group">
                  <label className="form-label">Tx Velocity 24h</label>
                  <input className="form-input" type="number" value={form.transaction_velocity_24h}
                    onChange={e => set('transaction_velocity_24h', Number(e.target.value))} min={0} />
                </div>
                <div className="form-group">
                  <label className="form-label">Recipient History (days)</label>
                  <input className="form-input" type="number" value={form.recipient_history_days}
                    onChange={e => set('recipient_history_days', Number(e.target.value))} min={0} />
                </div>
              </div>
            </div>
          )}

          {error && <div className="alert alert-error"><AlertCircle size={15} />{error}</div>}

          <button className="btn btn-primary btn-full btn-lg"
            onClick={() => submit()} disabled={loading}>
            {loading ? <><div className="spinner" />Processing...</> : <><Send size={16} />Process Payment</>}
          </button>
        </div>

        {/* ── Result Panel ── */}
        <div>
          {!result && !loading && (
            <div className="card" style={{ textAlign:'center', padding:48, color:'var(--text-muted)' }}>
              <Send size={32} style={{ margin:'0 auto 12px', opacity:0.3 }} />
              <div>Submit a payment to see the CitiFlow orchestration result</div>
            </div>
          )}

          {loading && (
            <div className="card">
              <div className="loading-overlay" style={{ padding:60 }}>
                <div className="spinner" />
                <div>
                  <div style={{ color:'var(--text-primary)', fontWeight:600 }}>Processing payment...</div>
                  <div style={{ fontSize:'0.78rem', color:'var(--text-muted)', marginTop:4 }}>
                    Risk → Compliance → Liquidity → FX → Route → Settlement
                  </div>
                </div>
              </div>
            </div>
          )}

          {result && <ResultPanel result={result} />}
        </div>
      </div>
    </div>
  );
}

function ResultPanel({ result }) {
  const statusIcon =
    result.status === 'SETTLED'  || result.status === 'ROUTE_SELECTED' ? <CheckCircle size={16} color="var(--accent-green)" /> :
    result.status === 'FAILED'                                           ? <XCircle    size={16} color="var(--accent-red)" /> :
                                                                          <AlertCircle size={16} color="var(--accent-amber)" />;

  const riskColor =
    result.risk.level === 'LOW'  ? 'var(--accent-green)' :
    result.risk.level === 'HIGH' ? 'var(--accent-red)'   : 'var(--accent-amber)';

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
      {/* Status */}
      <div className="card">
        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:16 }}>
          {statusIcon}
          <h3>Result</h3>
          <span className="mono" style={{ marginLeft:'auto', fontSize:'0.8rem', color:'var(--accent-blue)' }}>
            {result.transaction_ref}
          </span>
        </div>
        <div style={{ display:'flex', gap:12, flexWrap:'wrap' }}>
          <span className={`badge badge-${result.status === 'SETTLED' || result.status === 'ROUTE_SELECTED' ? 'settled' : result.status === 'FAILED' ? 'failed' : 'on-hold'}`}>
            {result.status.replace(/_/g,' ')}
          </span>
          <span style={{ fontSize:'0.8rem', color:'var(--text-muted)' }}>
            {result.processing_time_ms}ms
          </span>
        </div>
      </div>

      {/* Risk */}
      <div className="card">
        <div className="section-title">Risk Analysis</div>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
          <div>
            <div style={{ fontSize:'2rem', fontWeight:800, color:riskColor, lineHeight:1 }}>
              {result.risk.score}<span style={{ fontSize:'1rem', color:'var(--text-muted)' }}>/100</span>
            </div>
            <div style={{ fontSize:'0.8rem', color:'var(--text-muted)', marginTop:4 }}>
              {result.risk.level} RISK → {result.risk.decision}
            </div>
          </div>
          <span className={`badge badge-${result.risk.level.toLowerCase()}`} style={{ fontSize:'0.85rem', padding:'6px 14px' }}>
            {result.risk.level}
          </span>
        </div>

        <div className="risk-bar-track" style={{ marginBottom:12 }}>
          <div className={`risk-bar-fill ${result.risk.level.toLowerCase()}`} style={{ width:`${result.risk.score}%` }} />
        </div>

        {result.risk.top_factors?.length > 0 && (
          <>
            <div style={{ fontSize:'0.72rem', color:'var(--text-muted)', marginBottom:8, textTransform:'uppercase', letterSpacing:'0.08em' }}>Top Factors</div>
            <div className="shap-list">
              {result.risk.top_factors.map((f, i) => {
                const isInc = f.direction === 'risk_increasing';
                const w     = Math.min(Math.abs(f.contribution) * 200, 100);
                return (
                  <div key={i} className="shap-row">
                    <div className="shap-label">{f.label || f.feature}</div>
                    <div className="shap-bar-track">
                      <div className={`shap-bar-fill ${isInc ? 'inc' : 'red'}`} style={{ width:`${w}%` }} />
                    </div>
                    <div className="shap-val" style={{ color: isInc ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                      {isInc ? '+' : ''}{(f.contribution * 100).toFixed(1)}%
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Compliance */}
      <div className="card">
        <div className="section-title">Compliance</div>
        <div className={`alert ${result.compliance.passed ? 'alert-success' : result.status === 'FAILED' ? 'alert-error' : 'alert-warning'}`}>
          {result.compliance.passed ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
          {result.compliance.notes}
        </div>
        {result.compliance.rules_triggered?.length > 0 && (
          <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
            {result.compliance.rules_triggered.map(r => (
              <span key={r} className="badge badge-high" style={{ fontSize:'0.68rem' }}>{r.replace(/_/g,' ')}</span>
            ))}
          </div>
        )}
      </div>

      {/* Route */}
      {result.selected_route && (
        <div className="card">
          <div className="section-title">Selected Route</div>
          <div className="rail-grid" style={{ marginBottom:12 }}>
            {result.all_routes_evaluated?.map(r => (
              <div key={r.rail_id} className={`rail-card ${r.rail_id === result.selected_route.rail_id ? 'selected' : ''} ${!r.eligible ? 'rejected' : ''}`}>
                <div className="rail-card-header">
                  <div>
                    <div className="rail-name">{r.rail_name || r.rail_id}</div>
                    <div className="rail-type">{r.eligible ? 'ELIGIBLE' : 'REJECTED'}</div>
                  </div>
                  <div className="rail-score">{r.score}</div>
                </div>
                {!r.eligible && r.ineligible_reason && (
                  <div style={{ fontSize:'0.7rem', color:'var(--accent-red)', marginTop:4 }}>
                    {r.ineligible_reason.substring(0, 60)}…
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="alert alert-info" style={{ margin:0 }}>
            <Zap size={14} /> {result.selected_route.reason}
          </div>
        </div>
      )}

      {/* Settlement */}
      {result.settlement && (
        <div className="card">
          <div className="section-title">Settlement</div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12 }}>
            <div>
              <div className="stat-label">Settlement Time</div>
              <div style={{ fontSize:'1.4rem', fontWeight:800, color:'var(--accent-green)' }}>
                {(result.settlement.settlement_time_ms / 1000).toFixed(1)}s
              </div>
            </div>
            {result.settlement.blockchain?.tx_hash && (
              <div>
                <div className="stat-label">Blockchain Record</div>
                <div className="mono" style={{ fontSize:'0.7rem', color:'var(--accent-blue)', wordBreak:'break-all' }}>
                  {result.settlement.blockchain.tx_hash.substring(0, 20)}…
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
