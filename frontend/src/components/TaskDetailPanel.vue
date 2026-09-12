<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import type { AuditEntry, Evaluation, Evidence, Task } from '../types'
import type { TimelineEvent } from '../timeline'
const EvidenceGraph = defineAsyncComponent(() => import('./EvidenceGraph.vue'))

type DetailHandlers = {
  closeTaskDetail: () => unknown
  openTaskDetail: () => unknown
  openEditTask: () => unknown
  archiveTask: () => unknown
  deleteTask: () => unknown
  runEvaluation: () => unknown
  downloadReport: () => unknown
  printReport: () => unknown
  createCandidate: () => unknown
  changeStatus: (status: string) => unknown
  updateCriterion: (id: number, status: string) => unknown
  addCriterion: () => unknown
  checkEvidenceLink: (item: Evidence) => unknown
  verifyEvidence: (id: number, status: string) => unknown
  addEvidence: () => unknown
  importRun: () => unknown
  openRun: (id: number) => unknown
  addReview: () => unknown
}

const props = defineProps<{
  task: Task
  evaluation: Evaluation | null
  timeline: TimelineEvent[]
  auditLog: AuditEntry[]
  activeView: 'board' | 'detail'
  statusNames: Record<string, string>
  criterionNames: Record<string, string>
  criterionTitle: string
  evidenceForm: Record<string, string>
  importText: string
  importFormat: string
  reviewText: string
  handlers: DetailHandlers
  timelineKindLabel: (kind: TimelineEvent['kind']) => string
  auditActionLabel: (action: string) => string
  auditDetail: (entry: AuditEntry) => string
  formatBytes: (size?: number) => string
}>()

const emit = defineEmits<{
  (event: 'update:criterionTitle', value: string): void
  (event: 'update:importText', value: string): void
  (event: 'update:importFormat', value: string): void
  (event: 'update:reviewText', value: string): void
}>()

const task = computed(() => props.task)
const evaluation = computed(() => props.evaluation)
const timeline = computed(() => props.timeline)
const auditLog = computed(() => props.auditLog)
const activeView = computed(() => props.activeView)
const statusNames = computed(() => props.statusNames)
const criterionNames = computed(() => props.criterionNames)
const handlers = computed(() => props.handlers)
const criterionInput = computed({ get: () => props.criterionTitle, set: (value: string) => emit('update:criterionTitle', value) })
const importInput = computed({ get: () => props.importText, set: (value: string) => emit('update:importText', value) })
const formatInput = computed({ get: () => props.importFormat, set: (value: string) => emit('update:importFormat', value) })
const reviewInput = computed({ get: () => props.reviewText, set: (value: string) => emit('update:reviewText', value) })
const evidenceForm = props.evidenceForm
const timelineKindLabel = props.timelineKindLabel
const auditActionLabel = props.auditActionLabel
const auditDetail = props.auditDetail
const formatBytes = props.formatBytes
function eventValue(event: Event) { return (event.target as HTMLSelectElement).value }
</script>

