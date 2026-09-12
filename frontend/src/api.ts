import type { AuditEntry, Candidate, Evaluation, Evidence, RunDetail, Task, TaskTemplate } from './types'
import type { BackupPayload } from './backup'
import type { CompareRow, TimelineEvent } from './timeline'
import { request, requestText } from './http'

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  templates: () => request<TaskTemplate[]>('/api/templates'),
  createTemplate: (payload: Record<string, unknown>) => request<TaskTemplate>('/api/templates', { method: 'POST', body: JSON.stringify(payload) }),
  deleteTemplate: (id: number) => request<{ deleted: boolean }>(`/api/templates/${id}`, { method: 'DELETE' }),
  instantiateTemplate: (id: number, payload: Record<string, unknown> = {}) => request<Task>(`/api/templates/${id}/instantiate`, { method: 'POST', body: JSON.stringify(payload) }),
  tasks: (includeArchived = false, search = '') => request<Task[]>(`/api/tasks?include_archived=${includeArchived}&q=${encodeURIComponent(search)}`),
  task: (id: number) => request<Task>(`/api/tasks/${id}`),
  createTask: (payload: Record<string, unknown>) => request<Task>('/api/tasks', { method: 'POST', body: JSON.stringify(payload) }),
  patchTask: (id: number, payload: Record<string, unknown>) => request<Task>(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteTask: (id: number) => request<{ deleted: boolean }>(`/api/tasks/${id}`, { method: 'DELETE' }),
  addCriterion: (id: number, payload: Record<string, unknown>) => request(`/api/tasks/${id}/criteria`, { method: 'POST', body: JSON.stringify(payload) }),
  patchCriterion: (id: number, payload: Record<string, unknown>) => request(`/api/criteria/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  addEvidence: (id: number, payload: Record<string, unknown>) => request<Evidence>(`/api/tasks/${id}/evidence`, { method: 'POST', body: JSON.stringify(payload) }),
  patchEvidence: (id: number, payload: Record<string, unknown>) => request(`/api/evidence/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  checkLink: (id: number) => request<Evidence>(`/api/evidence/${id}/check-link`, { method: 'POST' }),
  copyEvidence: (id: number, source_path: string) => request<Evidence>(`/api/evidence/${id}/copy`, { method: 'POST', body: JSON.stringify({ source_path }) }),
  run: (id: number) => request<RunDetail>(`/api/runs/${id}`),
  evaluate: (id: number) => request<Evaluation>(`/api/tasks/${id}/evaluate`, { method: 'POST' }),
  timeline: (id: number) => request<TimelineEvent[]>(`/api/tasks/${id}/timeline`),
  auditLog: (id: number) => request<AuditEntry[]>(`/api/tasks/${id}/audit-log`),
  compare: (ids: number[]) => request<CompareRow[]>(`/api/tasks/compare`, { method: 'POST', body: JSON.stringify(ids) }),
  importRun: (task_id: number, content: string, format: string) => request(`/api/runs/import`, { method: 'POST', body: JSON.stringify({ task_id, content, format }) }),
  addReview: (id: number, content: string) => request(`/api/tasks/${id}/review`, { method: 'POST', body: JSON.stringify({ content, reviewer: 'manual' }) }),
  candidates: () => request<Candidate[]>('/api/memory-candidates'),
  createCandidate: (payload: Record<string, unknown>) => request<Candidate>('/api/memory-candidates', { method: 'POST', body: JSON.stringify(payload) }),
  patchCandidate: (id: number, payload: Record<string, unknown>) => request<Candidate>(`/api/memory-candidates/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  report: (id: number) => requestText(`/api/tasks/${id}/report/markdown`),
  batchReport: (ids: number[]) => requestText('/api/reports/batch', { method: 'POST', body: JSON.stringify({ task_ids: ids }) }),
  reportHtml: (id: number) => requestText(`/api/tasks/${id}/report/html`),
  backupExport: () => request<BackupPayload>('/api/backup/export'),
  backupRestore: (backup: BackupPayload) => request<{ restored: boolean; schema_version: number }>('/api/backup/restore', { method: 'POST', body: JSON.stringify({ backup, replace: true }) }),
}
