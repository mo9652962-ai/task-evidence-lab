// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TaskListPanel from './TaskListPanel.vue'
import type { Task } from '../types'

describe('TaskListPanel', () => {
  it('emits selection and search changes from the task list controls', async () => {
    const task = { id: 1, title: '搜索任务', description: '目标', status: 'draft', priority: 'medium', completion_basis: '', created_at: '', updated_at: '', criteria: [], evidence: [], runs: [], reviews: [], evaluation: null } as Task
    const wrapper = mount(TaskListPanel, { props: { visibleTasks: [task], selectedId: undefined, loading: false, filter: 'all', includeArchived: false, searchQuery: '' } })

    await wrapper.get('input[aria-label="搜索任务"]').setValue('搜索')
    await wrapper.get('.task-row').trigger('click')

    expect(wrapper.emitted('update:searchQuery')?.[0]).toEqual(['搜索'])
    expect(wrapper.emitted('select')?.[0]).toEqual([task])
  })
})
