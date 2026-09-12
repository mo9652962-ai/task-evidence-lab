<script setup lang="ts">
import { ref } from 'vue'
import type { TaskTemplate } from '../types'

defineProps<{ templates: TaskTemplate[] }>()
const emit = defineEmits<{
  (event: 'create', payload: Record<string, unknown>): void
  (event: 'instantiate', template: TaskTemplate, title?: string): void
  (event: 'delete', template: TaskTemplate): void
}>()

const form = ref({ name: '', description: '', priority: 'medium', completion_basis: '', criteria: '', evidence_types: '' })
const titles = ref<Record<number, string>>({})
function create() {
  if (!form.value.name.trim()) return
  emit('create', {
    name: form.value.name.trim(), description: form.value.description, priority: form.value.priority,
    completion_basis: form.value.completion_basis,
    criteria: form.value.criteria.split('\n').map((item) => item.trim()).filter(Boolean),
    evidence_types: form.value.evidence_types.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean),
  })
  form.value = { name: '', description: '', priority: 'medium', completion_basis: '', criteria: '', evidence_types: '' }
}
</script>

<template>
  <section class="panel templates-panel">
    <div class="panel-title"><div><small>TASK TEMPLATES</small><h3>任务模板</h3></div><span>模板只生成本地任务和待补充证据，不会自动执行任何操作</span></div>
    <form class="template-form" @submit.prevent="create"><input v-model="form.name" placeholder="模板名称，例如：开发交付复盘" required maxlength="160" /><select v-model="form.priority"><option value="high">高优先级</option><option value="medium">中优先级</option><option value="low">低优先级</option></select><textarea v-model="form.description" placeholder="模板适用范围" rows="2"></textarea><textarea v-model="form.completion_basis" placeholder="完成依据模板" rows="2"></textarea><textarea v-model="form.criteria" placeholder="验收项（每行一项）" rows="3"></textarea><input v-model="form.evidence_types" placeholder="证据类型（逗号分隔），例如：测试输出, Git diff" /><button class="primary">保存模板</button></form>
    <div v-if="!templates.length" class="empty">暂无模板，先保存一个常用任务结构。</div>
    <article v-for="template in templates" :key="template.id" class="template-card"><div><span class="candidate-status">{{ template.priority }}</span><h4>{{ template.name }}</h4><p>{{ template.description || '未填写适用范围。' }}</p><small>验收项 {{ template.criteria.length }} 个 · 证据类型 {{ template.evidence_types.length }} 个</small><div class="template-chips"><span v-for="criterion in template.criteria" :key="criterion">验收：{{ criterion }}</span><span v-for="evidenceType in template.evidence_types" :key="evidenceType">证据：{{ evidenceType }}</span></div></div><div class="template-actions"><input v-model="titles[template.id]" placeholder="实例任务名称（可选）" /><button class="primary" @click="emit('instantiate', template, titles[template.id]?.trim() || undefined)">用此模板创建</button><button class="danger-button" @click="emit('delete', template)">删除模板</button></div></article>
  </section>
</template>
