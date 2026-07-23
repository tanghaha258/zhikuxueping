// 通用 UI 基座（Task 1）
// 来源：docs/superpowers/plans/2026-07-24-zhi-kua-xue-ping-full-rebuild.md §2
// 所有教师/管理/学生页面应使用本基座组件，不允许各页面自行创造样式与反馈模式。
import PageHeader from './PageHeader.vue'
import ContextBar from './ContextBar.vue'
import AsyncState from './AsyncState.vue'
import InlineAlert from './InlineAlert.vue'
import StatusBadge from './StatusBadge.vue'
import ProjectPhaseStepper from './ProjectPhaseStepper.vue'
import MetricStrip from './MetricStrip.vue'
import EvidenceLink from './EvidenceLink.vue'
import ContextPicker from './ContextPicker.vue'
import StickyActionBar from './StickyActionBar.vue'
import ConfirmActionDialog from './ConfirmActionDialog.vue'

export type AsyncStateName = 'loading' | 'ready' | 'empty' | 'error' | 'forbidden'
export type ProjectPhase =
  | 'diagnosis' | 'design' | 'preparation' | 'implementation'
  | 'evaluation' | 'improvement' | 'closure'

export {
  PageHeader,
  ContextBar,
  AsyncState,
  InlineAlert,
  StatusBadge,
  ProjectPhaseStepper,
  MetricStrip,
  EvidenceLink,
  ContextPicker,
  StickyActionBar,
  ConfirmActionDialog,
}
