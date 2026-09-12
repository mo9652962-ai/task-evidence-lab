import { describe, expect, it } from 'vitest'
import { comparisonBarPercent, filterComparisonRows } from './comparison'
import type { CompareRow } from './timeline'

const rows: CompareRow[] = [
  { id: 1, title: '安全任务', test_pass_rate: 1, duration_seconds: 60, tool_calls: 2, risk_flags: ['.env'], unfinished_criteria: [], run_breakdown: [{ id: 1, executor: 'a', status: 'completed', duration_seconds: 60, tool_calls: 2, failed_tool_calls: 0, tests: { total: 1, passed: 1, skipped: 0, failed: 0 }, changed_files: 1, risk_flags: [] }, { id: 2, executor: 'b', status: 'completed', duration_seconds: 30, tool_calls: 1, failed_tool_calls: 0, tests: { total: 1, passed: 1, skipped: 0, failed: 0 }, changed_files: 0, risk_flags: [] }] },
  { id: 2, title: '待补任务', test_pass_rate: 0.5, duration_seconds: 120, tool_calls: 4, risk_flags: [], unfinished_criteria: ['补充测试'], run_breakdown: [] },
]

describe('comparison filters and bars', () => {
  it('filters rows by risk, unfinished criteria, and multiple runs', () => {
    expect(filterComparisonRows(rows, 'risk').map((row) => row.title)).toEqual(['安全任务'])
    expect(filterComparisonRows(rows, 'unfinished').map((row) => row.title)).toEqual(['待补任务'])
    expect(filterComparisonRows(rows, 'multiple_runs').map((row) => row.title)).toEqual(['安全任务'])
  })

  it('normalizes a metric against the comparison maximum', () => {
    expect(comparisonBarPercent(60, rows, 'duration')).toBe(50)
    expect(comparisonBarPercent(null, rows, 'pass_rate')).toBe(0)
  })
})
