<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from './api'
import { isBackupPayload } from './backup'
import type { BackupPayload } from './backup'
import type { AuditEntry, Candidate, Evaluation, Evidence, RunDetail, Task, TaskTemplate } from './types'
import { timelineKindLabel } from './timeline'
import type { CompareRow, TimelineEvent } from './timeline'
import type { ComparisonFilter } from './comparison'
import { parseTaskHash } from './navigation'
import ComparePanel from './components/ComparePanel.vue'
import TaskListPanel from './components/TaskListPanel.vue'
import TaskDetailPanel from './components/TaskDetailPanel.vue'
import TaskTemplatesPanel from './components/TaskTemplatesPanel.vue'
const tasks = ref<Task[]>([])
const selected = ref<Task | null>(null)
const candidates = ref<Candidate[]>([])
const templates = ref<TaskTemplate[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const filter = ref<'all' | Task['status']>('all')
const includeArchived = ref(false)
const searchQuery = ref('')
const activeView = ref<'board' | 'detail' | 'candidates' | 'compare' | 'templates'>('board')
const showNewTask = ref(false)
const newTask = ref({ title: '', description: '', priority: 'medium', completion_basis: '' })
const showEditTask = ref(false)
const editTask = ref({ title: '', description: '', priority: 'medium', completion_basis: '', due_at: '' })
const criterionTitle = ref('')
const evidenceForm = ref({ title: '', evidence_type: '文件', content: '', file_path: '', external_url: '', source_path: '' })
const reviewText = ref('')
const importText = ref('')
const importFormat = ref('auto')
const evaluation = ref<Evaluation | null>(null)
const timeline = ref<TimelineEvent[]>([])
const auditLog = ref<AuditEntry[]>([])
const compareLeft = ref<number | null>(null)
const compareRight = ref<number | null>(null)
const comparison = ref<CompareRow[]>([])
const comparisonFilter = ref<ComparisonFilter>('all')
const selectedRun = ref<RunDetail | null>(null)
const restoreInput = ref<HTMLInputElement | null>(null)
let searchTimer: number | undefined

const visibleTasks = computed(() => filter.value === 'all' ? tasks.value : tasks.value.filter((task) => task.status === filter.value))
const stats = computed(() => ({
  total: tasks.value.length,
  active: tasks.value.filter((task) => ['in_progress', 'blocked'].includes(task.status)).length,
  partial: tasks.value.filter((task) => task.status === 'partially_verified').length,
  unverified: tasks.value.filter((task) => !task.evaluation?.verified).length,
}))

const statusNames: Record<string, string> = { draft: '草稿', in_progress: '进行中', blocked: '已阻塞', partially_verified: '部分验证', completed: '已完成', archived: '已归档' }
const criterionNames: Record<string, string> = { pending: '待处理', in_progress: '进行中', verified: '已验证', failed: '失败', not_applicable: '不适用' }

function statusLabel(status: string) { return statusNames[status] ?? status }
function criterionLabel(status: string) { return criterionNames[status] ?? status }
function score(value: unknown) { return typeof value === 'number' ? value : 0 }
function eventValue(event: Event) { return (event.target as HTMLSelectElement).value }
function flash(message: string) { notice.value = message; window.setTimeout(() => { notice.value = '' }, 3000) }
function auditActionLabel(action: string) { return ({ 'task.created': '创建任务', 'task.updated': '更新任务', 'task.archived': '归档任务', 'task.deleted': '删除任务', 'criterion.created': '添加验收项', 'criterion.updated': '更新验收项', 'evidence.created': '添加证据', 'evidence.updated': '更新证据', 'evidence.link_checked': '检查外部链接', 'evidence.file_copied': '复制本地证据', 'run.imported': '导入运行记录', 'evaluation.created': '生成确定性评测', 'review.created': '保存人工复盘', 'backup.restored': '恢复本地备份' } as Record<string, string>)[action] ?? action }
function auditDetail(entry: AuditEntry) { const pairs = Object.entries(entry.detail); return pairs.length ? pairs.map(([key, value]) => `${key}=${String(value)}`).join(' · ') : '无额外字段' }

async function loadTasks() {
  loading.value = true
  error.value = ''
  try { tasks.value = await api.tasks(includeArchived.value, searchQuery.value); if (selected.value) await loadTask(selected.value.id) }
  catch (err) { error.value = err instanceof Error ? err.message : '无法加载任务' }
  finally { loading.value = false }
}
function scheduleTaskSearch() {
  if (searchTimer) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => { void loadTasks() }, 250)
}
async function loadTemplates() { templates.value = await api.templates().catch(() => []) }
async function loadTask(id: number) {
  selected.value = await api.task(id)
  evaluation.value = selected.value.evaluation
  const [events, audits] = await Promise.all([api.timeline(id), api.auditLog(id)])
  timeline.value = events
  auditLog.value = audits
}
async function selectTask(task: Task) { activeView.value = 'board'; await loadTask(task.id) }
async function openTaskDetail() {
  if (!selected.value) return
  activeView.value = 'detail'
  history.replaceState(null, '', `#task/${selected.value.id}`)
}
function closeTaskDetail() { activeView.value = 'board'; history.replaceState(null, '', window.location.pathname) }

