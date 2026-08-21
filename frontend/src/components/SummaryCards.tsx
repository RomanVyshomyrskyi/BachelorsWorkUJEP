import type { ExportResult } from '../types';

interface Props {
  summary: ExportResult['summary'];
  dashboard: ExportResult['dashboard'];
}

function SummaryCards({ summary, dashboard }: Props) {
  return (
    <div className="summary-grid">
      <div className="summary-card">
        <div className="summary-card-value">{dashboard.chart_count}</div>
        <div className="summary-card-label">Charts</div>
      </div>
      <div className="summary-card">
        <div className="summary-card-value">{summary.total_datasets}</div>
        <div className="summary-card-label">Datasets</div>
      </div>
      <div className="summary-card">
        <div className="summary-card-value">{summary.total_databases}</div>
        <div className="summary-card-label">Databases</div>
      </div>
      <div className="summary-card">
        <div className="summary-card-value">{summary.total_tables}</div>
        <div className="summary-card-label">Tables</div>
      </div>
      <div className="summary-card">
        <div className="summary-card-value">{summary.total_sql_queries}</div>
        <div className="summary-card-label">SQL Queries</div>
      </div>
    </div>
  );
}

export default SummaryCards;
