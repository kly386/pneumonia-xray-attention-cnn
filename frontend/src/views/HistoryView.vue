<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  CircleCheckFilled,
  Delete,
  Document,
  EditPen,
  Refresh,
  Search,
  View,
  WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import http from '@/api/http'
import { startPageTour, startPageTourOnce, onPageTourRequest } from '@/composables/usePageTour'
import { useTheme } from '@/composables/useTheme'
import AppDisclaimer from '@/components/AppDisclaimer.vue'

const router = useRouter()
const { isDark } = useTheme()

const loading = ref(false)
const deletingId = ref(null)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const predictionFilter = ref('ALL')
const detailVisible = ref(false)
const selectedRecord = ref(null)
const errorMessage = ref('')
const judgementVisible = ref(false)
const judgementTarget = ref(null)
const judgementMode = ref('')
const judgementSaving = ref(false)

const ORIGINAL_PLACEHOLDER = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480"><rect width="640" height="480" fill="#0f172a"/><rect x="24" y="24" width="592" height="432" rx="20" fill="#12242f" stroke="#22d3ee" stroke-opacity="0.42" stroke-dasharray="10 8"/><text x="320" y="220" text-anchor="middle" fill="#9db4c0" font-family="sans-serif" font-size="28">原始 X 光片未归档</text><text x="320" y="262" text-anchor="middle" fill="#64748b" font-family="sans-serif" font-size="20">该记录未保存原始影像</text></svg>',
)}`

const HEATMAP_PLACEHOLDER = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480"><rect width="640" height="480" fill="#0f172a"/><rect x="24" y="24" width="592" height="432" rx="20" fill="#12242f" stroke="#22d3ee" stroke-opacity="0.42" stroke-dasharray="10 8"/><text x="320" y="220" text-anchor="middle" fill="#9db4c0" font-family="sans-serif" font-size="28">Grad-CAM 未生成</text><text x="320" y="262" text-anchor="middle" fill="#64748b" font-family="sans-serif" font-size="20">该记录未保存热力图</text></svg>',
)}`

const hasRecords = computed(() => total.value > 0)
const filterLabel = computed(() => {
  if (predictionFilter.value === 'NORMAL') return '正常记录'
  if (predictionFilter.value === 'PNEUMONIA') return '肺炎记录'
  return '全部记录'
})

