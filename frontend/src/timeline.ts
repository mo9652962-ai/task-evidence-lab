export type TimelineKind = 'evidence' | 'run' | 'evaluation' | 'review'

export interface TimelineEvent {
  kind: TimelineKind
  id: number
  title: string
  status: string
  detail: string
  occurred_at: string
}

export interface CompareRow {
  id: number
  title: string
  status?: string
  evidence_count?: number
  confirmed_evidence?: number
  unfinished_criteria?: string[]
  test_pass_rate: number | null
  duration_seconds: number
  tool_calls: number
  risk_flags: string[]
  run_breakdown?: RunBreakdown[]
}

export interface RunBreakdown {
  id: number
  executor: string
  model?: string
  status: string
  duration_seconds: number
  tool_calls: number
  failed_tool_calls: number
  tests: { total: number; passed: number; skipped: number; failed: number }
  changed_files: number
  risk_flags: string[]
}

export function timelineKindLabel(kind: TimelineKind): string {
  return ({
    evidence: '成果证据',
    run: '运行记录（仅展示）',
    evaluation: '确定性评测（系统推断）',
    review: '人工复盘',
  })[kind]
}

export function compareMetricRows(row: CompareRow): [string, string][] {
  return [
    ['测试通过率', row.test_pass_rate === null ? '未记录' : `${Math.round(row.test_pass_rate * 100)}%`],
    ['耗时', `${row.duration_seconds} 秒`],
    ['工具调用', `${row.tool_calls} 次`],
    ['风险标记', `${row.risk_flags.length} 条`],
  ]
}
