import type { ExportResult } from '../types';

interface Props {
  data: ExportResult;
}

function ExportResults({ data }: Props) {
  return (
    <div className="card">
      <div className="card-title">Dashboard Details</div>

      <div className="results-grid results-grid-2">
        {data.databases.length > 0 && (
          <div className="result-item">
            <div className="result-item-title">Databases</div>
            {data.databases.map(db => (
              <div key={db.id} className="result-item-value">
                {db.name} ({db.engine})
              </div>
            ))}
          </div>
        )}

        {data.datasets.length > 0 && (
          <div className="result-item">
            <div className="result-item-title">Datasets</div>
            {data.datasets.map(ds => (
              <div key={ds.id} className="result-item-value">
                {ds.name} [{ds.type}]
                {ds.schema && ` (${ds.schema})`}
              </div>
            ))}
          </div>
        )}

        <div className="result-item" style={{ gridColumn: '1 / -1' }}>
          <div className="result-item-title">Charts</div>
          {data.charts.map(chart => (
            <div key={chart.id} className="result-item-value">
              {chart.name} ({chart.viz_type})
              {chart.sql_in_params.length > 0 && ` - ${chart.sql_in_params.length} SQL queries`}
            </div>
          ))}
        </div>

        {data.sql_queries.length > 0 && (
          <div className="result-item" style={{ gridColumn: '1 / -1' }}>
            <div className="result-item-title">SQL Queries</div>
            {data.sql_queries.slice(0, 5).map((sq, i) => (
              <details key={i} style={{ marginTop: '0.5rem' }}>
                <summary style={{ cursor: 'pointer', fontSize: '0.8rem' }}>
                  {sq.chart_name}
                </summary>
                <div className="json-viewer" style={{ marginTop: '0.5rem', maxHeight: '200px' }}>
                  {sq.sql}
                </div>
              </details>
            ))}
            {data.sql_queries.length > 5 && (
              <div className="result-item-value" style={{ marginTop: '0.5rem' }}>
                + {data.sql_queries.length - 5} more queries
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ExportResults;
