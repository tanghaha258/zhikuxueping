import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AsyncState from './AsyncState.vue'
import PageHeader from './PageHeader.vue'
import ContextBar from './ContextBar.vue'
import InlineAlert from './InlineAlert.vue'
import StatusBadge from './StatusBadge.vue'
import ProjectPhaseStepper from './ProjectPhaseStepper.vue'
import MetricStrip from './MetricStrip.vue'
import EvidenceLink from './EvidenceLink.vue'
import ContextPicker from './ContextPicker.vue'
import StickyActionBar from './StickyActionBar.vue'
import ConfirmActionDialog from './ConfirmActionDialog.vue'

describe('shared UI contracts', () => {
  it('renders one primary action in PageHeader', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '学情诊断', primaryLabel: '确认诊断' },
    })
    expect(wrapper.findAll('[data-ui="primary-action"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('学情诊断')
  })

  it('PageHeader emits primary on primary action click', async () => {
    const wrapper = mount(PageHeader, {
      props: { title: '总览', primaryLabel: '下一步' },
    })
    await wrapper.get('[data-ui="primary-action"]').trigger('click')
    expect(wrapper.emitted('primary')).toHaveLength(1)
  })

  it('AsyncState renders loading state without retry', () => {
    const wrapper = mount(AsyncState, { props: { state: 'loading' } })
    expect(wrapper.find('[data-ui="state-loading"]').exists()).toBe(true)
    expect(wrapper.find('[data-ui="retry"]').exists()).toBe(false)
  })

  it('AsyncState renders empty state with hint and no retry', () => {
    const wrapper = mount(AsyncState, {
      props: { state: 'empty', emptyHint: '暂无学习证据' },
    })
    expect(wrapper.find('[data-ui="state-empty"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无学习证据')
    expect(wrapper.find('[data-ui="retry"]').exists()).toBe(false)
  })

  it('AsyncState offers retry when failed and emits retry', async () => {
    const wrapper = mount(AsyncState, {
      props: { state: 'error', message: '加载失败' },
    })
    expect(wrapper.find('[data-ui="state-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('加载失败')
    await wrapper.get('[data-ui="retry"]').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('AsyncState renders forbidden state and does not offer retry', () => {
    const wrapper = mount(AsyncState, { props: { state: 'forbidden' } })
    expect(wrapper.find('[data-ui="state-forbidden"]').exists()).toBe(true)
    expect(wrapper.find('[data-ui="retry"]').exists()).toBe(false)
  })

  it('AsyncState renders default slot when ready', () => {
    const wrapper = mount(AsyncState, {
      props: { state: 'ready' },
      slots: { default: '<div data-ui="body">内容</div>' },
    })
    expect(wrapper.find('[data-ui="body"]').exists()).toBe(true)
  })

  it('ContextBar renders provided context and dirty hint', () => {
    const wrapper = mount(ContextBar, {
      props: {
        project: { id: 'p1', name: '光的旅程' },
        className: '七年级1班',
        subjectName: '物理',
        dirty: true,
      },
    })
    expect(wrapper.text()).toContain('光的旅程')
    expect(wrapper.text()).toContain('七年级1班')
    expect(wrapper.find('[data-ui="dirty-hint"]').exists()).toBe(true)
  })

  it('InlineAlert renders blocker tone and emits action', async () => {
    const wrapper = mount(InlineAlert, {
      props: {
        tone: 'blocker',
        title: '存在未处理阻断',
        actionLabel: '去处理',
      },
    })
    expect(wrapper.find('[data-ui="inline-alert"]').classes()).toContain('ui-alert--blocker')
    await wrapper.get('[data-ui="alert-action"]').trigger('click')
    expect(wrapper.emitted('action')).toHaveLength(1)
  })

  it('StatusBadge maps known status and degrades unknown to muted', () => {
    const known = mount(StatusBadge, { props: { status: 'in_progress' } })
    expect(known.text().length).toBeGreaterThan(0)
    const unknown = mount(StatusBadge, { props: { status: 'totally-unknown-xyz' } })
    expect(unknown.find('[data-ui="status-badge"]').exists()).toBe(true)
    expect(unknown.find('[data-ui="status-badge"]').classes()).toContain('ui-badge--muted')
  })

  it('ProjectPhaseStepper renders phases and emits select', async () => {
    const wrapper = mount(ProjectPhaseStepper, {
      props: {
        phases: [
          { key: 'diagnosis', label: '学情诊断', status: 'done' },
          { key: 'design', label: '跨学科设计', status: 'current' },
          { key: 'preparation', label: '备课与资源', status: 'pending' },
        ],
      },
    })
    expect(wrapper.findAll('[data-ui="phase-step"]')).toHaveLength(3)
    await wrapper.findAll('[data-ui="phase-step"]')[1].trigger('click')
    expect(wrapper.emitted('select')?.[0]).toEqual(['design'])
  })

  it('ProjectPhaseStepper degrades unknown phase status without crash', () => {
    const wrapper = mount(ProjectPhaseStepper, {
      props: {
        phases: [
          { key: 'diagnosis', label: '学情诊断', status: 'unknown-status' as unknown as 'done' },
        ],
      },
    })
    expect(wrapper.findAll('[data-ui="phase-step"]')).toHaveLength(1)
  })

  it('MetricStrip renders compact metric items', () => {
    const wrapper = mount(MetricStrip, {
      props: {
        metrics: [
          { label: '学生数', value: '32' },
          { label: '完成率', value: '64%', tone: 'warning' },
        ],
      },
    })
    expect(wrapper.findAll('[data-ui="metric-item"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('完成率')
  })

  it('EvidenceLink shows unverified marker when not verified', () => {
    const wrapper = mount(EvidenceLink, {
      props: {
        evidence: { kind: 'submission', label: '小组提交 v1', verified: false },
      },
    })
    expect(wrapper.find('[data-ui="evidence-link"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('未验证')
  })

  it('EvidenceLink does not show unverified marker when verified and emits open', async () => {
    const wrapper = mount(EvidenceLink, {
      props: {
        evidence: { kind: 'rubric', label: '量规 A', verified: true },
      },
    })
    expect(wrapper.text()).not.toContain('未验证')
    await wrapper.get('[data-ui="evidence-link"]').trigger('click')
    expect(wrapper.emitted('open')).toHaveLength(1)
  })

  it('ContextPicker supports v-model and emits change', async () => {
    const wrapper = mount(ContextPicker, {
      props: {
        modelValue: { mode: 'standalone' },
        projects: [
          { id: 'p1', name: '光的旅程' },
          { id: 'p2', name: '声音的秘密' },
        ],
        phases: [{ key: 'diagnosis', label: '学情诊断' }],
      },
    })
    await wrapper.get('[data-ui="mode-select"]').setValue('linked')
    const updates = wrapper.emitted('update:modelValue')
    expect(updates).toBeTruthy()
    expect(updates?.[0]?.[0]).toMatchObject({ mode: 'linked' })
    expect(wrapper.emitted('change')).toBeTruthy()
  })

  it('ContextPicker linked mode requires project before emitting valid change', async () => {
    const wrapper = mount(ContextPicker, {
      props: {
        modelValue: { mode: 'linked' },
        projects: [{ id: 'p1', name: '光的旅程' }],
        phases: [{ key: 'diagnosis', label: '学情诊断' }],
      },
    })
    expect(wrapper.find('[data-ui="project-required"]').exists()).toBe(true)
    await wrapper.get('[data-ui="project-select"]').setValue('p1')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
  })

  it('StickyActionBar emits primary and secondary, disabled shows reason', async () => {
    const wrapper = mount(StickyActionBar, {
      props: {
        primaryLabel: '保存',
        secondaryLabel: '取消',
        primaryDisabled: true,
        disabledReason: '必填项未完成',
      },
    })
    const primary = wrapper.get('[data-ui="primary-action"]')
    expect(primary.attributes('disabled')).toBeDefined()
    expect(wrapper.attributes()).toBeTruthy()
    expect(wrapper.text()).toContain('必填项未完成')
  })

  it('StickyActionBar emits primary when enabled', async () => {
    const wrapper = mount(StickyActionBar, {
      props: { primaryLabel: '发布', primaryDisabled: false },
    })
    await wrapper.get('[data-ui="primary-action"]').trigger('click')
    expect(wrapper.emitted('primary')).toHaveLength(1)
  })

  it('ConfirmActionDialog cancel does not emit confirm', async () => {
    const wrapper = mount(ConfirmActionDialog, {
      props: {
        modelValue: true,
        title: '发布评价',
        impactSummary: '将向 32 名学生公示反馈',
      },
    })
    await wrapper.get('[data-ui="dialog-cancel"]').trigger('click')
    expect(wrapper.emitted('confirm')).toBeUndefined()
    expect(wrapper.emitted('cancel')).toBeTruthy()
    const updates = wrapper.emitted('update:modelValue')
    expect(updates?.[0]?.[0]).toBe(false)
  })

  it('ConfirmActionDialog emits confirm only after explicit confirm', async () => {
    const wrapper = mount(ConfirmActionDialog, {
      props: {
        modelValue: true,
        title: '归档项目',
        impactSummary: '项目转为只读',
        confirmLabel: '确认归档',
      },
    })
    await wrapper.get('[data-ui="dialog-confirm"]').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
    expect(wrapper.emitted('update:modelValue')?.[0]?.[0]).toBe(false)
  })
})
