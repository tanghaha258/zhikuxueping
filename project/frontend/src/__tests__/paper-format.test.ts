import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PaperFormatPreview from '@/components/paper/PaperFormatPreview.vue'

function mountPreview(formattedHtml: string) {
  return mount(PaperFormatPreview, {
    props: { formattedHtml },
    global: {
      stubs: {
        'el-button': true,
        'el-button-group': true,
      },
    },
  })
}

describe('PaperFormatPreview', () => {
  it('renders iframe with formatted html', () => {
    const wrapper = mountPreview('<html><body>test</body></html>')
    expect(wrapper.find('iframe').exists()).toBe(true)
  })

  it('shows empty state when no html', () => {
    const wrapper = mountPreview('')
    expect(wrapper.text()).toContain('试卷转换')
  })

  it('emits save event', () => {
    const wrapper = mountPreview('<p>hello</p>')
    wrapper.vm.$emit('save', '<p>edited</p>')
    expect(wrapper.emitted('save')).toBeTruthy()
    expect(wrapper.emitted('save')?.[0]).toEqual(['<p>edited</p>'])
  })
})
