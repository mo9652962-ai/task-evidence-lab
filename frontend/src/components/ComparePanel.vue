<script setup lang="ts">
import type { Task } from '../types'
import { comparisonBarPercent, filterComparisonRows } from '../comparison'
import { compareMetricRows } from '../timeline'
import type { CompareRow } from '../timeline'
import type { ComparisonFilter } from '../comparison'

defineProps<{
  tasks: Pick<Task, 'id' | 'title'>[]
  left: number | null
  right: number | null
  comparison: CompareRow[]
  filter: ComparisonFilter
}>()

const emit = defineEmits<{
  (event: 'update:left', value: number | null): void
  (event: 'update:right', value: number | null): void
  (event: 'update:filter', value: ComparisonFilter): void
  (event: 'compare'): void
  (event: 'download'): void
}>()
</script>

<template>
  <section class="panel compare-panel">
    <div class="panel-title"><div><small>COMPARISON</small><h3>任务对比</h3></div><span>只比较已记录数据，不重新执行任何 Agent 或命令</span></div>
    <div class="compare-controls">
      <select :value="left" @change="emit('update:left', Number(($event.target as HTMLSelectElement).value) || null)"><option :value="null">选择任务 A</option><option v-for="task in tasks" :key="`left-${task.id}`" :value="task.id">{{ task.title }}</option></select>
      <span>VS</span>
      <select :value="right" @change="emit('update:right', Number(($event.target as HTMLSelectElement).value) || null)"><option :value="null">选择任务 B</option><option v-for="task in tasks" :key="`right-${task.id}`" :value="task.id">{{ task.title }}</option></select>
      <button class="primary" @click="emit('compare')">开始对比</button>
      <button :disabled="!comparison.length" @click="emit('download')">导出批量报告</button>
      <select aria-label="对比筛选" :value="filter" @change="emit('update:filter', ($event.target as HTMLSelectElement).value as ComparisonFilter)"><option value="all">全部结果</option><option value="risk">仅有风险</option><option value="unfinished">有未完成验收</option><option value="multiple_runs">多次运行</option></select>
    </div>
    <div v-if="!comparison.length" class="empty">选择两个任务后查看完成度、证据、测试、耗时、工具调用和风险差异。</div>
    <div v-else-if="!filterComparisonRows(comparison, filter).length" class="empty">当前筛选条件没有匹配结果。</div>
    <div v-else class="comparison-grid">
      <article v-for="row in filterComparisonRows(comparison, filter)" :key="row.title" class="comparison-card">
        <small>任务</small><h4>{{ row.title }}</h4><span class="compare-status">{{ row.status ?? '已记录' }}</span>
        <div class="compare-metric" v-for="metric in compareMetricRows(row)" :key="metric[0]"><span>{{ metric[0] }}</span><b>{{ metric[1] }}</b></div>
        <div class="compare-bars"><div><span>测试通过率</span><i><b :style="{ width: `${comparisonBarPercent(row.test_pass_rate, comparison, 'pass_rate')}%` }"></b></i></div><div><span>相对耗时</span><i><b :style="{ width: `${comparisonBarPercent(row.duration_seconds, comparison, 'duration')}%` }"></b></i></div><div><span>相对工具调用</span><i><b :style="{ width: `${comparisonBarPercent(row.tool_calls, comparison, 'tool_calls')}%` }"></b></i></div></div>
        <div class="compare-metric"><span>证据</span><b>{{ row.evidence_count ?? 0 }} 条 / 已确认 {{ row.confirmed_evidence ?? 0 }} 条</b></div><div class="compare-metric"><span>未完成验收项</span><b>{{ row.unfinished_criteria?.length ?? 0 }} 项</b></div>
        <div v-if="row.run_breakdown?.length" class="run-breakdown"><h5>单次运行明细</h5><div v-for="run in row.run_breakdown" :key="run.id" class="breakdown-row"><b>#{{ run.id }} {{ run.executor }}</b><span>{{ run.duration_seconds }} 秒 · 工具 {{ run.tool_calls }} 次（失败 {{ run.failed_tool_calls }}）· 测试 {{ run.tests.passed }}/{{ run.tests.total }} 通过 · 文件 {{ run.changed_files }} 个</span></div></div>
      </article>
    </div>
  </section>
</template>