<template>
        <section class="panel detail-panel"><div class="detail-head"><div><small>TASK #{{ task.id }} · {{ task.priority.toUpperCase() }}</small><h3>{{ task.title }}</h3><p>{{ task.description || '尚未填写任务目标。' }}</p></div><select :value="task.status" @change="handlers.changeStatus(eventValue($event))"><option v-for="(label, key) in statusNames" :key="key" :value="key">{{ label }}</option></select></div>
          <div class="detail-actions"><button @click="activeView === 'detail' ? handlers.closeTaskDetail() : handlers.openTaskDetail()">{{ activeView === 'detail' ? '返回任务列表' : '打开独立详情' }}</button><button @click="handlers.openEditTask">编辑任务</button><button @click="handlers.archiveTask">归档</button><button class="danger-button" @click="handlers.deleteTask">删除</button><button @click="handlers.runEvaluation">运行确定性评测</button><button @click="handlers.downloadReport">导出 Markdown 报告</button><button @click="handlers.printReport">打印 / PDF</button><button :disabled="!evaluation" @click="handlers.createCandidate">生成经验候选</button></div>
          <div class="section"><div class="section-heading"><h4>完成标准</h4><span>{{ task.criteria.filter(c => c.status === 'verified' || c.status === 'not_applicable').length }}/{{ task.criteria.length }} 已满足</span></div><div v-for="criterion in task.criteria" :key="criterion.id" class="criterion"><input type="checkbox" :checked="criterion.status === 'verified'" @change="handlers.updateCriterion(criterion.id, criterion.status === 'verified' ? 'pending' : 'verified')" /><span>{{ criterion.title }} <small v-if="criterion.required">必需</small></span><select :value="criterion.status" @change="handlers.updateCriterion(criterion.id, eventValue($event))"><option v-for="(label, key) in criterionNames" :key="key" :value="key">{{ label }}</option></select></div><form class="inline-form" @submit.prevent="handlers.addCriterion"><input v-model="criterionInput" placeholder="添加一个验收项，例如：前端真实浏览器验证" /><button>添加</button></form></div>

          <div class="section"><div class="section-heading"><h4>成果证据</h4><span>用户声称 ≠ 已验证</span></div><div v-for="item in task.evidence" :key="item.id" class="evidence"><div><strong>{{ item.title }}</strong><span>{{ item.evidence_type }} · {{ item.source }}<template v-if="item.file_path"> · {{ item.file_path }}</template></span><p v-if="item.content">{{ item.content }}</p><small v-if="item.external_url" class="external-link">链接：{{ item.external_url }}</small><small v-if="item.local_path" class="local-file">本地副本：{{ item.local_path }} · {{ formatBytes(item.size_bytes) }} · SHA-256 {{ item.sha256 }}</small><div v-if="item.external_url" class="link-check"><button type="button" @click="handlers.checkEvidenceLink(item)">检查链接</button><small v-if="item.link_check_status">检查结果：{{ item.link_check_status }}<template v-if="item.link_status_code"> · HTTP {{ item.link_status_code }}</template><template v-if="item.link_checked_at"> · {{ new Date(item.link_checked_at).toLocaleString('zh-CN') }}</template><template v-if="item.link_error"> · {{ item.link_error }}</template></small></div></div><select :value="item.verification_status" @change="handlers.verifyEvidence(item.id, eventValue($event))"><option value="unreviewed">未审核</option><option value="confirmed">已确认</option><option value="rejected">已拒绝</option><option value="outdated">已过期</option></select></div><div v-if="!task.evidence.length" class="empty compact">暂未添加证据</div><form class="evidence-form" @submit.prevent="handlers.addEvidence"><input v-model="evidenceForm.title" placeholder="证据标题" required /><select v-model="evidenceForm.evidence_type"><option>文件</option><option>Git diff</option><option>测试输出</option><option>截图</option><option>网页链接</option><option>人工说明</option><option>AI 运行摘要</option></select><input v-model="evidenceForm.file_path" placeholder="文件路径说明（可选）" /><input v-model="evidenceForm.external_url" placeholder="外部链接（可选）" /><input v-model="evidenceForm.source_path" placeholder="复制本地文件路径（可选）" /><textarea v-model="evidenceForm.content" placeholder="证据内容或人工说明（只记录，不执行）" rows="2"></textarea><button class="primary">添加证据</button></form></div>

          <div class="section"><div class="section-heading"><h4>运行记录导入</h4><span>JSON / JSONL / Markdown · 只展示不执行</span></div><div class="import-controls"><select v-model="formatInput"><option value="auto">自动识别</option><option value="json">JSON</option><option value="jsonl">JSONL</option><option value="markdown">Markdown</option></select><button @click="handlers.importRun">导入记录</button></div><textarea v-model="importInput" rows="5" placeholder="粘贴通用运行记录。命令、脚本和路径会被当作文本保存，不会执行。"></textarea></div>

          <div class="section runs-section"><div class="section-heading"><h4>运行记录</h4><span>点击查看步骤、工具调用、文件变更和测试结果</span></div><div v-if="!task.runs.length" class="empty compact">暂无运行记录</div><button v-for="run in task.runs" :key="run.id" class="run-row" @click="handlers.openRun(run.id)"><span><b>运行 #{{ run.id }}</b> · {{ run.executor }}<small>{{ run.started_at || '未记录开始时间' }}</small></span><em>{{ run.status }}</em></button></div>

          <div class="section evaluation" v-if="evaluation"><div class="section-heading"><h4>评测结果</h4><strong class="score">{{ evaluation.overall_score }}</strong></div><div class="score-grid"><div><span>完成度</span><b>{{ evaluation.completion_score }}</b></div><div><span>证据充分性</span><b>{{ evaluation.evidence_score }}</b></div><div><span>验证状态</span><b>{{ evaluation.verification_score }}</b></div><div><span>执行情况</span><b>{{ evaluation.execution_score }}</b></div><div><span>风险评分</span><b>{{ evaluation.risk_score }}</b></div></div><p><b>系统推断：</b>{{ evaluation.summary }}</p><small>verified={{ evaluation.verified }} · human_confirmed={{ evaluation.human_confirmed }}。评分不是事实结论。</small></div>

          <div class="section"><div class="section-heading"><h4>人工复盘</h4><span>必须由人确认</span></div><div v-for="review in task.reviews" :key="review.id" class="review-note"><b>{{ review.reviewer }}</b><span>{{ review.content }}</span></div><form class="inline-form" @submit.prevent="handlers.addReview"><input v-model="reviewInput" placeholder="记录人工判断、未验证事项或后续行动" /><button>保存复盘</button></form></div>
          <div class="section timeline-section"><div class="section-heading"><h4>任务时间线</h4><span>系统推断与人工判断分开显示</span></div><div v-if="!timeline.length" class="empty compact">暂无时间线事件</div><div v-for="event in timeline" :key="`${event.kind}-${event.id}`" class="timeline-event"><div class="timeline-dot"></div><div><small>{{ timelineKindLabel(event.kind) }} · {{ new Date(event.occurred_at).toLocaleString('zh-CN') }}</small><strong>{{ event.title }}</strong><span>{{ event.detail }}</span></div></div></div>
          <div class="section audit-section"><div class="section-heading"><h4>变更审计</h4><span>最多展示最近 200 条关键变更</span></div><div v-if="!auditLog.length" class="empty compact">暂无审计记录</div><div v-for="entry in auditLog" :key="entry.id" class="audit-entry"><div class="audit-dot"></div><div><small>{{ new Date(entry.created_at).toLocaleString('zh-CN') }} · {{ entry.entity_type }}<template v-if="entry.entity_id"> #{{ entry.entity_id }}</template></small><strong>{{ auditActionLabel(entry.action) }}</strong><span>{{ auditDetail(entry) }}</span></div></div></div>
          <EvidenceGraph v-if="task" :task="task" />
        </section>
</template>
