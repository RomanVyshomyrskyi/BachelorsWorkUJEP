import type { ImportCheckResult } from '../types';

interface Props {
  data: ImportCheckResult;
}

function ImportResults({ data }: Props) {
  return (
    <div>
      <div className="card">
        <div className="results-header">
          <div className="card-title" style={{ marginBottom: 0 }}>Import Readiness</div>
          <span className={`results-badge ${data.can_import ? 'badge-success' : 'badge-danger'}`}>
            {data.can_import ? '✓ Can Import' : '✗ Cannot Import'}
          </span>
        </div>

        <div style={{ fontSize: '0.9rem', color: 'var(--text-light)', marginTop: '0.5rem' }}>
          Dashboard: <strong>{data.dashboard.name}</strong> from <strong>{data.dashboard.source_server}</strong> → <strong>{data.target_server}</strong>
        </div>

        <div className="summary-grid" style={{ marginTop: '1rem' }}>
          <div className="summary-card">
            <div className="summary-card-value" style={{ color: data.summary.databases_missing === 0 ? 'var(--success)' : 'var(--danger)' }}>
              {data.summary.databases_checked - data.summary.databases_missing}/{data.summary.databases_checked}
            </div>
            <div className="summary-card-label">Databases</div>
          </div>
          <div className="summary-card">
            <div className="summary-card-value" style={{ color: data.summary.datasets_missing === 0 ? 'var(--success)' : 'var(--danger)' }}>
              {data.summary.datasets_checked - data.summary.datasets_missing}/{data.summary.datasets_checked}
            </div>
            <div className="summary-card-label">Datasets</div>
          </div>
          <div className="summary-card">
            <div className="summary-card-value" style={{ color: data.summary.chart_issues === 0 ? 'var(--success)' : 'var(--danger)' }}>
              {data.summary.charts_checked - data.summary.chart_issues}/{data.summary.charts_checked}
            </div>
            <div className="summary-card-label">Charts</div>
          </div>
        </div>
      </div>

      {data.blockers.length > 0 && (
        <div className="card" style={{ borderLeft: '3px solid var(--danger)' }}>
          <div className="card-title" style={{ color: 'var(--danger)' }}>⚠ Blockers</div>
          {data.blockers.map((b, i) => (
            <div key={i} className="result-item" style={{ marginBottom: '0.5rem', borderLeftColor: 'var(--danger)' }}>
              <div className="result-item-value" style={{ color: 'var(--text)' }}>{b}</div>
            </div>
          ))}
        </div>
      )}

      {data.recommendations.length > 0 && (
        <div className="card" style={{ borderLeft: '3px solid var(--warning)' }}>
          <div className="card-title" style={{ color: 'var(--warning)' }}>💡 Recommendations</div>
          {data.recommendations.map((r, i) => (
            <div key={i} className="result-item" style={{ marginBottom: '0.5rem', borderLeftColor: 'var(--warning)' }}>
              <div className="result-item-value" style={{ color: 'var(--text)' }}>{r}</div>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <div className="card-title">Detailed Checks</div>

        <h4 style={{ fontSize: '0.9rem', marginBottom: '0.75rem', color: 'var(--text-light)' }}>Databases</h4>
        {data.checks.databases.map((db, i) => (
          <div key={i} className="result-item" style={{ marginBottom: '0.5rem', borderLeftColor: db.exists_on_target ? 'var(--success)' : 'var(--danger)' }}>
            <div className="result-item-title">
              {db.source_name || `DB ID ${db.source_id}`}
            </div>
            <div className="result-item-value">
              Exists on target: {db.exists_on_target ? '✓' : '✗'}
              {db.target_id && ` (Target ID: ${db.target_id})`}
            </div>
          </div>
        ))}

        <h4 style={{ fontSize: '0.9rem', marginBottom: '0.75rem', marginTop: '1rem', color: 'var(--text-light)' }}>Datasets</h4>
        {data.checks.datasets.map((ds, i) => (
          <div key={i} className="result-item" style={{ marginBottom: '0.5rem', borderLeftColor: ds.exists_on_target ? 'var(--success)' : 'var(--danger)' }}>
            <div className="result-item-title">
              {ds.source_name || `Dataset ID ${ds.source_id}`} [{ds.type}]
            </div>
            <div className="result-item-value">
              Exists on target: {ds.exists_on_target ? '✓' : '✗'}
              {ds.target_id && ` (Target ID: ${ds.target_id})`}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ImportResults;
