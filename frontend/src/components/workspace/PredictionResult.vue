<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import {
  Aim,
  CircleCheckFilled,
  Close,
  Document,
  Download,
  RefreshRight,
  UploadFilled,
  WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'

import AppDisclaimer from '@/components/AppDisclaimer.vue'
import { useUserStore } from '@/stores/user'
import AnimatedPercent from '@/components/workspace/AnimatedPercent.vue'
import InteractiveImageViewer from '@/components/workspace/InteractiveImageViewer.vue'
import MedicalImageCanvas from '@/components/workspace/MedicalImageCanvas.vue'

const props = defineProps({
  result: {
    type: Object,
    required: true,
  },
  previewUrl: {
    type: String,
    default: '',
  },
  heatmapUrl: {
    type: String,
    default: '',
  },
  previewUrls: {
    type: Array,
    default: () => [],
  },
  clinical: {
    type: Object,
    default: () => ({}),
  },
})

defineEmits(['reset'])

const userStore = useUserStore()
const reportCardRef = ref()
const exporting = ref(false)
const pdfExporting = ref(false)
const compareMode = ref(false)
const historicalPreviewUrl = ref('')
const historicalInput = ref()
const historicalError = ref('')
const adjustedThreshold = ref(
  Number(props.result?.prediction?.threshold || 0.5101),
)
const gradcamOpacity = ref(65)
const imageInverted = ref(false)
const windowWidth = ref(255)
const windowLevel = ref(128)
const feedbackVisible = ref(false)
const feedbackLabel = ref('')
const feedbackReason = ref('')
const feedbackTarget = ref(null)
const doctorJudgements = reactive({})

function cardKey(item, index) {
  return `${item.filename || 'image'}-${index}`
}

function normalizeProbability(value, fallback = 0) {
  if (value === null || value === undefined || value === '') return fallback
  const parsedValue = Number(value)
  if (!Number.isFinite(parsedValue)) return fallback
  return Math.min(Math.max(parsedValue, 0), 1)
}

const fusedPneumoniaProbability = computed(() =>
  normalizeProbability(props.result?.prediction?.probs?.PNEUMONIA),
)
const finalProbability = computed(() =>
  normalizeProbability(props.result?.final_prob, fusedPneumoniaProbability.value),
)
// 进行阈值模拟时，徽章使用联合风险 final_prob；不得改写 final_prob 原值。
const pneumoniaProbability = finalProbability
const imageProbability = computed(() =>
  normalizeProbability(props.result?.image_prob, finalProbability.value),
)
const normalProbability = computed(() =>
  normalizeProbability(
    props.result?.prediction?.probs?.NORMAL,
    1 - finalProbability.value,
  ),
)
const isPneumonia = computed(
  () => finalProbability.value >= adjustedThreshold.value,
)
const labelText = computed(() => (isPneumonia.value ? '肺炎' : '正常'))
const labelEnglish = computed(() => (isPneumonia.value ? 'PNEUMONIA' : 'NORMAL'))
const hasClinicalFusion = computed(() => {
  const value = props.result?.final_prob
  return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))
})
const clinicalRisk = computed(() => {
  if (typeof props.result?.clinical_risk === 'string' && props.result.clinical_risk.trim()) {
    return props.result.clinical_risk
  }
  return hasClinicalFusion.value ? '无明显高危特征' : '未提供临床融合信息'
})
const clinicalRiskElevated = computed(() =>
  /高风险|有风险|风险提示/.test(clinicalRisk.value),
)
const clinicalInfoMissing = computed(() =>
  /未填写|未提供/.test(clinicalRisk.value),
)
const clinicalRiskDescription = computed(() => {
  if (clinicalInfoMissing.value) {
    return '本次未填写临床信息，仅使用影像模型结果，不代表无临床风险。'
  }
  return clinicalRiskElevated.value
    ? '临床特征触发风险加权，请结合影像、病史与查体综合判断。'
    : '当前临床输入未触发预设风险加权规则。'
})
const fusionDelta = computed(() => finalProbability.value - imageProbability.value)
const fusionDeltaText = computed(() => {
  if (Math.abs(fusionDelta.value) < 0.00005) {
    return '联合概率与原始影像概率一致'
  }
  const direction = fusionDelta.value > 0 ? '增加' : '降低'
  return `较影像概率${direction} ${Math.abs(fusionDelta.value * 100).toFixed(2)} 个百分点`
})
const gradcamUrl = computed(
  () =>
    props.heatmapUrl ||
    props.result?.heatmap_url ||
    props.result?.gradcam?.heatmap_url ||
    props.result?.gradcam?.overlay_url ||
    '',
)
const gradcamStatus = computed(() => props.result?.gradcam?.status || 'UNAVAILABLE')
const gradcamAvailable = computed(
  () =>
    Boolean(gradcamUrl.value) ||
    (Array.isArray(props.result?.images)
      ? props.result.images.some((item) => item.heatmap_url)
      : false),
)
const inferenceMs = computed(() => Number(props.result?.inference_ms || 0))
const imageCards = computed(() => {
  const items = Array.isArray(props.result?.images) ? props.result.images : []
  return items.map((item, index) => ({
    ...item,
    previewUrl: props.previewUrls[index] || props.previewUrl,
  }))
})
const isMultiPatient = computed(() => imageCards.value.length > 1)

watch(
  () => props.result?.prediction?.threshold,
  (value) => {
    adjustedThreshold.value = Number(value || 0.5101)
  },
)

function resetImageAdjustments() {
  imageInverted.value = false
  windowWidth.value = 255
  windowLevel.value = 128
}

function openFeedback(target = null) {
  feedbackTarget.value = target || {
    filename: props.result?.filename,
    label: labelEnglish.value,
  }
  feedbackLabel.value =
    (target?.final_label || target?.label) === 'PNEUMONIA'
      ? 'NORMAL'
      : 'PNEUMONIA'
  feedbackReason.value = ''
  feedbackVisible.value = true
}

function submitFeedback() {
  if (!feedbackLabel.value) return
  console.log('[AI 纠错反馈]', {
    record_id: props.result?.record_id,
    filename: feedbackTarget.value?.filename,
    actual_label: feedbackLabel.value,
    reason: feedbackReason.value.trim(),
  })
  feedbackVisible.value = false
  ElMessage.success('反馈已记录，感谢您的纠正')
}

function formatPatientClinical(item) {
  const genderMap = { MALE: '男', FEMALE: '女' }
  const parts = []
  if (item.age !== null && item.age !== undefined) parts.push(`${item.age} 岁`)
  if (item.gender) parts.push(genderMap[item.gender] || item.gender)
  if (item.temperature !== null && item.temperature !== undefined) {
    parts.push(`${item.temperature} ℃`)
  }
  if (item.cough_days !== null && item.cough_days !== undefined) {
    parts.push(`咳嗽 ${item.cough_days} 天`)
  }
  return parts.length ? parts.join(' · ') : '未填写临床信息'
}

