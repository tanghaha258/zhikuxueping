import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StreamingProgress from '@/components/paper/StreamingProgress.vue'

describe('StreamingProgress', () => {
  it('renders the dialog', () => {
    const wrapper = mount(StreamingProgress)
    expect(document.body.textContent).toContain('AI 正在出卷')
    wrapper.unmount()
  })
})