async function createTask() {
  if (!newTask.value.title.trim()) return
  saving.value = true
  try { const created = await api.createTask(newTask.value); showNewTask.value = false; newTask.value = { title: '', description: '', priority: 'medium', completion_basis: '' }; await loadTasks(); await selectTask(created); flash('任务已创建') }
  catch (err) { error.value = err instanceof Error ? err.message : '创建失败' }
  finally { saving.value = false }
}
async function createTemplate(payload: Record<string, unknown>) {
  try {
    await api.createTemplate(payload)
    await loadTemplates(); flash('任务模板已保存')
  } catch (err) { error.value = err instanceof Error ? err.message : '模板保存失败' }
}
async function instantiateTemplate(template: TaskTemplate, title?: string) {
  try {
    const created = await api.instantiateTemplate(template.id, title ? { title } : {})
    await loadTasks(); await selectTask(created); flash('已根据模板创建任务，待补充证据已标记')
  } catch (err) { error.value = err instanceof Error ? err.message : '模板创建任务失败' }
}
async function deleteTemplate(template: TaskTemplate) {
  if (!window.confirm(`确定删除模板“${template.name}”吗？已创建的任务不会受影响。`)) return
  try { await api.deleteTemplate(template.id); await loadTemplates(); flash('任务模板已删除') }
  catch (err) { error.value = err instanceof Error ? err.message : '模板删除失败' }
}

function openEditTask() {
  if (!selected.value) return
  editTask.value = { title: selected.value.title, description: selected.value.description, priority: selected.value.priority, completion_basis: selected.value.completion_basis, due_at: selected.value.due_at?.slice(0, 16) ?? '' }
  showEditTask.value = true
}
async function saveEditTask() {
  if (!selected.value || !editTask.value.title.trim()) return
  saving.value = true
  try { await api.patchTask(selected.value.id, { ...editTask.value, due_at: editTask.value.due_at || null }); showEditTask.value = false; await loadTasks(); await loadTask(selected.value.id); flash('任务已更新') }
  catch (err) { error.value = err instanceof Error ? err.message : '任务更新失败' }
  finally { saving.value = false }
}
async function archiveTask() {
  if (!selected.value || !window.confirm(`确定归档任务“${selected.value.title}”吗？归档后仍可通过“含已归档”找回。`)) return
  try { await api.patchTask(selected.value.id, { status: 'archived' }); selected.value = null; await loadTasks(); flash('任务已归档') }
  catch (err) { error.value = err instanceof Error ? err.message : '归档失败' }
}
async function deleteTask() {
  if (!selected.value || !window.confirm(`确定永久删除任务“${selected.value.title}”吗？关联证据、运行记录和复盘也会删除，且不可恢复。`)) return
  try { await api.deleteTask(selected.value.id); selected.value = null; await loadTasks(); flash('任务已删除') }
  catch (err) { error.value = err instanceof Error ? err.message : '删除失败' }
}

