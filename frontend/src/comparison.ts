import type { CompareRow } from './timeline'

export type ComparisonFilter = 'all' | 'risk' | 'unfinished' | 'multiple_runs'
export type ComparisonMetric = 'pass_rate' | 'duration' | 'tool_calls'

export function filterComparisonRows(rows: CompareRow[], filter: ComparisonFilter): CompareRow[] {
  if (filter === 'risk') return rows.filter((row) => row.risk_flags.length > 0)
  if (filter === 'unfinished') return rows.filter((row) => (row.unfinished_criteria?.length ?? 0) > 0)
  if (filter === 'multiple_runs') return rows.filter((row) => (row.run_breakdown?.length ?? 0) > 1)
  return rows
}

function metricValue(row: CompareRow, metric: ComparisonMetric): number | null {
  if (metric === 'pass_rate') return row.test_pass_rate
  if (metric === 'duration') return row.duration_seconds
  return row.tool_calls
}

export function comparisonBarPercent(value: number | null, rows: CompareRow[], metric: ComparisonMetric): number {
  if (value === null) return 0
  const max = Math.max(...rows.map((row) => metricValue(row, metric) ?? 0), 0)
  if (metric === 'pass_rate') return Math.round(value * 100)
  return max === 0 ? 0 : Math.round((value / max) * 100)
}
