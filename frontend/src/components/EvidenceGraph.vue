<script setup lang="ts">
import { computed } from 'vue'
import type { Task } from '../types'
import { buildEvidenceGraph } from '../evidenceGraph'

const props = defineProps<{ task: Task }>()
const graph = computed(() => buildEvidenceGraph(props.task))
const groups = ['criterion', 'evidence', 'run', 'review'] as const
const groupLabels = { criterion: '验收项', evidence: '证据', run: '运行', review: '复盘' }
const graphHeight = computed(() => Math.max(260, ...groups.map((kind) => graph.value.nodes.filter((node) => node.kind === kind).length * 48 + 50)))
const positions = computed(() => {
  const result = new Map<string, { x: number; y: number }>()
  result.set(`task-${props.task.id}`, { x: 72, y: graphHeight.value / 2 })
  groups.forEach((kind, groupIndex) => {
    graph.value.nodes.filter((node) => node.kind === kind).forEach((node, index, list) => {
      result.set(node.id, { x: 220 + groupIndex * 155, y: (graphHeight.value - (list.length - 1) * 48) / 2 + index * 48 })
    })
  })
  return result
})
function position(id: string) { return positions.value.get(id) ?? { x: 0, y: 0 } }
function shortLabel(label: string) { return label.length > 18 ? `${label.slice(0, 18)}…` : label }
</script>

<template>
  <div class="evidence-graph">
    <div class="section-heading"><h4>证据关联图</h4><span>只展示与当前任务的已记录关系，不推断证据之间的因果关系</span></div>
    <svg :viewBox="`0 0 820 ${graphHeight}`" role="img" aria-label="任务证据关联图">
      <defs><marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#6b7f9f" /></marker></defs>
      <line v-for="edge in graph.edges" :key="`${edge.from}-${edge.to}`" :x1="position(edge.from).x + 82" :y1="position(edge.from).y" :x2="position(edge.to).x - 70" :y2="position(edge.to).y" stroke="#3a4b67" stroke-width="1.5" marker-end="url(#graph-arrow)" />
      <g v-for="node in graph.nodes" :key="node.id" :transform="`translate(${position(node.id).x}, ${position(node.id).y - 18})`" :class="`graph-node graph-node-${node.kind}`">
        <rect x="-70" y="-18" width="140" height="36" rx="8" />
        <text x="0" y="-1" text-anchor="middle">{{ shortLabel(node.label) }}</text>
        <text x="0" y="12" text-anchor="middle" class="graph-status">{{ node.status }}</text>
      </g>
    </svg>
    <div class="graph-legend"><span v-for="kind in ['task', ...groups]" :key="kind" :class="`legend-${kind}`">{{ kind === 'task' ? '任务' : groupLabels[kind as keyof typeof groupLabels] }}</span></div>
  </div>
</template>