async function changeStatus(status: string) {
  if (!selected.value) return
  try { await api.patchTask(selected.value.id, { status }); await loadTasks(); flash('任务状态已更新') }
  catch (err) { error.value = err instanceof Error ? err.message : '状态更新失败' }
}
async function addCriterion() {
  if (!selected.value || !criterionTitle.value.trim()) return
  try { await api.addCriterion(selected.value.id, { title: criterionTitle.value, required: true }); criterionTitle.value = ''; await loadTask(selected.value.id); await loadTasks(); flash('验收项已添加') }
  catch (err) { error.value = err instanceof Error ? err.message : '添加验收项失败' }
}
async function updateCriterion(id: number, status: string) {
  try { await api.patchCriterion(id, { status }); if (selected.value) await loadTask(selected.value.id); await loadTasks() }
  catch (err) { error.value = err instanceof Error ? err.message : '更新验收项失败' }
}
async function addEvidence() {
  if (!selected.value || !evidenceForm.value.title.trim()) return
  try { const created = await api.addEvidence(selected.value.id, evidenceForm.value); if (evidenceForm.value.source_path.trim()) await api.copyEvidence(created.id, evidenceForm.value.source_path.trim()); evidenceForm.value = { title: '', evidence_type: '文件', content: '', file_path: '', external_url: '', source_path: '' }; await loadTask(selected.value.id); await loadTasks(); flash('证据已添加') }
  catch (err) { error.value = err instanceof Error ? err.message : '添加证据失败' }
}
async function verifyEvidence(id: number, status: string) {
  try { await api.patchEvidence(id, { verification_status: status }); if (selected.value) await loadTask(selected.value.id); await loadTasks() }
  catch (err) { error.value = err instanceof Error ? err.message : '更新证据失败' }
}
async function checkEvidenceLink(item: Evidence) {
  if (!item.external_url) return
  try { await api.checkLink(item.id); if (selected.value) await loadTask(selected.value.id); flash('链接检查完成') }
  catch (err) { error.value = err instanceof Error ? err.message : '链接检查失败' }
}
async function runEvaluation() {
  if (!selected.value) return
  try { evaluation.value = await api.evaluate(selected.value.id); await loadTask(selected.value.id); await loadTasks(); flash('已完成确定性评测') }
  catch (err) { error.value = err instanceof Error ? err.message : '评测失败' }
}
async function importRun() {
  if (!selected.value || !importText.value.trim()) return
  try { await api.importRun(selected.value.id, importText.value, importFormat.value); importText.value = ''; await loadTask(selected.value.id); await loadTasks(); flash('运行记录已导入，未执行其中任何命令') }
  catch (err) { error.value = err instanceof Error ? err.message : '导入失败' }
}
async function addReview() {
  if (!selected.value || !reviewText.value.trim()) return
  try { await api.addReview(selected.value.id, reviewText.value); reviewText.value = ''; await loadTask(selected.value.id); flash('人工复盘已保存') }
  catch (err) { error.value = err instanceof Error ? err.message : '保存复盘失败' }
}
async function createCandidate() {
  if (!selected.value || !evaluation.value) return
  try { await api.createCandidate({ task_id: selected.value.id, title: '待确认经验：' + selected.value.title, content: evaluation.value.summary, source_evidence: `任务 #${selected.value.id} 的确定性评测`, target_type: 'manual' }); candidates.value = await api.candidates(); flash('已生成待人工确认的经验候选') }
  catch (err) { error.value = err instanceof Error ? err.message : '生成经验候选失败' }
}
async function downloadReport() {
  if (!selected.value) return
  const content = await api.report(selected.value.id)
  const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = `task-${selected.value.id}-review.md`; link.click(); URL.revokeObjectURL(url)
}
async function downloadBatchReport() {
  if (!comparison.value.length) return
  try {
    const content = await api.batchReport(comparison.value.map((row) => row.id))
    const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = `task-evidence-lab-batch-review-${new Date().toISOString().slice(0, 10)}.md`; link.click(); URL.revokeObjectURL(url)
    flash('批量复盘报告已导出')
  } catch (err) { error.value = err instanceof Error ? err.message : '批量报告导出失败' }
}
async function printReport() {
  if (!selected.value) return
  try {
    const reportWindow = window.open('', '_blank')
    if (!reportWindow) throw new Error('浏览器阻止了报告窗口，请允许弹出窗口后重试')
    reportWindow.document.write(await api.reportHtml(selected.value.id)); reportWindow.document.close(); reportWindow.focus(); window.setTimeout(() => reportWindow.print(), 250)
  } catch (err) { error.value = err instanceof Error ? err.message : '打印报告失败' }
}
async function downloadBackup() {
  try {
    const backup = await api.backupExport()
    const url = URL.createObjectURL(new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = `task-evidence-lab-backup-${new Date().toISOString().slice(0, 10)}.json`; link.click(); URL.revokeObjectURL(url)
    flash('JSON 备份已导出')
  } catch (err) { error.value = err instanceof Error ? err.message : '备份导出失败' }
}
function openRestorePicker() { restoreInput.value?.click() }
async function restoreBackup(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  try {
    const parsed: unknown = JSON.parse(await file.text())
    if (!isBackupPayload(parsed)) throw new Error('不是受支持的 Task Evidence Lab JSON 备份')
    if (!window.confirm('恢复会替换当前本地任务、证据、运行记录和复盘，确定继续吗？')) return
    saving.value = true
    await api.backupRestore(parsed as BackupPayload)
    selected.value = null; comparison.value = []; await loadTasks(); flash('本地数据已从备份恢复')
  } catch (err) { error.value = err instanceof Error ? err.message : '备份恢复失败' }
  finally { saving.value = false }
}
async function updateCandidate(candidate: Candidate, status: 'approved' | 'rejected') {
  try { await api.patchCandidate(candidate.id, { status }); candidates.value = await api.candidates(); flash('经验候选状态已更新') }
  catch (err) { error.value = err instanceof Error ? err.message : '更新经验候选失败' }
}
async function runComparison() {
  if (!compareLeft.value || !compareRight.value || compareLeft.value === compareRight.value) {
    error.value = '请选择两个不同的任务进行对比'
    return
  }
  try { comparison.value = await api.compare([compareLeft.value, compareRight.value]); error.value = ''; flash('任务对比已更新') }
  catch (err) { error.value = err instanceof Error ? err.message : '任务对比失败' }
}
async function openRun(runId: number) {
  try { selectedRun.value = await api.run(runId) }
  catch (err) { error.value = err instanceof Error ? err.message : '运行记录加载失败' }
}
function closeRun() { selectedRun.value = null }
function formatBytes(size?: number) { if (size === undefined || size === null) return '未知大小'; if (size < 1024) return `${size} B`; if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`; return `${(size / (1024 * 1024)).toFixed(1)} MB` }
const detailHandlers = { closeTaskDetail, openTaskDetail, openEditTask, archiveTask, deleteTask, runEvaluation, downloadReport, printReport, createCandidate, changeStatus, updateCriterion, addCriterion, checkEvidenceLink, verifyEvidence, addEvidence, importRun, openRun, addReview }

onMounted(async () => { const [, loadedCandidates, loadedTemplates] = await Promise.all([loadTasks(), api.candidates().catch(() => []), api.templates().catch(() => [])]); candidates.value = loadedCandidates; templates.value = loadedTemplates; const hashTaskId = parseTaskHash(window.location.hash); const hashTask = hashTaskId ? tasks.value.find((task) => task.id === hashTaskId) : null; if (hashTask) { await loadTask(hashTask.id); activeView.value = 'detail' } else if (tasks.value[0]) await selectTask(tasks.value[0]) })
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand"><span class="brand-mark">TE</span><div><small>TASK EVIDENCE LAB</small><h1>任务证据台</h1></div></div>
      <div class="top-actions"><span class="local-badge">● 本地模式 · AI 默认关闭</span><button @click="downloadBackup">导出 JSON 备份</button><button @click="openRestorePicker">恢复 JSON 备份</button><input ref="restoreInput" type="file" accept="application/json,.json" hidden @change="restoreBackup" /><button class="primary" @click="showNewTask = true">＋ 新建任务</button></div>
    </header>

    <main>
      <section class="hero"><div><small>EVIDENCE-FIRST WORKFLOW</small><h2>不记录“我做过什么”，而是记录“我完成了什么，以及凭什么证明”。</h2><p>让目标、验收项、证据、测试结果和人工判断在同一条可追溯链路中。</p></div><div class="hero-mark">✓</div></section>

      <section class="stats"><article><span>总任务</span><strong>{{ stats.total }}</strong><small>本地记录</small></article><article><span>进行中</span><strong>{{ stats.active }}</strong><small>含阻塞任务</small></article><article><span>部分完成</span><strong>{{ stats.partial }}</strong><small>仍有验收缺口</small></article><article><span>未验证</span><strong>{{ stats.unverified }}</strong><small>系统提示，不是事实结论</small></article></section>

      <div v-if="error" class="alert error">{{ error }} <button @click="error = ''">×</button></div>
      <div v-if="notice" class="alert success">{{ notice }}</div>

      <nav class="view-tabs"><button :class="{ active: activeView === 'board' }" @click="activeView = 'board'">任务工作台</button><button v-if="selected" :class="{ active: activeView === 'detail' }" @click="openTaskDetail">任务详情</button><button :class="{ active: activeView === 'templates' }" @click="activeView = 'templates'">任务模板 <b>{{ templates.length }}</b></button><button :class="{ active: activeView === 'compare' }" @click="activeView = 'compare'">任务对比</button><button :class="{ active: activeView === 'candidates' }" @click="activeView = 'candidates'">经验候选 <b>{{ candidates.filter(c => c.status === 'pending').length }}</b></button></nav>

      <section v-if="activeView === 'board' || activeView === 'detail'" class="board-layout" :class="{ 'detail-only': activeView === 'detail' }">
        <TaskListPanel v-if="activeView === 'board'" :visible-tasks="visibleTasks" :selected-id="selected?.id" :loading="loading" v-model:filter="filter" v-model:include-archived="includeArchived" v-model:search-query="searchQuery" @search="scheduleTaskSearch" @select="selectTask" @update:include-archived="loadTasks" />

        <TaskDetailPanel v-if="selected" :task="selected" :evaluation="evaluation" :timeline="timeline" :audit-log="auditLog" :active-view="activeView" :status-names="statusNames" :criterion-names="criterionNames" v-model:criterion-title="criterionTitle" :evidence-form="evidenceForm" v-model:import-text="importText" v-model:import-format="importFormat" v-model:review-text="reviewText" :handlers="detailHandlers" :timeline-kind-label="timelineKindLabel" :audit-action-label="auditActionLabel" :audit-detail="auditDetail" :format-bytes="formatBytes" />
        <section v-else class="panel empty detail-empty">请选择或创建一个任务</section>
      </section>

      <ComparePanel v-else-if="activeView === 'compare'" :tasks="tasks" v-model:left="compareLeft" v-model:right="compareRight" :comparison="comparison" v-model:filter="comparisonFilter" @compare="runComparison" @download="downloadBatchReport" />
      <TaskTemplatesPanel v-else-if="activeView === 'templates'" :templates="templates" @create="createTemplate" @instantiate="instantiateTemplate" @delete="deleteTemplate" />
      <section v-else class="panel candidates-panel"><div class="panel-title"><div><small>MEMORY CANDIDATES</small><h3>待人工确认的经验候选</h3></div><span>不会自动写入 MEMORY.md、AGENTS.md 或任何项目文件</span></div><div v-if="!candidates.length" class="empty">暂无经验候选</div><article v-for="candidate in candidates" :key="candidate.id" class="candidate"><div><span class="candidate-status">{{ candidate.status }}</span><h4>{{ candidate.title }}</h4><p>{{ candidate.content }}</p><small>来源：{{ candidate.source_evidence }}</small></div><div v-if="candidate.status === 'pending'" class="candidate-actions"><button @click="updateCandidate(candidate, 'approved')">确认</button><button @click="updateCandidate(candidate, 'rejected')">拒绝</button></div></article></section>
    </main>

    <footer>本地单机 MVP · 数据存储在 SQLite · 外部环境、真实浏览器和生产部署尚未验证</footer>

    <div v-if="showNewTask" class="modal-backdrop" @click.self="showNewTask = false"><form class="modal" @submit.prevent="createTask"><div class="panel-title"><div><small>NEW TASK</small><h3>创建任务</h3></div><button type="button" class="close" @click="showNewTask = false">×</button></div><label>任务标题<input v-model="newTask.title" required maxlength="160" placeholder="例如：实现诊断报告接口" /></label><label>任务目标与范围<textarea v-model="newTask.description" rows="4" maxlength="6000" placeholder="写清楚要完成什么"></textarea></label><label>完成依据<textarea v-model="newTask.completion_basis" rows="3" maxlength="4000" placeholder="完成后由人工填写：凭什么认为它完成了"></textarea></label><label>优先级<select v-model="newTask.priority"><option value="high">高</option><option value="medium">中</option><option value="low">低</option></select></label><div class="modal-actions"><button type="button" @click="showNewTask = false">取消</button><button class="primary" :disabled="saving">创建任务</button></div></form></div>
    <div v-if="showEditTask" class="modal-backdrop" @click.self="showEditTask = false"><form class="modal" @submit.prevent="saveEditTask"><div class="panel-title"><div><small>EDIT TASK</small><h3>编辑任务</h3></div><button type="button" class="close" @click="showEditTask = false">×</button></div><label>任务标题<input v-model="editTask.title" required maxlength="160" /></label><label>任务目标与范围<textarea v-model="editTask.description" rows="4" maxlength="6000"></textarea></label><label>完成依据<textarea v-model="editTask.completion_basis" rows="3" maxlength="4000"></textarea></label><label>截止时间<input v-model="editTask.due_at" type="datetime-local" /></label><label>优先级<select v-model="editTask.priority"><option value="high">高</option><option value="medium">中</option><option value="low">低</option></select></label><div class="modal-actions"><button type="button" @click="showEditTask = false">取消</button><button class="primary" :disabled="saving">保存修改</button></div></form></div>
    <div v-if="selectedRun" class="modal-backdrop" @click.self="closeRun"><section class="modal run-detail-modal"><div class="panel-title"><div><small>RUN #{{ selectedRun.id }}</small><h3>运行记录详情</h3></div><button type="button" class="close" @click="closeRun">×</button></div><p class="run-note">执行者：{{ selectedRun.executor }} · 状态：{{ selectedRun.status }} · 本记录只展示导入内容，未执行其中任何命令。</p><div class="run-detail-section"><h4>步骤时间线</h4><div v-if="!selectedRun.steps.length" class="empty compact">暂无步骤</div><div v-for="step in selectedRun.steps" :key="step.id" class="run-detail-item"><b>#{{ step.step_index }} {{ step.step_type }}</b><span>{{ step.status }} · {{ step.content }}</span></div></div><div class="run-detail-section"><h4>工具调用</h4><div v-if="!selectedRun.tool_calls.length" class="empty compact">暂无工具调用</div><div v-for="call in selectedRun.tool_calls" :key="call.id" class="run-detail-item"><b>{{ call.tool_name }}</b><span>{{ call.status }} · 风险 {{ call.risk_level }} · {{ call.input_json }}</span></div></div><div class="run-detail-section"><h4>文件变更</h4><div v-for="file in selectedRun.changed_files" :key="file.id" class="run-detail-item"><b>{{ file.path }}</b><span>{{ file.change_type }} · +{{ file.additions }} / -{{ file.deletions }} · 风险 {{ file.risk_level }}</span></div></div><div class="run-detail-section"><h4>测试结果</h4><div v-for="test in selectedRun.tests" :key="test.id" class="run-detail-item"><b>{{ test.name }}</b><span>{{ test.status }} · {{ test.duration_ms ?? 0 }} ms</span></div></div></section></div>
  </div>
</template>
