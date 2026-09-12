<script setup lang="ts">
import type { Task } from '../types'
import StatusBadge from './StatusBadge.vue'

defineProps<{
  visibleTasks: Task[]
  selectedId?: number
  loading: boolean
  filter: 'all' | Task['status']
  includeArchived: boolean
  searchQuery: string
}>()

const emit = defineEmits<{
  (event: 'select', task: Task): void
  (event: 'update:filter', value: 'all' | Task['status']): void
  (event: 'update:includeArchived', value: boolean): void
  (event: 'update:searchQuery', value: string): void
  (event: 'search'): void
}>()

const statusNames: Record<string, string> = { draft: '草稿', in_progress: '进行中', blocked: '已阻塞', partially_verified: '部分验证', completed: '已完成', archived: '已归档' }
function statusLabel(status: string) { return statusNames[status] ?? status }
</script>

<template>
  <aside class="panel task-panel">
    <div class="panel-title">
      <div><small>WORKBOARD</small><h3>任务列表</h3></div>
      <div class="task-filters">
        <input :value="searchQuery" aria-label="搜索任务" placeholder="搜索标题或目标" @input="emit('update:searchQuery', ($event.target as HTMLInputElement).value); emit('search')" />
        <select :value="filter" @change="emit('update:filter', ($event.target as HTMLSelectElement).value as 'all' | Task['status'])">
          <option value="all">全部</option><option value="draft">草稿</option><option value="in_progress">进行中</option><option value="blocked">已阻塞</option><option value="partially_verified">部分验证</option><option value="completed">已完成</option><option value="archived">已归档</option>
        </select>
        <label><input :checked="includeArchived" type="checkbox" @change="emit('update:includeArchived', ($event.target as HTMLInputElement).checked)" /> 含已归档</label>
      </div>
    </div>
    <div v-if="loading" class="empty">正在加载任务…</div>
    <button v-for="task in visibleTasks" :key="task.id" class="task-row" :class="{ selected: selectedId === task.id }" @click="emit('select', task)">
      <div><strong>{{ task.title }}</strong><span>{{ task.criteria_count ?? 0 }} 个验收项 · {{ task.evidence_count ?? 0 }} 条证据</span></div>
      <StatusBadge :status="task.status" :label="statusLabel(task.status)" />
    </button>
    <div v-if="!loading && !visibleTasks.length" class="empty">暂无符合条件的任务</div>
  </aside>
</template>
