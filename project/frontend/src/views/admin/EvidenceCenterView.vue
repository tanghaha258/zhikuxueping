<script setup lang="ts">
/**
 * EvidenceCenterView - 运营证据中心（Task 8 / 验收 3.8.3）。
 *
 * 三大能力：
 * 1. 指标台账：列出运营指标（公式/周期/样本量/来源/责任人），默认仅真实数据。
 * 2. 来源追溯：查看每个指标的证据台账（evidence ledger）。
 * 3. 导出预览 / 脱敏 / 二次确认：
 *    - previewExportApi 生成预览（含脱敏示例 anonymizationExamples）
 *    - confirmExportByIdApi 路径参数二次确认（审计备注留痕）
 *
 * dataOrigin=real 不可切换。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  confirmExportByIdApi,
  listEvidenceLedgerApi,
  listOperationalMetricsApi,
  previewExportApi,
} from '@/features/operational-evidence/api'
import type {
  EvidenceLedger,
  ExportPreviewResponse,
  OperationalMetric,
} from '@/features/operational-evidence/types'
import {
  DATA_ORIGIN_LABELS,
  PERIOD_LABELS,
} from '@/features/operational-evidence/types'

// ── 指标台账 ─────────────────────────────────────────────────
const loading = ref(false)
const errorMsg = ref('')
const metrics = ref<OperationalMetric[]>([])
const selectedMetrics = ref<OperationalMetric[]>([])
const dataOrigin = ref<'real'>('real')

async function loadMetrics() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await listOperationalMetricsApi({ dataOrigin: 'real' })
    metrics.value = res.data.data.items || []
  } catch (err: unknown) {
    errorMsg.value = err instanceof Error ? err.message : '加载指标台账失败'
  } finally {
    loading.value = false
  }
}

function handleSelectionChange(rows: OperationalMetric[]) {
  selectedMetrics.value = rows
}

function periodLabel(p: string): string {
  return PERIOD_LABELS[p] || p
}

function originLabel(o: string): string {
  return DATA_ORIGIN_LABELS[o] || o
}

// ── 来源追溯（证据台账抽屉） ─────────────────────────────────
const drawerVisible = ref(false)
const drawerMetric = ref<OperationalMetric | null>(null)
const drawerEvidence = ref<EvidenceLedger[]>([])
const drawerLoading = ref(false)

async function openEvidenceDrawer(row: OperationalMetric) {
  drawerMetric.value = row
  drawerVisible.value = true
  drawerEvidence.value = []
  drawerLoading.value = true
  try {
    // 优先按指标 id 拉取证据台账（来源追溯）
    const res = await listEvidenceLedgerApi({ metricId: row.id })
    drawerEvidence.value = res.data.data.items || []
  } catch {
    // 错误由拦截器提示
  } finally {
    drawerLoading.value = false
  }
}

// ── 导出预览 / 脱敏 / 二次确认 ───────────────────────────────
const exportAnonymized = ref(true)
const previewLoading = ref(false)
const previewVisible = ref(false)
const preview = ref<ExportPreviewResponse | null>(null)
const confirmLoading = ref(false)
const auditNote = ref('')

const selectedIds = computed(() => selectedMetrics.value.map((m) => m.id))

async function handlePreview() {
  if (selectedMetrics.value.length === 0) {
    ElMessage.warning('请至少选择一个指标')
    return
  }
  previewLoading.value = true
  try {
    const res = await previewExportApi({
      metricIds: selectedIds.value,
      anonymized: exportAnonymized.value,
    })
    preview.value = res.data.data
    auditNote.value = ''
    previewVisible.value = true
  } catch {
    // 错误由拦截器提示
  } finally {
    previewLoading.value = false
  }
}

async function handleConfirmExport() {
  if (!preview.value) return
  if (!auditNote.value.trim()) {
    ElMessage.warning('请填写审计备注（二次确认留痕）')
    return
  }
  try {
    await ElMessageBox.confirm(
      '确认导出？导出操作将被审计记录，脱敏后的数据将生成下载凭据。',
      '二次确认导出',
      { type: 'warning' },
    )
  } catch {
    return
  }
  confirmLoading.value = true
  try {
    await confirmExportByIdApi(preview.value.export.id, {
      auditNote: auditNote.value.trim(),
    })
    ElMessage.success('已确认导出，审计记录已留存')
    previewVisible.value = false
    preview.value = null
  } catch {
    // 错误由拦截器提示
  } finally {
    confirmLoading.value = false
  }
}

// ── 生命周期 ─────────────────────────────────────────────────
onMounted(loadMetrics)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="page-head">
      <h2 class="page-title">运营证据中心</h2>
      <div class="head-meta">
        <el-tag size="small" type="success">
          数据口径：仅真实数据（{{ dataOrigin }}，不可切换）
        </el-tag>
        <el-button size="small" @click="loadMetrics">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="errorMsg"
      :title="errorMsg"
      type="error"
      :closable="true"
      show-icon
      style="margin-bottom: 16px"
    />

    <!-- 指标台账 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">指标台账（{{ metrics.length }}）</span>
          <div class="export-panel">
            <span class="selected-hint">已选 {{ selectedMetrics.length }} 项</span>
            <el-switch
              v-model="exportAnonymized"
              active-text="脱敏导出"
              inline-prompt
            />
            <el-button
              type="primary"
              size="small"
              :disabled="selectedMetrics.length === 0"
              :loading="previewLoading"
              @click="handlePreview"
            >
              导出预览
            </el-button>
          </div>
        </div>
      </template>
      <el-table
        :data="metrics"
        stripe
        size="small"
        empty-text="暂无运营指标"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column prop="name" label="指标名称" min-width="150" />
        <el-table-column prop="code" label="代码" min-width="140" />
        <el-table-column prop="formula" label="公式" min-width="220" show-overflow-tooltip />
        <el-table-column label="周期" width="80">
          <template #default="{ row }">{{ periodLabel(row.period) }}</template>
        </el-table-column>
        <el-table-column prop="sampleSize" label="样本量" width="90" align="right" />
        <el-table-column prop="sourceTable" label="来源表" min-width="140" show-overflow-tooltip />
        <el-table-column prop="sourceOwner" label="数据来源责任方" min-width="130" show-overflow-tooltip />
        <el-table-column prop="responsiblePerson" label="责任人" min-width="100" show-overflow-tooltip />
        <el-table-column label="当前值" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.value !== null && row.value !== undefined">{{ row.value }}</span>
            <span v-else class="text-muted">未采集</span>
          </template>
        </el-table-column>
        <el-table-column label="数据口径" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="(row.dataOrigin === 'real' ? 'success' : 'warning') as any">
              {{ originLabel(row.dataOrigin) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" type="primary" @click="openEvidenceDrawer(row)">
              来源追溯
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 来源追溯抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="`来源追溯 · ${drawerMetric?.name || ''}`"
      size="520px"
      direction="rtl"
    >
      <div v-loading="drawerLoading">
        <el-descriptions v-if="drawerMetric" :column="1" border size="small" style="margin-bottom: 16px">
          <el-descriptions-item label="指标代码">{{ drawerMetric.code }}</el-descriptions-item>
          <el-descriptions-item label="公式">{{ drawerMetric.formula }}</el-descriptions-item>
          <el-descriptions-item label="来源表">{{ drawerMetric.sourceTable || '—' }}</el-descriptions-item>
          <el-descriptions-item label="数据来源责任方">{{ drawerMetric.sourceOwner || '—' }}</el-descriptions-item>
          <el-descriptions-item label="责任人">{{ drawerMetric.responsiblePerson || '—' }}</el-descriptions-item>
          <el-descriptions-item label="样本量">{{ drawerMetric.sampleSize ?? '—' }}</el-descriptions-item>
        </el-descriptions>

        <div class="drawer-section-title">证据台账（{{ drawerEvidence.length }}）</div>
        <el-empty v-if="drawerEvidence.length === 0" description="暂无证据记录" :image-size="60" />
        <el-table v-else :data="drawerEvidence" stripe size="small">
          <el-table-column prop="evidenceRef" label="证据引用" min-width="160" show-overflow-tooltip />
          <el-table-column prop="evidenceSummary" label="摘要" min-width="200" show-overflow-tooltip />
          <el-table-column label="采集时间" width="160">
            <template #default="{ row }">
              {{ row.collectedAt ? row.collectedAt.slice(0, 19).replace('T', ' ') : '—' }}
            </template>
          </el-table-column>
          <el-table-column prop="verifiedBy" label="核验人" width="100" />
        </el-table>
      </div>
    </el-drawer>

    <!-- 导出预览对话框（脱敏 + 二次确认） -->
    <el-dialog
      v-model="previewVisible"
      title="导出预览（脱敏）"
      width="640px"
      :close-on-click-modal="false"
    >
      <div v-if="preview">
        <el-descriptions :column="2" border size="small" style="margin-bottom: 16px">
          <el-descriptions-item label="导出 ID">
            #{{ preview.export.id.slice(0, 8) }}
          </el-descriptions-item>
          <el-descriptions-item label="脱敏">
            <el-tag size="small" :type="(preview.export.anonymized ? 'success' : 'warning') as any">
              {{ preview.export.anonymized ? '已脱敏' : '未脱敏' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="指标数">{{ preview.metrics.length }}</el-descriptions-item>
          <el-descriptions-item label="证据数">{{ preview.evidence.length }}</el-descriptions-item>
        </el-descriptions>

        <div class="preview-section-title">脱敏示例</div>
        <ul v-if="preview.anonymizationExamples.length > 0" class="anon-list">
          <li v-for="(ex, i) in preview.anonymizationExamples" :key="i">{{ ex }}</li>
        </ul>
        <el-empty v-else description="无脱敏示例" :image-size="50" />

        <div class="preview-section-title" style="margin-top: 16px">导出指标</div>
        <el-table :data="preview.metrics" stripe size="small" max-height="180">
          <el-table-column prop="name" label="指标" min-width="140" />
          <el-table-column prop="code" label="代码" min-width="120" />
          <el-table-column label="值" width="100" align="right">
            <template #default="{ row }">
              {{ row.value !== null && row.value !== undefined ? row.value : '—' }}
            </template>
          </el-table-column>
        </el-table>

        <el-form style="margin-top: 16px" label-width="100px">
          <el-form-item required>
            <template #label>审计备注</template>
            <el-input
              v-model="auditNote"
              type="textarea"
              :rows="2"
              placeholder="二次确认需填写审计备注（留痕）"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="previewVisible = false">取消</el-button>
        <el-button type="primary" :loading="confirmLoading" @click="handleConfirmExport">
          二次确认导出
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.page-title {
  margin: 0;
}

.head-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.export-panel {
  display: flex;
  align-items: center;
  gap: 12px;
}

.selected-hint {
  font-size: 13px;
  color: #909399;
}

.text-muted {
  color: #c0c4cc;
  font-style: italic;
}

.drawer-section-title,
.preview-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.anon-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: #606266;
  line-height: 1.8;
  background: #f7f9fc;
  border-radius: 4px;
  padding: 10px 10px 10px 28px;
}
</style>
