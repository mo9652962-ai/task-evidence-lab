// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ComparePanel from './ComparePanel.vue'

describe('ComparePanel', () => {
  it('emits a comparison request for two selected tasks', async () => {
    const wrapper = mount(ComparePanel, { props: { tasks: [{ id: 1, title: '任务 A' }, { id: 2, title: '任务 B' }], left: null, right: null, comparison: [], filter: 'all' } })
    const selects = wrapper.findAll('select')
    await selects[0].setValue('1')
    await selects[1].setValue('2')
    await wrapper.get('button.primary').trigger('click')

    expect(wrapper.emitted('update:left')?.[0]).toEqual([1])
    expect(wrapper.emitted('update:right')?.[0]).toEqual([2])
    expect(wrapper.emitted('compare')?.length).toBe(1)
  })
})