const clinicalItems = computed(() => {
  const clinical = props.clinical || {}
  const genderMap = { MALE: '男', FEMALE: '女' }
  return [
    {
      label: '年龄',
      value: clinical.age ? `${clinical.age} 岁` : '未填写',
    },
    {
      label: '性别',
      value: genderMap[clinical.gender] || '未填写',
    },
    {
      label: '体温',
      value: clinical.temperature ? `${clinical.temperature} ℃` : '未填写',
    },
    {
      label: '咳嗽天数',
      value: clinical.cough_days ? `${clinical.cough_days} 天` : '未填写',
    },
  ]
})

const createdAt = computed(() => {
  const value = props.result?.created_at
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
})

function toggleCompareMode() {
  compareMode.value = !compareMode.value
}

function openHistoricalPicker() {
  historicalInput.value?.click()
}

function releaseHistoricalPreview() {
  if (historicalPreviewUrl.value) {
    URL.revokeObjectURL(historicalPreviewUrl.value)
    historicalPreviewUrl.value = ''
  }
}

function onHistoricalFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  historicalError.value = ''

  if (!file) return

  const extension = file.name.split('.').pop()?.toLowerCase() || ''
  if (!['jpg', 'jpeg', 'png'].includes(extension) || !['image/jpeg', 'image/png'].includes(file.type)) {
    historicalError.value = '对比影像仅支持 JPG、JPEG、PNG'
    ElMessage.error(historicalError.value)
    return
  }

  if (file.size > 10 * 1024 * 1024) {
    historicalError.value = '对比影像大小不得超过 10 MB'
    ElMessage.error(historicalError.value)
    return
  }

  releaseHistoricalPreview()
  historicalPreviewUrl.value = URL.createObjectURL(file)
}

function clearHistoricalImage() {
  releaseHistoricalPreview()
  historicalError.value = ''
}

async function waitForImages(root) {
  if (!root) return

  const images = Array.from(root.querySelectorAll('img'))
  await Promise.all(
    images.map((image) => {
      if (image.complete && image.naturalWidth > 0) return Promise.resolve()

      return new Promise((resolve) => {
        const finish = () => {
          image.removeEventListener('load', finish)
          image.removeEventListener('error', finish)
          resolve()
        }
        image.addEventListener('load', finish, { once: true })
        image.addEventListener('error', finish, { once: true })
        window.setTimeout(finish, 5000)
      })
    }),
  )
}

async function captureReportCanvas({ largeLayout = true } = {}) {
  const card = reportCardRef.value
  if (!card) throw new Error('结果卡片尚未准备完成')

  await document.fonts?.ready
  await nextTick()
  await waitForImages(card)

  card.classList.add('report-exporting')
  if (largeLayout) card.classList.add('report-export-large')
  await nextTick()
  await new Promise((resolve) => requestAnimationFrame(resolve))

  const pageBackground = getComputedStyle(document.documentElement)
    .getPropertyValue('--bg-page')
    .trim()

  try {
    return await html2canvas(card, {
      backgroundColor: pageBackground || '#f4f8fc',
      scale: 2,
      useCORS: true,
      allowTaint: false,
      imageTimeout: 15000,
      logging: false,
      onclone: (clonedDocument) => {
        clonedDocument
          .querySelectorAll('[data-export-ignore="true"]')
          .forEach((element) => element.remove())
      },
    })
  } finally {
    card.classList.remove('report-exporting')
    card.classList.remove('report-export-large')
  }
}

function exportFileName() {
  const stamp = new Date()
    .toISOString()
    .replace(/[:.]/g, '-')
    .slice(0, 19)
  return `AI辅助筛查结果_${stamp}.png`
}

async function exportReport() {
  if (!reportCardRef.value || exporting.value) return

  exporting.value = true

  try {
    const canvas = await captureReportCanvas()

    const blob = await new Promise((resolve) => {
      canvas.toBlob(resolve, 'image/png')
    })

    if (!blob) throw new Error('PNG 生成失败')

    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = exportFileName()
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)

    ElMessage.success('结果卡片已导出为 PNG')
  } catch (error) {
    console.error('图片导出失败', error)
    ElMessage.error('图片导出失败，请确认影像资源已加载后重试')
  } finally {
    exporting.value = false
  }
}

function pdfFileName() {
  const stamp = new Date()
    .toISOString()
    .replace(/[:.]/g, '-')
    .slice(0, 19)
  return `AI辅助筛查诊断报告_${stamp}.pdf`
}

async function exportPdfReport() {
  if (!reportCardRef.value || pdfExporting.value) return

  pdfExporting.value = true

  try {
    const canvas = await captureReportCanvas({ largeLayout: true })
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
    })

    const pageWidth = pdf.internal.pageSize.getWidth()
    const pageHeight = pdf.internal.pageSize.getHeight()
    const margin = 10
    const availableWidth = pageWidth - margin * 2
    const availableHeight = pageHeight - margin * 2
    const renderScale = availableWidth / canvas.width
    const pageSliceHeight = Math.max(
      1,
      Math.floor(availableHeight / renderScale),
    )

    let offset = 0
    let pageIndex = 0

    while (offset < canvas.height) {
      const sliceHeight = Math.min(
        pageSliceHeight,
        canvas.height - offset,
      )
      const slice = document.createElement('canvas')
      slice.width = canvas.width
      slice.height = sliceHeight
      const ctx = slice.getContext('2d')
      ctx.drawImage(
        canvas,
        0,
        offset,
        canvas.width,
        sliceHeight,
        0,
        0,
        canvas.width,
        sliceHeight,
      )

      if (pageIndex > 0) pdf.addPage()
      pdf.addImage(
        slice.toDataURL('image/png'),
        'PNG',
        margin,
        margin,
        availableWidth,
        sliceHeight * renderScale,
        undefined,
        'FAST',
      )

      offset += sliceHeight
      pageIndex += 1
    }

    pdf.save(pdfFileName())
    ElMessage.success('PDF 诊断报告已导出')
  } catch (error) {
    console.error('PDF 报告生成失败', error)
    ElMessage.error('PDF 报告生成失败，请确认影像资源已加载后重试')
  } finally {
    pdfExporting.value = false
  }
}

function probabilityWidth(value) {
  return `${Math.min(Math.max(Number(value) * 100, 0), 100)}%`
}

onBeforeUnmount(() => {
  releaseHistoricalPreview()
})</script>

