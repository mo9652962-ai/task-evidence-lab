import type { Task } from './types'

export type GraphNodeKind = 'task' | 'criterion' | 'evidence' | 'run' | 'review'

export interface EvidenceGraphNode {
  id: string
  kind: GraphNodeKind
  label: string
  status: string
}

export interface EvidenceGraphEdge {
  from: string
  to: string
}

export interface EvidenceGraph {
  nodes: EvidenceGraphNode[]
  edges: EvidenceGraphEdge[]
}

export function buildEvidenceGraph(task: Task): EvidenceGraph {
  const nodes: EvidenceGraphNode[] = [{ id: `task-${task.id}`, kind: 'task', label: task.title, status: task.status }]
  const edges: EvidenceGraphEdge[] = []
  const add = (node: EvidenceGraphNode) => {
    nodes.push(node)
    edges.push({ from: `task-${task.id}`, to: node.id })
  }
  task.criteria.forEach((item) => add({ id: `criterion-${item.id}`, kind: 'criterion', label: item.title, status: item.status }))
  task.evidence.forEach((item) => add({ id: `evidence-${item.id}`, kind: 'evidence', label: item.title, status: item.verification_status }))
  task.runs.forEach((item) => add({ id: `run-${item.id}`, kind: 'run', label: `运行：${item.executor}`, status: item.status }))
  task.reviews.forEach((item) => add({ id: `review-${item.id}`, kind: 'review', label: `复盘：${item.reviewer}`, status: 'human_confirmed' }))
  return { nodes, edges }
}
