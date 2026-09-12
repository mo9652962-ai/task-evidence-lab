// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusBadge from './StatusBadge.vue'

describe('StatusBadge', () => {
  it('renders a human label and semantic status class', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'partially_verified', label: '部分验证' } })
    expect(wrapper.text()).toBe('部分验证')
    expect(wrapper.classes()).toContain('status-partially_verified')
  })
})