<template>
  <section
    ref="reportCardRef"
    class="prediction-result glass-panel"
    :class="{ 'is-pneumonia': isPneumonia }"
  >
    <header class="result-header">
      <div>
        <p class="page-eyebrow">PNEUMO·AI · DIAGNOSTIC REPORT</p>
        <h2>肺炎 X 光片辅助筛查报告</h2>
        <p class="result-subtitle">
          记录 {{ result.record_id ? `#${result.record_id}` : '—' }} 已写入当前医生的历史记录
        </p>
      </div>
      <div class="result-header__right">
        <div class="result-time">
          <span>生成时间</span>
          <strong>{{ createdAt }}</strong>
        </div>
        <el-button
          class="result-close"
          circle
          :icon="Close"
          aria-label="关闭结果并开始新的筛查"
          title="关闭结果并继续筛查"
          @click="$emit('reset')"
        />
      </div>
    </header>

    <section v-if="!isMultiPatient" class="clinical-snapshot">
      <div class="clinical-snapshot__title">
        <strong>患者临床信息</strong>
        <small>用于影像 + 临床联合评估</small>
      </div>
      <div class="clinical-snapshot__grid">
        <div v-for="item in clinicalItems" :key="item.label">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </section>

    <div v-if="!isMultiPatient" class="result-hero">
      <div class="result-badge">
        <el-icon class="result-badge__icon">
          <WarningFilled v-if="isPneumonia" />
          <CircleCheckFilled v-else />
        </el-icon>
        <div>
          <span>模型判定类别</span>
          <strong>{{ labelText }}</strong>
          <small>{{ labelEnglish }}</small>
        </div>
      </div>

      <div class="confidence-block">
        <span>原始影像 AI 肺炎概率</span>
        <AnimatedPercent :value="imageProbability" />
        <small class="probability-source">image_prob · ResNet50 原始影像输出</small>
      </div>

      <div class="threshold-block">
        <div class="threshold-heading">
          <span>动态判定阈值</span>
          <strong class="mono">{{ adjustedThreshold.toFixed(4) }}</strong>
        </div>
        <el-slider
          v-model="adjustedThreshold"
          :min="0.1"
          :max="0.9"
          :step="0.0001"
          :show-tooltip="false"
          size="small"
          data-export-ignore="true"
        />
        <small>
          拖拽滑块仅模拟联合风险的灵敏度 / 特异度权衡，不修改 final_prob。
        </small>
        <div class="threshold-decision mono">
          联合肺炎概率 {{ (finalProbability * 100).toFixed(2) }}%
          <span>{{ isPneumonia ? '≥' : '<' }}</span>
          {{ adjustedThreshold.toFixed(4) }}
        </div>
      </div>
    </div>

    <section
      v-if="!isMultiPatient"
      class="multimodal-fusion"
      :class="{ 'has-clinical-risk': clinicalRiskElevated }"
      aria-labelledby="fusion-title"
    >
      <div class="multimodal-fusion__header">
        <div>
          <span class="multimodal-fusion__eyebrow">MULTIMODAL LATE FUSION</span>
          <h3 id="fusion-title">影像 + 临床联合评估</h3>
        </div>
        <span class="multimodal-fusion__chip">基于影像与临床多模态晚期融合</span>
      </div>

      <div class="fusion-row">
        <div class="fusion-row__heading">
          <span>临床文本提示</span>
          <small>clinical_risk</small>
        </div>
        <div class="clinical-risk-result" :class="{ 'is-missing': clinicalInfoMissing }">
          <el-icon class="clinical-risk-result__icon">
            <WarningFilled v-if="clinicalRiskElevated" />
            <Aim v-else-if="clinicalInfoMissing" />
            <CircleCheckFilled v-else />
          </el-icon>
          <div>
            <strong>{{ clinicalRisk }}</strong>
            <small>{{ clinicalRiskDescription }}</small>
          </div>
        </div>
      </div>

      <div class="fusion-row fusion-row--probability">
        <div class="fusion-row__heading">
          <span>联合预测风险</span>
          <small>final_prob · 不受阈值滑块调节影响</small>
        </div>
        <div class="fusion-probability">
          <div class="fusion-probability__value">
            <AnimatedPercent :value="finalProbability" :duration="1300" />
          </div>
          <span class="fusion-probability__delta">{{ fusionDeltaText }}</span>
        </div>
      </div>
    </section>

    <div v-if="!isMultiPatient" class="probability-panel">
      <div class="probability-row">
        <div class="probability-label">
          <span>联合 NORMAL 概率</span>
          <strong>{{ (normalProbability * 100).toFixed(2) }}%</strong>
        </div>
        <div class="probability-track">
          <span
            class="probability-fill probability-fill--normal"
            :style="{ width: probabilityWidth(normalProbability) }"
          ></span>
        </div>
      </div>

      <div class="probability-row">
        <div class="probability-label">
          <span>联合 PNEUMONIA 概率</span>
          <strong>{{ (pneumoniaProbability * 100).toFixed(2) }}%</strong>
        </div>
        <div class="probability-track">
          <span
            class="probability-fill probability-fill--pneumonia"
            :style="{ width: probabilityWidth(pneumoniaProbability) }"
          ></span>
        </div>
      </div>
    </div>

    <div class="image-view-toolbar" data-export-ignore="true">
      <div>
        <strong>影像视图</strong>
        <span>可开启正位 / 侧位影像独立对比</span>
      </div>
      <el-button
        :type="compareMode ? 'primary' : 'default'"
        plain
        @click="toggleCompareMode"
      >
        {{ compareMode ? '关闭对比模式' : '对比模式' }}
      </el-button>
    </div>

    <input
      ref="historicalInput"
      class="historical-file-input"
      type="file"
      accept=".jpg,.jpeg,.png,image/jpeg,image/png"
      @change="onHistoricalFile"
    />

    <Transition name="compare-fade">
      <section v-if="compareMode" class="clinical-compare">
        <figure class="image-panel">
          <figcaption>
            <span class="compare-index">A</span>
            <span>当前影像（正位）</span>
            <span class="view-hint">独立缩放 / 平移</span>
          </figcaption>
          <InteractiveImageViewer
            class="image-frame"
            :src="previewUrl"
            :alt="`${result.filename || '上传影像'} 正位影像`"
          >
            <template #base>
              <MedicalImageCanvas
                :src="previewUrl"
                :alt="`${result.filename || '上传影像'} 正位影像`"
                :window-width="windowWidth"
                :window-level="windowLevel"
                :inverted="imageInverted"
              />
            </template>
          </InteractiveImageViewer>
        </figure>

        <figure class="image-panel">
          <figcaption>
            <span class="compare-index">B</span>
            <span>历史影像（侧位）</span>
            <el-button
              v-if="historicalPreviewUrl"
              link
              type="danger"
              data-export-ignore="true"
              @click="clearHistoricalImage"
            >
              移除
            </el-button>
          </figcaption>

          <div
            v-if="!historicalPreviewUrl"
            class="historical-upload"
            data-export-ignore="true"
            role="button"
            tabindex="0"
            @click="openHistoricalPicker"
            @keydown.enter.prevent="openHistoricalPicker"
          >
            <span class="historical-upload__icon">
              <el-icon><UploadFilled /></el-icon>
            </span>
            <strong>上传历史或侧位影像</strong>
            <small>支持 JPG / PNG，最大 10 MB</small>
            <span v-if="historicalError" class="historical-upload__error">
              {{ historicalError }}
            </span>
          </div>

          <InteractiveImageViewer
            v-else
            class="image-frame"
            :src="historicalPreviewUrl"
            :alt="`${result.filename || '历史影像'} 侧位对比影像`"
          >
            <template #base>
              <MedicalImageCanvas
                :src="historicalPreviewUrl"
                alt="历史或侧位对比影像"
                :window-width="windowWidth"
                :window-level="windowLevel"
                :inverted="imageInverted"
              />
            </template>
          </InteractiveImageViewer>
        </figure>
      </section>
    </Transition>

    <div v-if="!isMultiPatient" class="image-compare">
      <figure class="image-panel">
        <figcaption>
          <span class="compare-index">01</span>
          <span>{{ imageCards.length > 1 ? '主影像（最高风险）' : '原始 X 光片' }}</span>
          <span class="view-hint">滚轮缩放 · 拖拽平移</span>
        </figcaption>
        <InteractiveImageViewer
          class="image-frame"
          :src="previewUrl"
          :alt="`${result.filename || '上传影像'} 原始 X 光片`"
        >
          <template #base>
            <MedicalImageCanvas
              :src="previewUrl"
              :alt="`${result.filename || '上传影像'} 原始 X 光片`"
              :window-width="windowWidth"
              :window-level="windowLevel"
              :inverted="imageInverted"
            />
          </template>
          <div v-if="!previewUrl" class="image-placeholder">
            <el-icon><Document /></el-icon>
            <span>原始影像预览不可用</span>
          </div>
        </InteractiveImageViewer>
      </figure>

      <figure class="image-panel">
        <figcaption>
          <span class="compare-index">02</span>
          <span>热力图（Grad-CAM 关注区域）</span>
          <span class="gradcam-status">{{ gradcamStatus }}</span>
        </figcaption>
        <InteractiveImageViewer
          class="image-frame image-frame--gradcam"
          :src="previewUrl"
          :alt="`${result.filename || '上传影像'} 原图与 Grad-CAM 叠加`"
        >
          <template #base>
            <MedicalImageCanvas
              :src="previewUrl"
              :alt="`${result.filename || '上传影像'} 原图与 Grad-CAM 底图`"
              :window-width="windowWidth"
              :window-level="windowLevel"
              :inverted="imageInverted"
            />
          </template>
          <img
            v-if="gradcamUrl"
            class="gradcam-overlay"
            :src="gradcamUrl"
            alt="Grad-CAM 模型关注区域热力图"
            :style="{ opacity: gradcamOpacity / 100 }"
          />
          <div v-else class="gradcam-placeholder">
            <span class="gradcam-placeholder__ring"></span>
            <el-icon><Aim /></el-icon>
            <strong>Grad-CAM 暂未生成</strong>
            <small>当前后端返回占位状态，分类结果不受影响</small>
          </div>
        </InteractiveImageViewer>
      </figure>
    </div>

    <section v-if="imageCards.length > 1" class="multi-image-results">
      <header class="multi-image-results__header">
        <div>
          <span>MULTI-PATIENT SCREENING</span>
          <strong>多受检者逐张筛查结果</strong>
        </div>
        <small>共 {{ imageCards.length }} 位受检者 · 逐位独立分析</small>
      </header>

      <div class="multi-image-grid">
        <article
          v-for="(item, index) in imageCards"
          :key="`${item.filename}-${index}`"
          class="multi-image-card"
        >
          <header class="multi-image-card__header">
            <strong>受检者 {{ index + 1 }}</strong>
            <small :title="item.filename">{{ item.filename }}</small>
          </header>
          <div class="multi-image-card__compare">
            <figure class="multi-image-card__figure">
              <figcaption>原图</figcaption>
              <el-image
                class="multi-image-card__image"
                :src="item.previewUrl"
                :preview-src-list="[item.previewUrl]"
                preview-teleported
                fit="contain"
                :alt="`${item.filename} 原图`"
              />
            </figure>
            <figure class="multi-image-card__figure">
              <figcaption>热力图</figcaption>
              <el-image
                class="multi-image-card__image"
                :src="item.heatmap_url || item.previewUrl"
                :preview-src-list="[item.heatmap_url || item.previewUrl]"
                preview-teleported
                fit="contain"
                :alt="`${item.filename} Grad-CAM 热力图`"
              />
            </figure>
          </div>
          <div class="multi-image-card__meta">
            <div
              class="multi-image-card__judgement"
              :class="{
                'is-normal': doctorJudgements[cardKey(item, index)] === 'NORMAL',
                'is-danger': doctorJudgements[cardKey(item, index)] === 'PNEUMONIA',
              }"
            >
              <span>医生判定</span>
              <el-select
                v-model="doctorJudgements[cardKey(item, index)]"
                size="small"
                clearable
                placeholder="未评判"
              >
                <el-option label="正常 NORMAL" value="NORMAL" />
                <el-option label="肺炎 PNEUMONIA" value="PNEUMONIA" />
              </el-select>
            </div>
            <small>
              AI 参考 · 肺炎概率
              {{ (Number(item.final_prob ?? item.prob_pneumonia) * 100).toFixed(2) }}%
            </small>
            <small>影像概率 {{ (Number(item.prob_pneumonia) * 100).toFixed(2) }}%</small>
            <small>临床信息 {{ formatPatientClinical(item) }}</small>
            <small v-if="item.clinical_risk">临床提示 {{ item.clinical_risk }}</small>
          </div>
        </article>
      </div>
    </section>

    <div class="gradcam-opacity" data-export-ignore="true">
      <div class="gradcam-opacity__label">
        <span>热力图叠加透明度</span>
        <strong class="mono">{{ gradcamOpacity }}%</strong>
      </div>
      <el-slider
        v-model="gradcamOpacity"
        :min="0"
        :max="100"
        :disabled="!gradcamAvailable"
        :show-tooltip="false"
        size="small"
      />
      <small v-if="!gradcamAvailable">当前没有可叠加的 Grad-CAM 热力图</small>
      <small v-else>
        0% 仅显示原图，100% 显示纯热力图，中间值为叠加效果
      </small>
    </div>

    <div v-if="!isMultiPatient" class="image-adjustments" data-export-ignore="true">
      <div class="image-adjustments__header">
        <div>
          <strong>影像阅片调节</strong>
          <span>Canvas 灰度重映射 · 模拟真实窗宽窗位</span>
        </div>
        <el-switch
          v-model="imageInverted"
          active-text="反色"
          inactive-text="原始"
          inline-prompt
        />
      </div>

      <div class="window-control">
        <div class="window-control__label">
          <span>窗宽 Window Width</span>
          <strong class="mono">{{ windowWidth }}</strong>
        </div>
        <el-slider
          v-model="windowWidth"
          :min="10"
          :max="255"
          :step="1"
          :show-tooltip="false"
          size="small"
        />
      </div>

      <div class="window-control">
        <div class="window-control__label">
          <span>窗位 Window Level</span>
          <strong class="mono">{{ windowLevel }}</strong>
        </div>
        <el-slider
          v-model="windowLevel"
          :min="0"
          :max="255"
          :step="1"
          :show-tooltip="false"
          size="small"
        />
      </div>

      <el-button class="window-reset" size="small" @click="resetImageAdjustments">
        重置窗宽窗位
      </el-button>
    </div>

    <div class="gradcam-note">
      <el-icon><Aim /></el-icon>
      高亮区域仅反映模型关注区域，不代表病灶边界或临床诊断依据。
    </div>

    <div class="result-meta">
      <div>
        <span>模型版本</span>
        <strong>{{ result.model_version || 'resnet50_baseline' }}</strong>
      </div>
      <div>
        <span>推理耗时</span>
        <strong>{{ inferenceMs }} ms</strong>
      </div>
      <div>
        <span>筛查医生</span>
        <strong>{{ userStore.displayName }}</strong>
      </div>
      <div>
        <span>文件</span>
        <strong :title="result.filename">{{ result.filename || '—' }}</strong>
      </div>
      <div class="result-meta__actions" data-export-ignore="true">
        <el-button
          :icon="Document"
          :loading="pdfExporting"
          @click="exportPdfReport"
        >
          导出诊断报告
        </el-button>
        <el-button
          :icon="Download"
          :loading="exporting"
          @click="exportReport"
        >
          导出图片
        </el-button>
        <el-button :icon="RefreshRight" @click="$emit('reset')">
          分析新影像
        </el-button>
      </div>
    </div>

    <div v-if="!isMultiPatient" class="feedback-row" data-export-ignore="true">
      <span>发现 AI 判定有误？</span>
      <el-button plain type="info" @click="openFeedback">
        反馈：AI判错了
      </el-button>
    </div>

    <el-dialog
      v-model="feedbackVisible"
      title="反馈 AI 判定结果"
      width="min(500px, 92vw)"
      class="feedback-dialog"
      append-to-body
      @closed="feedbackLabel = ''"
    >
      <p class="feedback-dialog__tip">
        请选择该受检者的真实诊断结果，反馈仅用于课程项目演示与模型改进。
      </p>
      <p v-if="feedbackTarget" class="feedback-dialog__target">
        受检者影像：{{ feedbackTarget.filename || '当前受检者' }}
      </p>
      <el-radio-group v-model="feedbackLabel" class="feedback-options">
        <el-radio value="NORMAL">正常（NORMAL）</el-radio>
        <el-radio value="PNEUMONIA">肺炎（PNEUMONIA）</el-radio>
      </el-radio-group>
      <el-input
        v-model="feedbackReason"
        class="feedback-reason"
        type="textarea"
        :rows="3"
        maxlength="200"
        show-word-limit
        placeholder="可选：填写 AI 判错的原因，例如病灶被遮挡或影像质量欠佳"
      />
      <template #footer>
        <el-button size="large" @click="feedbackVisible = false">取消</el-button>
        <el-button
          type="primary"
          size="large"
          :disabled="!feedbackLabel"
          @click="submitFeedback"
        >
          确认反馈
        </el-button>
      </template>
    </el-dialog>

    <div class="report-signature">
      <div>
        <span>筛查医生</span>
        <strong>{{ userStore.displayName }}</strong>
      </div>
      <div class="report-signature__line">
        <span>医师签名</span>
        <strong class="report-signature__signature">
          {{ userStore.displayName }}
        </strong>
      </div>
      <div>
        <span>报告生成时间</span>
        <strong>{{ createdAt }}</strong>
      </div>
    </div>

    <AppDisclaimer compact />
  </section>