const detailOriginalUrl = computed(
  () => selectedRecord.value?.original_url || ORIGINAL_PLACEHOLDER,
)
const detailHeatmapUrl = computed(
  () => selectedRecord.value?.heatmap_url || HEATMAP_PLACEHOLDER,
)
const detailOriginalIsPlaceholder = computed(
  () => !selectedRecord.value?.original_url,
)
const detailHeatmapIsPlaceholder = computed(
  () => !selectedRecord.value?.heatmap_url,
)

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`
}

function genderText(value) {
  if (value === 'MALE') return '男'
  if (value === 'FEMALE') return '女'
  return '未填写'
}

function clinicalText(value, suffix = '') {
  if (value === null || value === undefined || value === '') return '未填写'
  return `${value}${suffix}`
}

function judgementText(record) {
  if (record?.use_ai_judgement === true) {
    return `采用 AI · ${record.prediction === 'PNEUMONIA' ? '肺炎' : '正常'}`
  }
  if (record?.use_ai_judgement === false) {
    return `医生复核 · ${record.doctor_label === 'PNEUMONIA' ? '肺炎' : '正常'}`
  }
  return '未评判'
}

function judgementClass(record) {
  if (record?.use_ai_judgement === false) {
    return record.doctor_label === 'PNEUMONIA' ? 'is-danger' : 'is-normal'
  }
  if (record?.use_ai_judgement === true) {
    return record.prediction === 'PNEUMONIA' ? 'is-danger' : 'is-normal'
  }
  return 'is-pending'
}

function openJudgement(record) {
  judgementTarget.value = record
  judgementMode.value = record?.use_ai_judgement
    ? 'AI'
    : record?.doctor_label || ''
  judgementVisible.value = true
}

async function saveJudgement() {
  if (!judgementTarget.value || !judgementMode.value) {
    ElMessage.warning('请选择初步评判方式')
    return
  }

  judgementSaving.value = true

  try {
    const useAi = judgementMode.value === 'AI'
    const { data } = await http.patch(
      `/history/${judgementTarget.value.id}/judgement`,
      {
        use_ai_judgement: useAi,
        doctor_label: useAi ? null : judgementMode.value,
      },
    )

    const index = items.value.findIndex(
      (item) => item.id === judgementTarget.value.id,
    )
    if (index >= 0) items.value[index] = { ...items.value[index], ...data }
    if (selectedRecord.value?.id === data.id) {
      selectedRecord.value = { ...selectedRecord.value, ...data }
    }

    judgementVisible.value = false
    ElMessage.success('医生初步评判已保存')
  } catch (error) {
    ElMessage.error(error.userMessage || error.message || '保存失败，请重试')
  } finally {
    judgementSaving.value = false
  }
}

function normalProbability(record) {
  return Math.max(0, 1 - Number(record?.prob_pneumonia || 0))
}

async function loadHistory() {
  loading.value = true
  errorMessage.value = ''

  try {
    const { data } = await http.get('/history', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        ...(predictionFilter.value !== 'ALL'
          ? { prediction: predictionFilter.value }
          : {}),
      },
    })

    items.value = data.items || []
    total.value = Number(data.total || 0)
  } catch (error) {
    errorMessage.value =
      error.userMessage || error.message || '历史记录加载失败，请稍后重试'
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function applyFilter() {
  page.value = 1
  loadHistory()
}

function onPageChange(nextPage) {
  page.value = nextPage
  loadHistory()
}

function onPageSizeChange(nextSize) {
  pageSize.value = nextSize
  page.value = 1
  loadHistory()
}

function refresh() {
  loadHistory()
}

function openDetail(record) {
  selectedRecord.value = record
  detailVisible.value = true
}

function probabilityClass(record) {
  return Number(record?.prob_pneumonia || 0) >= 0.5101
    ? 'is-high'
    : 'is-low'
}

async function removeRecord(record) {
  try {
    await ElMessageBox.confirm(
      `确定删除 ${record.filename || '该条记录'} 吗？删除后不可恢复。`,
      '删除历史记录',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        distinguishCancelAndClose: true,
      },
    )
  } catch {
    return
  }

  deletingId.value = record.id

  try {
    await http.delete(`/history/${record.id}`)
    ElMessage.success('记录已删除')

    if (items.value.length === 1 && page.value > 1) {
      page.value -= 1
    }

    await loadHistory()
  } catch (error) {
    ElMessage.error(error.userMessage || error.message || '删除失败，请稍后重试')
  } finally {
    deletingId.value = null
  }
}

function goWorkspace() {
  router.push('/workspace')
}

const HISTORY_TOUR_STEPS = [
  {
    element: '#tour-history-toolbar',
    popover: {
      title: '筛选与刷新',
      description: '按正常 / 肺炎筛选记录，或刷新获取最新筛查结果。',
    },
  },
  {
    element: '#tour-history-table',
    popover: {
      title: '筛查记录列表',
      description: '查看详情、复评或删除记录；详情中可查看原始影像与 Grad-CAM。',
    },
  },
  {
    element: '#tour-history-pagination',
    popover: {
      title: '分页浏览',
      description: '切换页码或每页条数，浏览更早的历史筛查记录。',
    },
  },
]

let removeTourListener = null

onMounted(() => {
  loadHistory()
  startPageTourOnce({
    storageKey: 'hasSeenTour_history',
    isDark: isDark.value,
    delay: 800,
    steps: HISTORY_TOUR_STEPS,
  })

  removeTourListener = onPageTourRequest(() => {
    startPageTour({
      storageKey: 'hasSeenTour_history',
      isDark: isDark.value,
      steps: HISTORY_TOUR_STEPS,
    })
  }, '/history')
})

onBeforeUnmount(() => {
  removeTourListener?.()
})
</script>

<template>
  <main class="history-page">
    <header class="history-heading">
      <div>
        <p class="page-eyebrow">CLINICAL HISTORY</p>
        <h1 class="page-title">历史筛查记录</h1>
        <p class="page-description">
          查看当前医生已完成并自动保存的 AI 辅助筛查记录，支持按判定类别筛选和删除。
        </p>
      </div>

      <div class="history-summary glass-panel">
        <span>当前记录总数</span>
        <strong class="mono">{{ total }}</strong>
        <small>{{ filterLabel }}</small>
      </div>
    </header>

    <section class="history-card glass-panel">
      <div id="tour-history-toolbar" class="history-toolbar">
        <div class="toolbar-title">
          <el-icon><Document /></el-icon>
          <span>筛查记录</span>
        </div>

        <div class="toolbar-actions">
          <el-select
            v-model="predictionFilter"
            class="filter-select"
            popper-class="history-filter-popper"
            aria-label="按 AI 判定类别筛选"
            @change="applyFilter"
          >
            <el-option label="全部结果" value="ALL">
              <span class="filter-option is-all">
                <i class="filter-option__dot"></i>全部结果
              </span>
            </el-option>
            <el-option label="正常（NORMAL）" value="NORMAL">
              <span class="filter-option is-normal">
                <i class="filter-option__dot"></i>正常（NORMAL）
              </span>
            </el-option>
            <el-option label="肺炎（PNEUMONIA）" value="PNEUMONIA">
              <span class="filter-option is-danger">
                <i class="filter-option__dot"></i>肺炎（PNEUMONIA）
              </span>
            </el-option>
          </el-select>

          <el-button :icon="Refresh" :loading="loading" @click="refresh">
            刷新
          </el-button>
        </div>
      </div>

      <div v-if="errorMessage && !loading" class="history-error">
        <span>{{ errorMessage }}</span>
        <el-button size="small" @click="loadHistory">重新加载</el-button>
      </div>

      <el-table
        v-if="hasRecords || loading"
        id="tour-history-table"
        v-loading="loading"
        :data="items"
        class="history-table"
        empty-text="暂无符合条件的记录"
      >
        <el-table-column label="影像文件" min-width="230">
          <template #default="{ row }">
            <div class="file-cell">
              <span class="file-cell__icon">
                <el-icon><Document /></el-icon>
              </span>
              <div>
                <strong :title="row.filename">{{ row.filename || '未命名影像' }}</strong>
                <small>记录 #{{ row.id }}</small>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="AI 判定" width="130" align="center" header-align="center">
          <template #default="{ row }">
            <span
              class="result-pill"
              :class="row.prediction === 'PNEUMONIA' ? 'is-danger' : 'is-normal'"
            >
              <el-icon>
                <WarningFilled v-if="row.prediction === 'PNEUMONIA'" />
                <CircleCheckFilled v-else />
              </el-icon>
              {{ row.prediction === 'PNEUMONIA' ? '肺炎' : '正常' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="医生初步评判" width="200" align="center" header-align="center">
          <template #default="{ row }">
            <span
              class="judgement-pill"
              :class="judgementClass(row)"
            >
              {{ judgementText(row) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="肺炎概率" width="130" align="center" header-align="center">
          <template #default="{ row }">
            <span
              class="mono probability-value"
              :class="probabilityClass(row)"
            >
              {{ formatPercent(row.prob_pneumonia) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="置信度" width="110" align="center" header-align="center">
          <template #default="{ row }">
            <span class="mono confidence-value">{{ formatPercent(row.confidence) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="判定阈值" width="110" align="center" header-align="center">
          <template #default>
            <span class="mono threshold-value">0.5101</span>
          </template>
        </el-table-column>

        <el-table-column label="筛查时间" min-width="185" align="center" header-align="center">
          <template #default="{ row }">
            <span class="time-value">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="210" align="center" header-align="center">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button link type="primary" :icon="View" @click="openDetail(row)">
                查看详情
              </el-button>
              <el-button link type="primary" :icon="EditPen" @click="openJudgement(row)">
                复评
              </el-button>
              <el-button
                link
                type="danger"
                :icon="Delete"
                :loading="deletingId === row.id"
                @click="removeRecord(row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-else-if="!errorMessage" class="history-empty">
        <span class="history-empty__icon">
          <el-icon><Search /></el-icon>
        </span>
        <strong>暂无筛查记录</strong>
        <p>前往工作台上传一张 X 光片，完成首次辅助筛查。</p>
        <el-button type="primary" @click="goWorkspace">前往工作台</el-button>
      </div>

      <div v-if="hasRecords" id="tour-history-pagination" class="history-pagination">
        <el-pagination
          background
          :current-page="page"
          :page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </section>

    <el-dialog
      v-model="detailVisible"
      title="筛查记录详情"
      width="min(920px, 94vw)"
      class="history-detail-dialog"
    >
      <div v-if="selectedRecord" class="detail-content">
        <div
          class="detail-banner"
          :class="selectedRecord.prediction === 'PNEUMONIA' ? 'is-danger' : 'is-normal'"
        >
          <el-icon>
            <WarningFilled v-if="selectedRecord.prediction === 'PNEUMONIA'" />
            <CircleCheckFilled v-else />
          </el-icon>
          <div>
            <span>AI 判定类别</span>
            <strong>
              {{ selectedRecord.prediction === 'PNEUMONIA' ? '肺炎 PNEUMONIA' : '正常 NORMAL' }}
            </strong>
          </div>
        </div>

        <div class="detail-images">
          <figure class="detail-image-card">
            <figcaption>
              <span>原始 X 光片</span>
              <small v-if="detailOriginalIsPlaceholder">该记录未保存原图</small>
              <small v-else>本人上传原图 · 点击放大</small>
            </figcaption>
            <el-image
              class="detail-image"
              :src="detailOriginalUrl"
              :preview-src-list="detailOriginalIsPlaceholder ? [] : [detailOriginalUrl]"
              preview-teleported
              fit="contain"
              alt="原始 X 光片"
            />
          </figure>

          <figure class="detail-image-card">
            <figcaption>
              <span>Grad-CAM 对比图</span>
              <small v-if="detailHeatmapIsPlaceholder">该记录未生成热力图</small>
              <small v-else>本次分析热力图 · 点击放大</small>
            </figcaption>
            <el-image
              class="detail-image"
              :src="detailHeatmapUrl"
              :preview-src-list="detailHeatmapIsPlaceholder ? [] : [detailHeatmapUrl]"
              preview-teleported
              fit="contain"
              alt="Grad-CAM 热力图"
            />
          </figure>
        </div>

        <div class="detail-block">
          <h3 class="detail-block__title">
            <span class="detail-block__bar detail-block__bar--ai"></span>
            AI 检测结果
          </h3>
          <div class="detail-grid">
            <div>
              <span>肺炎概率</span>
              <strong
                class="mono detail-prob"
                :class="probabilityClass(selectedRecord)"
              >
                {{ formatPercent(selectedRecord.prob_pneumonia) }}
              </strong>
            </div>
            <div>
              <span>正常概率</span>
              <strong class="mono">{{ formatPercent(normalProbability(selectedRecord)) }}</strong>
            </div>
            <div>
              <span>判定置信度</span>
              <strong class="mono">{{ formatPercent(selectedRecord.confidence) }}</strong>
            </div>
            <div>
              <span>判定阈值</span>
              <strong class="mono">0.5101</strong>
            </div>
            <div>
              <span>影像文件</span>
              <strong :title="selectedRecord.filename">{{ selectedRecord.filename }}</strong>
            </div>
          </div>
        </div>

        <div class="detail-block">
          <h3 class="detail-block__title">
            <span class="detail-block__bar detail-block__bar--manual"></span>
            手动输入 / 医生信息
          </h3>
          <div class="detail-grid">
            <div>
              <span>医生初步评判</span>
              <strong>{{ judgementText(selectedRecord) }}</strong>
            </div>
            <div>
              <span>年龄</span>
              <strong>{{ clinicalText(selectedRecord.age, ' 岁') }}</strong>
            </div>
            <div>
              <span>性别</span>
              <strong>{{ genderText(selectedRecord.gender) }}</strong>
            </div>
            <div>
              <span>体温</span>
              <strong>{{ clinicalText(selectedRecord.temperature, ' ℃') }}</strong>
            </div>
            <div>
              <span>咳嗽天数</span>
              <strong>{{ clinicalText(selectedRecord.cough_days, ' 天') }}</strong>
            </div>
          </div>
        </div>

        <div class="detail-actions">
          <span class="detail-time">
            筛查时间 <strong>{{ formatDate(selectedRecord.created_at) }}</strong>
          </span>
          <el-button
            :icon="EditPen"
            type="primary"
            plain
            @click="openJudgement(selectedRecord)"
          >
            复评 / 医生初步评判
          </el-button>
        </div>

        <AppDisclaimer compact />
      </div>
    </el-dialog>

    <el-dialog
      v-model="judgementVisible"
      title="医生初步评判"
      width="min(540px, 92vw)"
      append-to-body
    >
      <div v-if="judgementTarget" class="feedback-content">
        <p class="feedback-record">
          记录 #{{ judgementTarget.id }} · {{ judgementTarget.filename }}
        </p>
        <p class="judgement-ai">
          AI 判定参考：<strong>{{ judgementTarget.prediction === 'PNEUMONIA' ? '肺炎 PNEUMONIA' : '正常 NORMAL' }}</strong>
        </p>

        <div class="feedback-field">
          <span>初步评判方式</span>
          <el-radio-group v-model="judgementMode" class="judgement-options">
            <el-radio value="AI" class="judgement-option is-ai">
              采用 AI 判定（{{ judgementTarget.prediction === 'PNEUMONIA' ? '肺炎' : '正常' }}）
            </el-radio>
            <el-radio value="NORMAL" class="judgement-option is-normal">
              医生复核：正常 NORMAL
            </el-radio>
            <el-radio value="PNEUMONIA" class="judgement-option is-danger">
              医生复核：肺炎 PNEUMONIA
            </el-radio>
          </el-radio-group>
        </div>
      </div>

      <template #footer>
        <el-button @click="judgementVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="judgementSaving"
          :disabled="!judgementMode"
          @click="saveJudgement"
        >
          保存评判
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>
<style scoped>
.history-page {
  width: 100%;
}

.history-heading {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 22px;
}

.history-summary {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  min-width: 190px;
  padding: 22px 26px;
}

.history-summary span,
.history-summary small {
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.4;
}

.history-summary strong {
  margin: 7px 0 4px;
  color: var(--brand);
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
}

.history-card {
  padding: clamp(18px, 2.5vw, 27px);
}

.history-toolbar {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.toolbar-title {
  display: flex;
  gap: 9px;
  align-items: center;
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 650;
}

.toolbar-title .el-icon {
  color: var(--color-primary-strong);
}

.toolbar-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.filter-select {
  width: 165px;
}

.history-error {
  display: flex;
  gap: 14px;
  align-items: center;
  justify-content: space-between;
  padding: 11px 14px;
  margin-bottom: 14px;
  color: var(--danger);
  font-size: 13px;
  background: color-mix(in srgb, var(--danger) 9%, transparent);
  border: 1px solid color-mix(in srgb, var(--danger) 24%, transparent);
  border-radius: 10px;
}

.history-table {
  width: 100%;
}

.history-table :deep(.el-table__header .el-table__cell) {
  font-size: 15px;
  font-weight: 650;
}

.history-table :deep(.el-table__body .el-table__cell) {
  padding: 14px 0;
  font-size: 14px;
  line-height: 1.5;
}

.file-cell {
  display: flex;
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.file-cell__icon {
  display: grid;
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 18%, transparent);
  border-radius: 9px;
  place-items: center;
}

.file-cell > div {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}

.file-cell strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-cell small {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 14px;
}
.result-pill {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 6px 10px;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid;
  border-radius: var(--radius-pill);
}

.result-pill.is-normal {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 10%, transparent);
  border-color: color-mix(in srgb, var(--success) 24%, transparent);
}

.result-pill.is-danger {
  color: var(--danger);
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-color: color-mix(in srgb, var(--danger) 26%, transparent);
}

.probability-value {
  color: var(--text-secondary);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.probability-value.is-high {
  color: var(--danger);
}

.probability-value.is-low {
  color: var(--success);
}

.confidence-value {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}

.threshold-value {
  color: var(--text-secondary);
  font-size: 14px;
}

.time-value {
  color: var(--text-secondary);
  font-size: 14px;
}

.judgement-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 5px 11px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
  border: 1px solid;
  border-radius: var(--radius-pill);
}

.judgement-pill.is-normal {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 10%, transparent);
  border-color: color-mix(in srgb, var(--success) 24%, transparent);
}

.judgement-pill.is-danger {
  color: var(--danger);
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-color: color-mix(in srgb, var(--danger) 26%, transparent);
}

.judgement-pill.is-pending {
  color: var(--text-tertiary);
  background: color-mix(in srgb, var(--text-primary) 5%, transparent);
  border-color: var(--border-color);
}

.table-actions {
  display: flex;
  flex-wrap: nowrap;
  gap: 2px;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.table-actions :deep(.el-button) {
  padding: 4px 6px;
  font-size: 13px;
}

.table-actions :deep(.el-button + .el-button) {
  margin-left: 2px;
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 330px;
  text-align: center;
}

.history-empty__icon {
  display: grid;
  width: 62px;
  height: 62px;
  margin-bottom: 17px;
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 18%, transparent);
  border-radius: 18px;
  font-size: 25px;
  place-items: center;
}

.history-empty strong {
  color: var(--color-text-soft);
  font-size: 14px;
  font-weight: 600;
}

.history-empty p {
  margin: 7px 0 19px;
  color: var(--color-text-faint);
  font-size: 10px;
}

.history-pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 18px;
  font-size: 14px;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.detail-banner {
  display: flex;
  gap: 13px;
  align-items: center;
  padding: 15px;
  border: 1px solid;
  border-radius: 13px;
}

.detail-banner.is-normal {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 8%, transparent);
  border-color: color-mix(in srgb, var(--success) 22%, transparent);
}

.detail-banner.is-danger {
  color: var(--danger);
  background: color-mix(in srgb, var(--danger) 8%, transparent);
  border-color: color-mix(in srgb, var(--danger) 22%, transparent);
}

.detail-banner > .el-icon {
  font-size: 30px;
}

.detail-banner > div {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.detail-banner span {
  color: var(--text-secondary);
  font-size: 14px;
  opacity: 0.9;
}

.detail-banner strong {
  margin-top: 5px;
  font-size: 18px;
}

.detail-images {
  display: flex;
  gap: 18px;
}

.detail-image-card {
  flex: 1;
  min-width: 0;
  margin: 0;
}

.detail-image-card figcaption {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 9px;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}

.detail-image-card figcaption small {
  color: var(--text-tertiary);
  font-size: 13px;
  font-weight: 400;
}

.detail-image {
  display: block;
  width: 100%;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  cursor: zoom-in;
  background: color-mix(in srgb, var(--bg-card) 80%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.detail-image :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
  object-fit: contain;
  transition: transform 240ms ease;
}

.detail-image:hover :deep(.el-image__inner) {
  transform: scale(1.02);
}

.detail-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-block__title {
  display: flex;
  gap: 9px;
  align-items: center;
  margin: 0;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 650;
}

.detail-block__bar {
  width: 4px;
  height: 16px;
  border-radius: 2px;
}

.detail-block__bar--ai {
  background: var(--brand);
  box-shadow: 0 0 8px color-mix(in srgb, var(--brand) 55%, transparent);
}

.detail-block__bar--manual {
  background: var(--color-primary-strong);
  box-shadow: 0 0 8px color-mix(in srgb, var(--color-primary-strong) 50%, transparent);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.detail-grid > div {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 15px;
  background: color-mix(in srgb, var(--text-primary) 4%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 11px;
}

.detail-grid span {
  color: var(--text-tertiary);
  font-size: 14px;
}

.detail-grid strong {
  overflow: hidden;
  margin-top: 7px;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-prob.is-high {
  color: var(--danger);
}

.detail-prob.is-low {
  color: var(--success);
}

.detail-actions {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
}

.detail-time {
  color: var(--text-tertiary);
  font-size: 13px;
}

.detail-time strong {
  margin-left: 4px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
}

.feedback-content {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.feedback-record {
  margin: 0;
  padding: 12px 14px;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.5;
  background: color-mix(in srgb, var(--text-primary) 4%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 10px;
}

.feedback-field {
  display: flex;
  flex-direction: column;
  gap: 9px;
  color: var(--text-secondary);
  font-size: 14px;
}

.feedback-field > span {
  color: var(--text-primary);
  font-weight: 600;
}

.judgement-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: stretch;
  width: 100%;
}

.judgement-options :deep(.judgement-option) {
  display: flex;
  align-items: center;
  width: 100%;
  height: auto;
  padding: 11px 14px;
  margin: 0;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.judgement-options :deep(.judgement-option.is-ai) {
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 7%, transparent);
  border-color: color-mix(in srgb, var(--brand) 24%, transparent);
}

.judgement-options :deep(.judgement-option.is-normal) {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 7%, transparent);
  border-color: color-mix(in srgb, var(--success) 24%, transparent);
}

.judgement-options :deep(.judgement-option.is-danger) {
  color: var(--danger);
  background: color-mix(in srgb, var(--danger) 7%, transparent);
  border-color: color-mix(in srgb, var(--danger) 24%, transparent);
}

.judgement-options :deep(.judgement-option .el-radio__label) {
  color: inherit;
  font-size: 14px;
  font-weight: 600;
}

.judgement-options :deep(.judgement-option.is-checked) {
  box-shadow: inset 0 0 0 1px currentColor;
}

.judgement-options :deep(.judgement-option.is-ai .el-radio__inner) {
  border-color: var(--brand);
}

.judgement-options :deep(.judgement-option.is-ai.is-checked .el-radio__inner) {
  background: var(--brand);
  border-color: var(--brand);
}

.judgement-options :deep(.judgement-option.is-normal .el-radio__inner) {
  border-color: var(--success);
}

.judgement-options :deep(.judgement-option.is-normal.is-checked .el-radio__inner) {
  background: var(--success);
  border-color: var(--success);
}

.judgement-options :deep(.judgement-option.is-danger .el-radio__inner) {
  border-color: var(--danger);
}

.judgement-options :deep(.judgement-option.is-danger.is-checked .el-radio__inner) {
  background: var(--danger);
  border-color: var(--danger);
}

.dropdown-icon {
  margin-left: 4px;
  vertical-align: middle;
}

@media (max-width: 900px) {
  .history-heading {
    flex-direction: column;
  }

  .history-summary {
    min-width: 0;
  }

  .detail-images {
    flex-direction: column;
  }

  .history-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-actions {
    justify-content: space-between;
  }

  .filter-select {
    flex: 1;
    width: auto;
  }

  .history-pagination {
    justify-content: flex-start;
    overflow-x: auto;
  }

  .detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 520px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}

:global(.history-filter-popper .el-select-dropdown__item) {
  height: auto;
  padding: 9px 16px;
  line-height: 1.5;
}

:global(.history-filter-popper .el-select-dropdown__item.is-selected) {
  background: color-mix(in srgb, var(--brand) 8%, transparent);
}

:global(.history-filter-popper .el-select-dropdown__item.is-selected::after) {
  display: none;
}

.filter-option {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
}

.filter-option__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.filter-option.is-all {
  color: var(--brand);
}

.filter-option.is-all .filter-option__dot {
  background: var(--brand);
  box-shadow: 0 0 8px color-mix(in srgb, var(--brand) 60%, transparent);
}

.filter-option.is-normal {
  color: var(--success);
}

.filter-option.is-normal .filter-option__dot {
  background: var(--success);
  box-shadow: 0 0 8px color-mix(in srgb, var(--success) 60%, transparent);
}

.filter-option.is-danger {
  color: var(--danger);
}

.filter-option.is-danger .filter-option__dot {
  background: var(--danger);
  box-shadow: 0 0 8px color-mix(in srgb, var(--danger) 60%, transparent);
}
</style>
