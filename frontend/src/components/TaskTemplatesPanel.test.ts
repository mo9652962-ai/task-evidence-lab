// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TaskTemplatesPanel from './TaskTemplatesPanel.vue'

describe('TaskTemplatesPanel', () => {
  it('emits a normalized template payload', async () => {
    const wrapper = mount(TaskTemplatesPanel, { props: { templates: [] } })
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('开发交付')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('create')?.[0]?.[0]).toMatchObject({ name: '开发交付', criteria: [], evidence_types: [] })
  })
})