</template>
<style scoped>
.prediction-result {
  position: relative;
  padding: clamp(22px, 3vw, 34px);
  overflow: hidden;
}

.prediction-result::before {
  position: absolute;
  top: 0;
  right: 0;
  width: 340px;
  height: 240px;
  pointer-events: none;
  content: '';
  background: radial-gradient(circle, rgba(34, 197, 94, 0.09), transparent 68%);
}

.prediction-result.is-pneumonia::before {
  background: radial-gradient(circle, rgba(239, 68, 68, 0.1), transparent 68%);
}

.result-header {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 24px;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 22px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.result-header h2 {
  margin: 0;
  font-size: clamp(24px, 2.7vw, 34px);
  line-height: 1.2;
  letter-spacing: -0.025em;
}

.result-subtitle {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  font-size: 11px;
}

.result-time {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  align-items: flex-end;
  color: var(--text-secondary);
  line-height: 1.45;
}

.result-time span {
  font-size: 14px;
  letter-spacing: 0.04em;
}

.result-time strong {
  margin-top: 5px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 15px;
  font-weight: 600;
}

.result-close {
  flex: 0 0 auto;
}

.result-close :deep(.el-icon) {
  font-size: 18px;
}

.result-hero {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(210px, 0.9fr) minmax(230px, 1fr) minmax(250px, 1.1fr);
  gap: 18px;
  padding: 24px 0;
}

.result-badge,
.confidence-block,
.threshold-block {
  min-height: 150px;
  padding: 20px;
  background: rgba(2, 6, 23, 0.32);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 16px;
}

.result-badge {
  display: flex;
  gap: 16px;
  align-items: center;
  color: var(--color-success);
  background: linear-gradient(145deg, rgba(34, 197, 94, 0.09), rgba(2, 6, 23, 0.3));
  border-color: rgba(34, 197, 94, 0.2);
}

.is-pneumonia .result-badge {
  color: var(--color-danger);
  background: linear-gradient(145deg, rgba(239, 68, 68, 0.1), rgba(2, 6, 23, 0.3));
  border-color: rgba(239, 68, 68, 0.22);
}

.result-badge__icon {
  flex: 0 0 auto;
  font-size: 48px;
  filter: drop-shadow(0 0 15px currentColor);
}

.result-badge > div {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.result-badge span,
.confidence-block > span,
.threshold-block > span {
  color: var(--color-text-muted);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.result-badge strong {
  margin-top: 8px;
  color: currentColor;
  font-size: 28px;
  font-weight: 700;
}

.result-badge small {
  margin-top: 5px;
  color: currentColor;
  font-family: var(--font-mono);
  font-size: 10px;
  opacity: 0.72;
}

.confidence-block {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.confidence-block > small {
  margin-top: 12px;
  color: var(--color-text-muted);
  font-size: 10px;
}

.threshold-block {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.threshold-block strong {
  margin: 10px 0 8px;
  color: var(--color-primary-strong);
  font-size: 31px;
  font-weight: 650;
  letter-spacing: -0.03em;
}

.threshold-block small {
  max-width: 260px;
  color: var(--color-text-muted);
  font-size: 10px;
  line-height: 1.65;
}
.probability-source {
  color: var(--color-text-faint) !important;
  font-family: var(--font-mono);
  font-size: 8px !important;
  letter-spacing: 0.02em;
}

.multimodal-fusion {
  position: relative;
  z-index: 1;
  padding: 18px;
  margin-bottom: 20px;
  overflow: hidden;
  background:
    linear-gradient(115deg, rgba(6, 182, 212, 0.075), transparent 48%),
    rgba(2, 6, 23, 0.25);
  border: 1px solid rgba(6, 182, 212, 0.16);
  border-radius: 17px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.035),
    0 16px 40px rgba(2, 6, 23, 0.12);
}

.multimodal-fusion::after {
  position: absolute;
  top: -90px;
  right: -65px;
  width: 280px;
  height: 220px;
  pointer-events: none;
  content: '';
  background: radial-gradient(circle, rgba(34, 211, 238, 0.11), transparent 68%);
}

.multimodal-fusion.has-clinical-risk {
  background:
    linear-gradient(115deg, rgba(239, 68, 68, 0.075), transparent 48%),
    rgba(2, 6, 23, 0.25);
  border-color: rgba(239, 68, 68, 0.18);
}

.multimodal-fusion__header,
.fusion-row {
  position: relative;
  z-index: 1;
}

.multimodal-fusion__header {
  display: flex;
  gap: 18px;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--glass-border);
}

.multimodal-fusion__eyebrow {
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.12em;
}

.multimodal-fusion__header h3 {
  margin: 5px 0 0;
  color: var(--color-text);
  font-size: 15px;
  font-weight: 650;
}

.multimodal-fusion__chip {
  flex: 0 0 auto;
  padding: 5px 9px;
  color: var(--color-primary-strong);
  font-size: 8px;
  background: rgba(6, 182, 212, 0.08);
  border: 1px solid rgba(6, 182, 212, 0.18);
  border-radius: var(--radius-pill);
}

.fusion-row {
  display: grid;
  grid-template-columns: minmax(170px, 0.34fr) minmax(0, 1fr);
  gap: 20px;
  align-items: center;
  padding: 16px 0;
}

.fusion-row + .fusion-row {
  border-top: 1px solid var(--glass-border);
}

.fusion-row__heading {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.fusion-row__heading span {
  color: var(--color-text-soft);
  font-size: 11px;
  font-weight: 600;
}

.fusion-row__heading small {
  margin-top: 4px;
  color: var(--color-text-faint);
  font-family: var(--font-mono);
  font-size: 8px;
}

.clinical-risk-result {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
  padding: 12px 14px;
  background: rgba(34, 197, 94, 0.045);
  border: 1px solid rgba(34, 197, 94, 0.13);
  border-radius: 12px;
}

.has-clinical-risk .clinical-risk-result {
  background: rgba(239, 68, 68, 0.055);
  border-color: rgba(239, 68, 68, 0.16);
}

.clinical-risk-result__icon {
  flex: 0 0 auto;
  color: var(--color-success);
  font-size: 25px;
  filter: drop-shadow(0 0 10px currentColor);
}

.has-clinical-risk .clinical-risk-result__icon {
  color: var(--color-danger);
}

.clinical-risk-result.is-missing {
  background: color-mix(in srgb, var(--text-primary) 3.5%, transparent);
  border-color: var(--border-color);
}

.clinical-risk-result.is-missing .clinical-risk-result__icon {
  color: var(--text-tertiary);
}

.clinical-risk-result.is-missing strong {
  color: var(--text-secondary);
}

.clinical-risk-result > div {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.45;
}

.clinical-risk-result strong {
  color: var(--color-success);
  font-size: 16px;
  font-weight: 650;
}

.has-clinical-risk .clinical-risk-result strong {
  color: var(--color-danger);
}

.clinical-risk-result small {
  margin-top: 3px;
  color: var(--color-text-muted);
  font-size: 9px;
}

.fusion-row--probability {
  padding-bottom: 4px;
}

.fusion-probability {
  display: flex;
  gap: 18px;
  align-items: flex-end;
  justify-content: space-between;
  min-width: 0;
}

.fusion-probability__value {
  min-width: 0;
  line-height: 1;
}

.fusion-probability__value :deep(.animated-percent) {
  color: var(--color-success);
  font-size: clamp(48px, 6.5vw, 78px);
  text-shadow: 0 0 30px rgba(34, 197, 94, 0.2);
}

.is-pneumonia .fusion-probability__value :deep(.animated-percent) {
  color: var(--color-danger);
  text-shadow: 0 0 32px rgba(239, 68, 68, 0.23);
}

.fusion-probability__delta {
  flex: 0 0 auto;
  padding: 5px 9px;
  margin-bottom: 5px;
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 8px;
  background: rgba(6, 182, 212, 0.07);
  border: 1px solid rgba(6, 182, 212, 0.14);
  border-radius: var(--radius-pill);
}

.probability-panel {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  padding: 0 0 24px;
}

.probability-row {
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
}

.probability-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 9px;
  color: var(--color-text-muted);
  font-size: 10px;
}

.probability-label strong {
  color: var(--color-text);
  font-family: var(--font-mono);
  font-size: 11px;
}

.probability-track {
  height: 5px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.12);
  border-radius: var(--radius-pill);
}

.probability-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  transition: width 900ms cubic-bezier(0.22, 1, 0.36, 1);
}

.probability-fill--normal {
  background: linear-gradient(90deg, #16a34a, #4ade80);
  box-shadow: 0 0 12px rgba(34, 197, 94, 0.35);
}

.probability-fill--pneumonia {
  background: linear-gradient(90deg, #dc2626, #f87171);
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.35);
}

.image-compare {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  padding-bottom: 18px;
}

.multi-image-results {
  padding: 16px;
  margin-bottom: 18px;
  background: rgba(6, 182, 212, 0.035);
  border: 1px solid rgba(6, 182, 212, 0.12);
  border-radius: 13px;
}

.multi-image-results__header {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  justify-content: space-between;
  padding-bottom: 11px;
  margin-bottom: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}

.multi-image-results__header > div {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.multi-image-results__header span {
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.1em;
}

.multi-image-results__header strong {
  margin-top: 3px;
  color: var(--color-text-soft);
  font-size: 12px;
  font-weight: 650;
}

.multi-image-results__header small {
  color: var(--color-text-faint);
  font-size: 8px;
}

.multi-image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
}

.multi-image-card {
  overflow: hidden;
  background: rgba(2, 6, 23, 0.26);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 11px;
}

.multi-image-card__header {
  display: flex;
  gap: 10px;
  align-items: baseline;
  justify-content: space-between;
  padding: 12px 14px;
  background: color-mix(in srgb, var(--brand) 7%, transparent);
  border-bottom: 1px solid var(--border-color);
}

.multi-image-card__header strong {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 700;
}

.multi-image-card__header small {
  overflow: hidden;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.multi-image-card__compare {
  position: relative;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 10px;
  background: color-mix(in srgb, var(--bg-page) 55%, transparent);
  border-bottom: 1px solid var(--border-color);
}

.multi-image-card__figure {
  min-width: 0;
  margin: 0;
}

.multi-image-card__figure figcaption {
  margin-bottom: 5px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.multi-image-card__image {
  display: block;
  width: 100%;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  cursor: zoom-in;
  background: color-mix(in srgb, var(--bg-card) 80%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 9px;
}

.multi-image-card__image :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.multi-image-card__index {
  position: absolute;
  top: 14px;
  left: 14px;
  z-index: 3;
  padding: 4px 9px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 12px;
  background: color-mix(in srgb, var(--bg-card) 82%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 24%, transparent);
  border-radius: 6px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.multi-image-card__meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
}

.multi-image-card__meta strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.multi-image-card__judgement {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  margin: 4px 0;
  background: color-mix(in srgb, var(--text-primary) 3.5%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 9px;
}

.multi-image-card__judgement.is-normal {
  background: color-mix(in srgb, var(--success) 9%, transparent);
  border-color: color-mix(in srgb, var(--success) 26%, transparent);
}

.multi-image-card__judgement.is-danger {
  background: color-mix(in srgb, var(--danger) 9%, transparent);
  border-color: color-mix(in srgb, var(--danger) 26%, transparent);
}

.multi-image-card__judgement > span {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.multi-image-card__judgement :deep(.el-select) {
  width: min(180px, 100%);
}

.multi-image-card__meta small {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.5;
}

.multi-image-card__feedback {
  align-self: flex-start;
  padding: 0;
  margin-top: 4px;
  font-size: 13px;
}

.image-panel {
  min-width: 0;
  margin: 0;
}

.image-panel figcaption {
  display: flex;
  gap: 9px;
  align-items: center;
  min-height: 28px;
  color: var(--color-text-soft);
  font-size: 11px;
  font-weight: 600;
}

.compare-index {
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 9px;
}

.gradcam-status {
  padding: 3px 7px;
  margin-left: auto;
  color: var(--color-warning);
  font-family: var(--font-mono);
  font-size: 8px;
  font-weight: 500;
  background: rgba(245, 158, 11, 0.07);
  border: 1px solid rgba(245, 158, 11, 0.18);
  border-radius: var(--radius-pill);
}

.image-frame {
  position: relative;
  display: grid;
  min-height: 330px;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% 45%, rgba(6, 182, 212, 0.06), transparent 55%),
    rgba(2, 6, 23, 0.62);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 16px;
  place-items: center;
}

.image-frame::before {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.025) 1px, transparent 1px);
  background-size: 24px 24px;
}

.image-frame img {
  width: 100%;
  height: 100%;
  max-height: 520px;
  object-fit: contain;
}

.image-frame--gradcam {
  border-color: rgba(6, 182, 212, 0.14);
}

.image-placeholder,
.gradcam-placeholder {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 9px;
  align-items: center;
  padding: 24px;
  color: var(--color-text-faint);
  text-align: center;
}

.image-placeholder .el-icon {
  font-size: 38px;
}

.gradcam-placeholder > .el-icon {
  color: var(--color-primary);
  font-size: 34px;
  filter: drop-shadow(0 0 12px rgba(6, 182, 212, 0.48));
}

.gradcam-placeholder strong {
  color: var(--color-text-soft);
  font-size: 12px;
  font-weight: 600;
}

.gradcam-placeholder small {
  color: var(--color-text-faint);
  font-size: 9px;
}

.gradcam-placeholder__ring {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 150px;
  height: 150px;
  pointer-events: none;
  border: 1px solid rgba(34, 211, 238, 0.09);
  border-radius: 50%;
  box-shadow:
    0 0 0 26px rgba(6, 182, 212, 0.025),
    0 0 0 52px rgba(6, 182, 212, 0.015);
  transform: translate(-50%, -50%);
}

.gradcam-note {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  padding: 11px 14px;
  margin-bottom: 18px;
  color: var(--color-text-muted);
  font-size: 10px;
  background: rgba(6, 182, 212, 0.04);
  border: 1px solid rgba(6, 182, 212, 0.12);
  border-radius: 10px;
}

.gradcam-note .el-icon {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--color-primary);
}
.result-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) auto;
  gap: 12px;
  padding: 17px 0 20px;
  margin-bottom: 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
}

.result-meta > div {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.4;
}

.result-meta span {
  color: var(--color-text-faint);
  font-size: 8px;
  letter-spacing: 0.07em;
}

.result-meta strong {
  overflow: hidden;
  margin-top: 4px;
  color: var(--color-text-soft);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-meta__actions {
  gap: 6px;
  justify-content: center;
  align-items: flex-end;
}

.result-meta__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.threshold-heading {
  display: flex;
  gap: 12px;
  align-items: baseline;
  justify-content: space-between;
}

.threshold-heading strong {
  margin: 0;
  color: var(--color-primary-strong);
  font-size: 24px;
  font-weight: 650;
  letter-spacing: -0.03em;
}

.threshold-block :deep(.el-slider) {
  margin: 10px 4px 4px;
}

.threshold-block :deep(.el-slider__runway) {
  background: rgba(148, 163, 184, 0.16);
}

.threshold-decision {
  margin-top: 8px;
  color: var(--color-text-muted);
  font-size: 9px;
}

.threshold-decision span {
  color: var(--color-primary-strong);
  font-weight: 700;
}

.view-hint {
  margin-left: auto;
  color: var(--color-text-faint);
  font-size: 8px;
  font-weight: 400;
}

.gradcam-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
  transition: opacity 180ms ease;
}

.image-adjustments {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr)) auto;
  gap: 12px 18px;
  align-items: center;
  padding: 14px 15px;
  margin-bottom: 14px;
  background: rgba(6, 182, 212, 0.035);
  border: 1px solid rgba(6, 182, 212, 0.12);
  border-radius: 11px;
}

