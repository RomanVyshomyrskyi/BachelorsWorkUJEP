/**
 * @module components/SummaryCards
 * @description Displays summary statistics from a dashboard export result.
 * Shows counts for charts, datasets, databases, tables, and SQL queries.
 */

import type { ExportResult } from '../types';

/**
 * Props for the SummaryCards component.
 *
 * @interface Props
 * @property {ExportResult['summary']} summary - The summary object containing resource counts.
 * @property {ExportResult['dashboard']} dashboard - The dashboard object containing chart count and metadata.
 */
interface Props {
  summary: ExportResult['summary'];
  dashboard: ExportResult['dashboard'];
}

/**
 * Summary cards component displaying export statistics.
 *
 * Renders a grid of cards showing the count of charts, datasets,
 * databases, tables, and SQL queries in the exported dashboard.
 *
 * @component
 * @param {Props} props - The component props.
 * @param {ExportResult['summary']} props.summary - Summary counts from the export.
 * @param {ExportResult['dashboard']} props.dashboard - Dashboard metadata from the export.
 * @returns {JSX.Element} A grid of summary statistic cards.
 *
 * @example
 * <SummaryCards
 *   summary={exportData.summary}
 *   dashboard={exportData.dashboard}
 * />
 */
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
