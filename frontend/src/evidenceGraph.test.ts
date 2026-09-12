import { describe, expect, it } from 'vitest'
import { buildEvidenceGraph } from './evidenceGraph'
import type { Task } from './types'

describe('evidence relationship graph', () => {
  it('connects task-centered records without inventing evidence causality', () => {
    const task = {
      id: 7, title: '图谱任务', status: 'in_progress', priority: 'medium', description: '', completion_basis: '', created_at: '', updated_at: '',
      criteria: [{ id: 1, task_id: 7, title: '验收', required: 1, status: 'verified', note: '' }],
      evidence: [{ id: 2, task_id: 7, title: '截图', evidence_type: '截图', content: '', source: 'manual', verification_status: 'confirmed', review_note: '', created_at: '' }],
      runs: [{ id: 3, executor: 'manual', status: 'completed', created_at: '' }],
      reviews: [{ id: 4, reviewer: 'human', content: '确认', created_at: '' }],
      evaluation: null,
    } as Task

    const graph = buildEvidenceGraph(task)

    expect(graph.nodes.map((node) => node.id)).toEqual(['task-7', 'criterion-1', 'evidence-2', 'run-3', 'review-4'])
    expect(graph.edges).toEqual([
      { from: 'task-7', to: 'criterion-1' },
      { from: 'task-7', to: 'evidence-2' },
      { from: 'task-7', to: 'run-3' },
      { from: 'task-7', to: 'review-4' },
    ])
  })
})