.image-adjustments__header {
  display: flex;
  grid-column: 1 / -1;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 9px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}

.image-adjustments__header > div {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.image-adjustments__header strong {
  color: var(--color-text-soft);
  font-size: 10px;
  font-weight: 600;
}

.image-adjustments__header span {
  margin-top: 3px;
  color: var(--color-text-faint);
  font-size: 8px;
}

.window-control {
  min-width: 0;
}

.window-control__label {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  color: var(--color-text-muted);
  font-size: 9px;
}

.window-control__label strong {
  color: var(--color-primary-strong);
  font-size: 10px;
}

.window-control :deep(.el-slider) {
  margin: 7px 4px 0;
}

.window-control :deep(.el-slider__runway) {
  background: rgba(148, 163, 184, 0.15);
}

.window-reset {
  align-self: end;
}
.gradcam-opacity {
  display: grid;
  grid-template-columns: minmax(145px, auto) minmax(0, 1fr);
  gap: 5px 16px;
  align-items: center;
  padding: 12px 15px;
  margin-bottom: 18px;
  background: rgba(6, 182, 212, 0.035);
  border: 1px solid rgba(6, 182, 212, 0.12);
  border-radius: 11px;
}

.gradcam-opacity__label {
  display: flex;
  gap: 8px;
  align-items: baseline;
  justify-content: space-between;
  color: var(--color-text-muted);
  font-size: 9px;
}

.gradcam-opacity__label strong {
  color: var(--color-primary-strong);
  font-size: 10px;
}

.gradcam-opacity :deep(.el-slider) {
  margin: 0 5px;
}

.gradcam-opacity small {
  grid-column: 2;
  color: var(--color-text-faint);
  font-size: 8px;
}

.feedback-row {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 30;
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: flex-end;
  padding: 10px 12px;
  background: color-mix(in srgb, var(--bg-card) 86%, transparent);
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  box-shadow: var(--shadow-pop);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.feedback-row > span {
  color: var(--text-secondary);
  font-size: 14px;
}

.feedback-dialog__tip {
  margin: 0 0 18px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.feedback-dialog__target {
  margin: -8px 0 16px;
  padding: 9px 11px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 13px;
  background: color-mix(in srgb, var(--text-primary) 4%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.feedback-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.result-header__right {
  display: flex;
  flex: 0 0 auto;
  gap: 12px;
  align-items: flex-start;
}

.image-view-toolbar {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  padding: 10px 2px 13px;
}

.image-view-toolbar > div {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.image-view-toolbar strong {
  color: var(--color-text-soft);
  font-size: 11px;
  font-weight: 600;
}

.image-view-toolbar span {
  margin-top: 3px;
  color: var(--color-text-faint);
  font-size: 8px;
}

.historical-file-input {
  display: none;
}

.clinical-compare {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  padding-bottom: 20px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--glass-border);
}

.historical-upload {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 330px;
  padding: 24px;
  color: var(--color-text-muted);
  text-align: center;
  cursor: pointer;
  background:
    radial-gradient(circle at 50% 44%, rgba(6, 182, 212, 0.055), transparent 48%),
    var(--surface-subtle);
  border: 1px dashed rgba(6, 182, 212, 0.25);
  border-radius: 16px;
  outline: none;
  transition:
    background var(--transition-base),
    border-color var(--transition-base);
}

.historical-upload:hover,
.historical-upload:focus-visible {
  background:
    radial-gradient(circle at 50% 44%, rgba(6, 182, 212, 0.11), transparent 50%),
    var(--surface-subtle);
  border-color: rgba(6, 182, 212, 0.52);
}

.historical-upload__icon {
  display: grid;
  width: 52px;
  height: 52px;
  margin-bottom: 14px;
  color: var(--color-primary-strong);
  background: rgba(6, 182, 212, 0.07);
  border: 1px solid rgba(6, 182, 212, 0.16);
  border-radius: 15px;
  font-size: 23px;
  place-items: center;
}

.historical-upload strong {
  color: var(--color-text-soft);
  font-size: 12px;
  font-weight: 600;
}

.historical-upload small {
  margin-top: 6px;
  color: var(--color-text-faint);
  font-size: 9px;
}

.historical-upload__error {
  margin-top: 9px;
  color: var(--color-danger);
  font-size: 9px;
}

.compare-fade-enter-active,
.compare-fade-leave-active {
  transition:
    opacity 240ms ease,
    transform 260ms ease;
}

.compare-fade-enter-from,
.compare-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
@media (max-width: 1080px) {
.clinical-snapshot {
  position: relative;
  z-index: 1;
  padding: 16px 18px;
  margin-top: 18px;
  background: color-mix(in srgb, var(--text-primary) 3.5%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 13px;
}

.clinical-snapshot__title {
  display: flex;
  gap: 12px;
  align-items: baseline;
  justify-content: space-between;
  padding-bottom: 11px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.clinical-snapshot__title strong {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 650;
}

.clinical-snapshot__title small {
  color: var(--text-tertiary);
  font-size: 13px;
}

.clinical-snapshot__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.clinical-snapshot__grid > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.clinical-snapshot__grid span {
  color: var(--text-tertiary);
  font-size: 13px;
}

.clinical-snapshot__grid strong {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}

.result-hero {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .threshold-block {
    grid-column: 1 / -1;
    min-height: auto;
  }
}

@media (max-width: 760px) {
  .result-header {
    flex-direction: column;
  }

  .feedback-row {
    right: 14px;
    bottom: 14px;
    left: 14px;
    justify-content: space-between;
  }

  .clinical-snapshot__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .report-signature {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .result-time {
    align-items: flex-start;
  }

  .result-hero,
  .probability-panel,
  .image-compare {
    grid-template-columns: 1fr;
  }
  .multimodal-fusion__header,
  .fusion-probability {
    flex-direction: column;
  }

  .multimodal-fusion__chip {
    align-self: flex-start;
  }

  .fusion-row {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .fusion-probability__delta {
    margin-bottom: 0;
  }


  .threshold-block {
    grid-column: auto;
  }

  .image-frame {
    min-height: 260px;
  }

  .image-adjustments {
    grid-template-columns: 1fr;
  }

  .window-reset {
    justify-self: start;
  }

  .gradcam-opacity {
    grid-template-columns: 1fr;
  }

  .gradcam-opacity small {
    grid-column: 1;
  }

  .result-meta {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .result-meta__actions {
    align-items: flex-start;
  }
}

@media (max-width: 480px) {
  .result-meta {
    grid-template-columns: 1fr;
  }

  .clinical-snapshot__grid {
    grid-template-columns: 1fr;
  }
}

.report-signature {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(180px, 1.2fr) minmax(0, 1fr);
  gap: 18px;
  align-items: end;
  padding: 18px 0;
  margin-bottom: 16px;
  border-top: 1px dashed var(--border-strong);
}

.report-signature > div {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.report-signature span {
  color: var(--text-tertiary);
  font-size: 13px;
}

.report-signature strong {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}

.report-signature__line {
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-strong);
}

.report-signature__signature {
  margin-top: 4px;
  color: var(--brand) !important;
  font-family: 'Segoe Script', 'Bradley Hand', 'KaiTi', cursive;
  font-size: 28px !important;
  font-weight: 500 !important;
  line-height: 1.2;
  letter-spacing: 0.04em;
}

/* 结果详情可读性 */
.result-subtitle,
.result-badge span,
.confidence-block > span,
.threshold-block > span,
.threshold-block small,
.fusion-row__heading span,
.clinical-risk-result small,
.probability-label,
.image-panel figcaption,
.gradcam-note,
.gradcam-opacity__label,
.gradcam-opacity small,
.window-control__label,
.image-adjustments__header span,
.analysis-actions__note,
.feedback-row > span {
  font-size: 14px;
  line-height: 1.6;
}

.result-badge small,
.probability-source,
.multi-image-results__header small,
.multi-image-card__meta strong,
.multi-image-card__meta small,
.image-view-toolbar span,
.view-hint,
.result-meta span,
.result-meta strong,
.fusion-row__heading small,
.fusion-probability__delta,
.gradcam-status,
.multi-image-card__label {
  font-size: 13px;
}

.gradcam-note,
.feedback-dialog__tip {
  font-size: 14px;
  line-height: 1.7;
}

.feedback-reason {
  margin-top: 16px;
}

.feedback-options {
  gap: 14px;
}

:global(.feedback-dialog.el-dialog) {
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--bg-elevated) 96%, transparent), color-mix(in srgb, var(--bg-card) 94%, transparent));
  border: 1px solid var(--border-strong);
  border-radius: 18px;
  box-shadow: var(--shadow-pop);
  backdrop-filter: blur(22px) saturate(1.25);
  -webkit-backdrop-filter: blur(22px) saturate(1.25);
}

:global(.feedback-dialog .el-dialog__title) {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 650;
}

:global(.feedback-dialog .el-dialog__body) {
  color: var(--text-secondary);
}

:global(.feedback-dialog .el-dialog__footer) {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
</style>