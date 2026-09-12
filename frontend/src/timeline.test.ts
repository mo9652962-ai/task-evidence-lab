import { describe, expect, it } from 'vitest'
import { compareMetricRows, timelineKindLabel } from './timeline'

describe('timeline and comparison presentation', () => {
  it('labels timeline events without turning system inference into certainty', () => {
    expect(timelineKindLabel('evaluation')).toBe('确定性评测（系统推断）')
    expect(timelineKindLabel('review')).toBe('人工复盘')
  })

  it('returns comparable metric rows with explicit missing values', () => {
    expect(compareMetricRows({ id: 1, title: '任务 A', test_pass_rate: 0.5, duration_seconds: 120, tool_calls: 2, risk_flags: ['.env'] })).toEqual([
      ['测试通过率', '50%'], ['耗时', '120 秒'], ['工具调用', '2 次'], ['风险标记', '1 条'],
    ])
    expect(compareMetricRows({ id: 2, title: '任务 B', test_pass_rate: null, duration_seconds: 0, tool_calls: 0, risk_flags: [] })[0]).toEqual(['测试通过率', '未记录'])
  })
})
