export default function TransactionRow({ txn, statusColors }) {
  const riskClass =
    txn.risk_level === 'HIGH'   ? 'badge-high' :
    txn.risk_level === 'MEDIUM' ? 'badge-medium' : 'badge-low';

  const statusClass = statusColors[txn.status] || 'badge-pending';

  const fmtAmt = (n, cur) =>
    `${cur} ${Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  return (
    <tr>
      <td>
        <span className="mono" style={{ fontSize:'0.8rem', color:'var(--accent-blue)' }}>
          {txn.ref}
        </span>
      </td>
      <td style={{ color:'var(--text-secondary)' }}>{txn.corridor}</td>
      <td>
        <span className="mono" style={{ fontSize:'0.8rem' }}>
          {fmtAmt(txn.amount, txn.source_currency)}
        </span>
      </td>
      <td>
        <span className={`badge ${riskClass}`}>{txn.risk_level}</span>
      </td>
      <td>
        {txn.rail ? (
          <span className="mono" style={{ fontSize:'0.78rem', color:'var(--text-secondary)' }}>
            {txn.rail}
          </span>
        ) : <span style={{ color:'var(--text-muted)' }}>—</span>}
      </td>
      <td>
        <span className={`badge ${statusClass}`}>
          {txn.status.replace('_', ' ')}
        </span>
      </td>
    </tr>
  );
}
