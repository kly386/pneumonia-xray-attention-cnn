<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  Aim,
  Clock,
  Delete,
  Document,
  Picture,
  RefreshLeft,
  Sunny,
  UploadFilled,
  User,
  VideoPlay,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import http from '@/api/http'
import { useTheme } from '@/composables/useTheme'
import { startPageTour, startPageTourOnce, onPageTourRequest } from '@/composables/usePageTour'
import PredictionResult from '@/components/workspace/PredictionResult.vue'
import ScanningOverlay from '@/components/workspace/ScanningOverlay.vue'

defineOptions({ name: 'WorkspaceView' })

const { isDark } = useTheme()

const MAX_FILE_SIZE = 10 * 1024 * 1024
const MAX_IMAGES = 3
const ALLOWED_EXTENSIONS = new Set(['jpg', 'jpeg', 'png'])
const ALLOWED_MIME_TYPES = new Set(['image/jpeg', 'image/png'])
const MIN_ANALYSIS_MS = 1100
const CLINICAL_FIELD_RULES = Object.freeze({
  age: {
    label: '年龄',
    min: 0,
    max: 120,
    step: 1,
    integer: true,
  },
  temperature: {
    label: '体温',
    min: 30,
    max: 45,
    step: 0.1,
    integer: false,
  },
  cough_days: {
    label: '咳嗽天数',
    min: 0,
    max: 365,
    step: 1,
    integer: true,
  },
})

const fileInput = ref()
const selectedFiles = ref([])
const dragging = ref(false)
const result = ref(null)
const resultPreviewUrl = ref('')
const analysisState = ref('idle')
const analysisStage = ref('preprocess')
const analysisError = ref('')
const clinicalValidationError = ref('')
const stageTimers = []
let analysisRunId = 0

function createClinicalForm() {
  return {
    age: '',
    gender: '',
    temperature: '',
    cough_days: '',
  }
}

const isAnalyzing = computed(() => analysisState.value === 'analyzing')
const canAnalyze = computed(
  () => selectedFiles.value.length > 0 && !isAnalyzing.value,
)
const selectedFile = computed(() => selectedFiles.value[0]?.file || null)
const previewUrl = computed(() => selectedFiles.value[0]?.url || '')
const previewUrls = computed(() =>
  selectedFiles.value.map((item) => item.url),
)

function formatFileSize(size) {
  if (!size) return '0 KB'
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

const totalSizeText = computed(() =>
  formatFileSize(
    selectedFiles.value.reduce((sum, item) => sum + item.file.size, 0),
  ),
)

const clinicalSnapshot = computed(() => {
  const primaryIndex = Number.isInteger(result.value?.primary_index)
    ? result.value.primary_index
    : 0
  return selectedFiles.value[primaryIndex]?.clinical || createClinicalForm()
})

const stageLabel = computed(() => {
  return {
    preprocess: '正在预处理影像…',
    inference: '正在提取影像特征…',
    finalize: '正在生成辅助结果…',
  }[analysisStage.value]
})

function validateClinicalField(form, field, labelPrefix = '') {
  const rule = CLINICAL_FIELD_RULES[field]
  const rawValue = String(form?.[field] ?? '').trim()

  if (!rule || !form) return false
  if (rawValue === '') {
    form[field] = ''
    return true
  }

  const numericValue = Number(rawValue)
  if (!Number.isFinite(numericValue)) {
    clinicalValidationError.value = `${labelPrefix}${rule.label}必须填写有效数字`
    return false
  }

  if (rule.integer && !Number.isInteger(numericValue)) {
    clinicalValidationError.value = `${labelPrefix}${rule.label}必须填写整数`
    return false
  }

  if (numericValue < rule.min || numericValue > rule.max) {
    clinicalValidationError.value =
      `${labelPrefix}${rule.label}需在 ${rule.min}–${rule.max} 之间`
    return false
  }

  form[field] = String(numericValue)
  clinicalValidationError.value = ''
  return true
}

function validateClinicalForm() {
  clinicalValidationError.value = ''

  for (let index = 0; index < selectedFiles.value.length; index += 1) {
    const item = selectedFiles.value[index]
    for (const field of Object.keys(CLINICAL_FIELD_RULES)) {
      if (!validateClinicalField(item.clinical, field, `影像 ${index + 1}：`)) {
        ElMessage.error(clinicalValidationError.value)
        return false
      }
    }
  }

  return true
}

function appendPatientsData(formData) {
  const patients = selectedFiles.value.map((item) => {
    const clinical = item.clinical
    return {
      gender: clinical.gender || null,
      age: clinical.age === '' ? null : Number(clinical.age),
      temperature:
        clinical.temperature === '' ? null : Number(clinical.temperature),
      cough_days:
        clinical.cough_days === '' ? null : Number(clinical.cough_days),
    }
  })
  formData.append('patients_data', JSON.stringify(patients))
}

function clearStageTimers() {
  stageTimers.forEach((timer) => window.clearTimeout(timer))
  stageTimers.length = 0
}

function scheduleAnalysisStages() {
  clearStageTimers()
  analysisStage.value = 'preprocess'
  stageTimers.push(
    window.setTimeout(() => {
      analysisStage.value = 'inference'
    }, 260),
  )
  stageTimers.push(
    window.setTimeout(() => {
      analysisStage.value = 'finalize'
    }, 900),
  )
}

function validateFile(file) {
  if (!file) return '请选择一张 X 光片'

  const extension = file.name.split('.').pop()?.toLowerCase() || ''
  if (!ALLOWED_EXTENSIONS.has(extension) || !ALLOWED_MIME_TYPES.has(file.type)) {
    return '仅支持 JPG、JPEG、PNG 格式的影像'
  }

  if (file.size <= 0) return '文件为空或已损坏'
  if (file.size > MAX_FILE_SIZE) return '文件大小不得超过 10 MB'

  return ''
}

function releasePreviews() {
  selectedFiles.value.forEach((item) => URL.revokeObjectURL(item.url))
  selectedFiles.value = []
}

function fileKey(file) {
  return `${file.name}-${file.size}-${file.lastModified}`
}

function addFiles(files) {
  if (isAnalyzing.value) return

  const incoming = Array.from(files || [])
  if (!incoming.length) return

  const remaining = MAX_IMAGES - selectedFiles.value.length
  if (remaining <= 0) {
    ElMessage.warning(`单次最多上传 ${MAX_IMAGES} 张影像`)
    return
  }

  const existingKeys = new Set(
    selectedFiles.value.map((item) => fileKey(item.file)),
  )
  const accepted = []
  let skippedByLimit = false

  for (const file of incoming) {
    if (accepted.length >= remaining) {
      skippedByLimit = true
      break
    }

    const validationError = validateFile(file)
    if (validationError) {
      ElMessage.error(`${file.name}：${validationError}`)
      continue
    }

    const key = fileKey(file)
    if (existingKeys.has(key)) continue

    existingKeys.add(key)
    accepted.push({
      id: key,
      file,
      url: URL.createObjectURL(file),
      clinical: createClinicalForm(),
    })
  }

  if (skippedByLimit) {
    ElMessage.warning(`单次最多上传 ${MAX_IMAGES} 张影像，已忽略多余文件`)
  }

  if (!accepted.length) return

  selectedFiles.value = [...selectedFiles.value, ...accepted]
  result.value = null
  resultPreviewUrl.value = ''
  analysisError.value = ''
  analysisState.value = 'selected'
}

function openFilePicker() {
  if (!isAnalyzing.value) {
    fileInput.value?.click()
  }
}

function onFileInput(event) {
  addFiles(event.target.files)
  event.target.value = ''
}

function onDrop(event) {
  dragging.value = false
  if (isAnalyzing.value) return

  const files = Array.from(event.dataTransfer?.files || [])
  if (!files.length) return

  addFiles(files)
}

function removeFile(index) {
  if (isAnalyzing.value) return

  const [removed] = selectedFiles.value.splice(index, 1)
  if (removed) URL.revokeObjectURL(removed.url)

  result.value = null
  resultPreviewUrl.value = ''
  analysisError.value = ''
  if (!selectedFiles.value.length) {
    analysisState.value = 'idle'
  }
}

function resetWorkspace() {
  analysisRunId += 1
  clearStageTimers()
  releasePreviews()
  result.value = null
  resultPreviewUrl.value = ''
  analysisError.value = ''
  analysisStage.value = 'preprocess'
  analysisState.value = 'idle'
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

async function startAnalysis() {
  if (!selectedFiles.value.length || isAnalyzing.value) return
  if (!validateClinicalForm()) return

  const runId = ++analysisRunId
  analysisState.value = 'analyzing'
  analysisError.value = ''
  result.value = null
  scheduleAnalysisStages()

  const startedAt = performance.now()
  const formData = new FormData()
  selectedFiles.value.forEach((item) => {
    formData.append('files', item.file, item.file.name)
  })
  appendPatientsData(formData)

  try {
    const { data } = await http.post('/predict', formData)
    if (runId !== analysisRunId) return

    const elapsed = performance.now() - startedAt
    if (elapsed < MIN_ANALYSIS_MS) {
      await wait(MIN_ANALYSIS_MS - elapsed)
    }
    if (runId !== analysisRunId) return

    const primaryIndex = Number.isInteger(data.primary_index)
      ? data.primary_index
      : 0
    resultPreviewUrl.value =
      selectedFiles.value[primaryIndex]?.url || previewUrl.value
    result.value = data
    analysisState.value = 'success'
    ElMessage.success('AI 辅助筛查完成')
  } catch (error) {
    if (runId !== analysisRunId) return

    const elapsed = performance.now() - startedAt
    if (elapsed < 650) {
      await wait(650 - elapsed)
    }
    if (runId !== analysisRunId) return

    analysisState.value = 'error'
    analysisError.value =
      error.userMessage || error.message || '分析失败，请稍后重试'
    ElMessage.error(analysisError.value)
  } finally {
    if (runId === analysisRunId) clearStageTimers()
  }
}

const WORKSPACE_TOUR_STEPS = [
  {
    element: '#tour-workspace-upload',
    popover: {
      title: '上传 X 光片',
      description: '拖拽或点击此处上传患者的 X 光片。',
    },
  },
  {
    element: '#tour-workspace-clinical',
    popover: {
      title: '临床信息',
      description: '可在此补充患者临床特征，系统将进行多模态联合评估。',
    },
  },
  {
    element: '#tour-workspace-analyze',
    popover: {
      title: '开始分析',
      description: '点击开始，AI 将为您生成诊断概率和热力图。',
    },
  },
]

let removeTourListener = null

onBeforeUnmount(() => {
  clearStageTimers()
  releasePreviews()
  removeTourListener?.()
})

onMounted(() => {
  startPageTourOnce({
    storageKey: 'hasSeenTour_workspace',
    isDark: isDark.value,
    delay: 700,
    steps: WORKSPACE_TOUR_STEPS,
  })

  removeTourListener = onPageTourRequest(() => {
    startPageTour({
      storageKey: 'hasSeenTour_workspace',
      isDark: isDark.value,
      steps: WORKSPACE_TOUR_STEPS,
    })
  }, '/workspace')
})
</script>

<template>
  <main class="workspace-page">
    <PredictionResult
      v-if="result"
      :result="result"
      :preview-url="resultPreviewUrl || previewUrl"
      :preview-urls="previewUrls"
      :heatmap-url="result.heatmap_url || result.gradcam?.heatmap_url || ''"
      :clinical="clinicalSnapshot"
      @reset="resetWorkspace"
    />

    <template v-else>
      <header class="workspace-heading">
        <div>
          <p class="page-eyebrow">AI SCREENING WORKSPACE</p>
          <h1 class="page-title">肺炎 X 光片辅助筛查</h1>
          <p class="page-description">
            上传 1–3 张胸部 X 光片，系统将逐张输出 NORMAL / PNEUMONIA 二分类概率，
            并逐张生成模型关注区域。
          </p>
        </div>

        <div class="workspace-status">
          <span class="status-dot"></span>
          <div>
            <strong>模型服务在线</strong>
            <small>ResNet50 · Threshold 0.5101</small>
          </div>
        </div>
      </header>

      <div class="workspace-grid">
        <section id="tour-workspace-upload" class="upload-panel glass-panel">
          <div class="panel-heading">
            <div>
              <span class="panel-index">01</span>
              <h2>上传影像</h2>
            </div>
            <span class="panel-hint">JPG / PNG · 最多 {{ MAX_IMAGES }} 张 · 单张 ≤ 10 MB</span>
          </div>

          <input
            ref="fileInput"
            class="file-input"
            type="file"
            multiple
            accept=".jpg,.jpeg,.png,image/jpeg,image/png"
            @change="onFileInput"
          />

          <div
            v-if="!selectedFiles.length"
            class="dropzone"
            :class="{ 'is-dragging': dragging }"
            role="button"
            tabindex="0"
            aria-label="拖拽或点击上传 X 光片"
            @click="openFilePicker"
            @keydown.enter.prevent="openFilePicker"
            @keydown.space.prevent="openFilePicker"
            @dragenter.prevent="dragging = true"
            @dragover.prevent="dragging = true"
            @dragleave.prevent="dragging = false"
            @drop.prevent="onDrop"
          >
            <span class="dropzone__icon">
              <el-icon><UploadFilled /></el-icon>
            </span>
            <strong>拖拽 X 光片到这里</strong>
            <p>或点击选择本地影像，单次最多 {{ MAX_IMAGES }} 张</p>
            <div class="dropzone__formats">
              <span>JPG</span>
              <span>JPEG</span>
              <span>PNG</span>
              <span>最多 {{ MAX_IMAGES }} 张</span>
              <span>单张 ≤ 10 MB</span>
            </div>
          </div>

          <div v-else class="selected-preview">
            <div class="preview-frame">
              <div v-if="selectedFiles.length > 1" class="preview-multi">
                <div
                  v-for="(item, index) in selectedFiles"
                  :key="item.id"
                  class="preview-multi__item"
                >
                  <img :src="item.url" :alt="item.file.name" />
                  <span v-if="isAnalyzing" class="thumb-scanline"></span>
                  <span class="preview-multi__index">影像 {{ index + 1 }}</span>
                </div>
              </div>

              <img
                v-else
                :src="previewUrl"
                :alt="selectedFile?.name || '待分析 X 光片'"
              />

              <ScanningOverlay
                v-if="isAnalyzing && selectedFiles.length === 1"
                :stage="analysisStage"
              />

              <div
                v-if="isAnalyzing && selectedFiles.length > 1"
                class="multi-scan-status"
              >
                <span class="multi-scan-status__dot"></span>
                <div>
                  <strong>AI 正在逐张分析 {{ selectedFiles.length }} 张影像</strong>
                  <small>{{ stageLabel }}</small>
                </div>
              </div>

              <div v-if="analysisState === 'error'" class="analysis-error">
                <strong>分析未完成</strong>
                <span>{{ analysisError }}</span>
              </div>

              <span v-if="!isAnalyzing" class="preview-corner preview-corner--tl"></span>
              <span v-if="!isAnalyzing" class="preview-corner preview-corner--tr"></span>
              <span v-if="!isAnalyzing" class="preview-corner preview-corner--bl"></span>
              <span v-if="!isAnalyzing" class="preview-corner preview-corner--br"></span>
              <span class="preview-badge">
                {{ selectedFiles.length }} 张影像 · 逐张分析
              </span>
            </div>

            <div class="file-strip">
              <div class="file-strip__icon">
                <el-icon><Document /></el-icon>
              </div>
              <div class="file-strip__copy">
                <strong>{{ selectedFiles.length }} 张影像已就绪</strong>
                <small>{{ totalSizeText }} · 最多 {{ MAX_IMAGES }} 张</small>
              </div>
              <button
                v-if="selectedFiles.length < MAX_IMAGES"
                class="append-button"
                type="button"
                :disabled="isAnalyzing"
                @click="openFilePicker"
              >
                追加
              </button>
            </div>

            <div class="uploaded-grid">
              <figure
                v-for="(item, index) in selectedFiles"
                :key="item.id"
                class="uploaded-item"
                :class="{ 'is-primary': index === 0 }"
              >
                <img :src="item.url" :alt="item.file.name" />
                <span v-if="isAnalyzing" class="thumb-scanline"></span>
                <span class="uploaded-item__tag">
                  {{ index === 0 ? '主影像' : `影像 ${index + 1}` }}
                </span>
                <button
                  class="uploaded-item__remove"
                  type="button"
                  :disabled="isAnalyzing"
                  :aria-label="`移除 ${item.file.name}`"
                  @click="removeFile(index)"
                >
                  <el-icon><Delete /></el-icon>
                </button>
              </figure>

              <button
                v-if="selectedFiles.length < MAX_IMAGES"
                class="uploaded-add"
                type="button"
                :disabled="isAnalyzing"
                @click="openFilePicker"
              >
                <el-icon><UploadFilled /></el-icon>
                <span>追加影像</span>
                <small>{{ selectedFiles.length }}/{{ MAX_IMAGES }}</small>
              </button>
            </div>
          </div>

          <section id="tour-workspace-clinical" class="clinical-panel" aria-labelledby="clinical-panel-title">
            <div class="clinical-panel__notice">
              提示：当前每次上传的影像视为不同受检者。系统会为每张影像分别结合其临床信息进行独立分析，请逐位填写或留空各自的临床信息。
            </div>
            <div class="clinical-panel__header">
              <div>
                <span class="clinical-panel__eyebrow">MULTIMODAL LATE FUSION</span>
                <h3 id="clinical-panel-title">受检者临床信息</h3>
                <p>每张影像对应一位受检者，临床信息可留空，留空时仅使用该影像的模型结果。</p>
              </div>
              <span class="clinical-panel__badge">逐张影像 + 临床</span>
            </div>

            <div v-if="selectedFiles.length" class="patient-forms">
              <section
                v-for="(item, index) in selectedFiles"
                :key="item.id"
                class="patient-form"
              >
                <header class="patient-form__head">
                  <img :src="item.url" :alt="item.file.name" />
                  <div>
                    <strong>受检者 {{ index + 1 }}</strong>
                    <small :title="item.file.name">{{ item.file.name }}</small>
                  </div>
                  <span class="patient-form__tag">影像 {{ index + 1 }}</span>
                </header>

                <div class="clinical-grid">
                  <label class="clinical-field">
                    <span class="clinical-field__label">
                      <el-icon><User /></el-icon>
                      性别
                      <small>可选</small>
                    </span>
                    <el-select
                      v-model="item.clinical.gender"
                      placeholder="请选择"
                      clearable
                    >
                      <el-option label="男" value="MALE" />
                      <el-option label="女" value="FEMALE" />
                    </el-select>
                  </label>

                  <label class="clinical-field">
                    <span class="clinical-field__label">
                      <el-icon><User /></el-icon>
                      年龄
                      <small>岁</small>
                    </span>
                    <el-input
                      v-model="item.clinical.age"
                      type="number"
                      :min="0"
                      :max="120"
                      :step="1"
                      placeholder="如 68"
                      clearable
                      @input="clinicalValidationError = ''"
                      @blur="validateClinicalField(item.clinical, 'age', `影像 ${index + 1}：`)"
                    />
                  </label>

                  <label class="clinical-field">
                    <span class="clinical-field__label">
                      <el-icon><Sunny /></el-icon>
                      体温
                      <small>℃</small>
                    </span>
                    <el-input
                      v-model="item.clinical.temperature"
                      type="number"
                      :min="30"
                      :max="45"
                      :step="0.1"
                      placeholder="如 38.6"
                      clearable
                      @input="clinicalValidationError = ''"
                      @blur="validateClinicalField(item.clinical, 'temperature', `影像 ${index + 1}：`)"
                    />
                  </label>

                  <label class="clinical-field">
                    <span class="clinical-field__label">
                      <el-icon><Clock /></el-icon>
                      咳嗽天数
                      <small>天</small>
                    </span>
                    <el-input
                      v-model="item.clinical.cough_days"
                      type="number"
                      :min="0"
                      :max="365"
                      :step="1"
                      placeholder="如 5"
                      clearable
                      @input="clinicalValidationError = ''"
                      @blur="validateClinicalField(item.clinical, 'cough_days', `影像 ${index + 1}：`)"
                    />
                  </label>
                </div>
              </section>
            </div>

            <div v-else class="patient-forms__empty">
              请先上传影像，系统将为每张影像生成独立的受检者临床信息表单。
            </div>

            <div class="clinical-panel__footer">
              <span>每位受检者的临床信息均可留空；留空时仅使用对应影像的模型结果。</span>
              <span v-if="clinicalValidationError" class="clinical-panel__error" role="alert">
                {{ clinicalValidationError }}
              </span>
            </div>
          </section>

          <div id="tour-workspace-analyze" class="analysis-actions">
            <div class="analysis-actions__note">
              <el-icon><Picture /></el-icon>
              <span>影像仅在本地业务系统内处理</span>
            </div>
            <div class="analysis-buttons">
              <el-button
                type="primary"
                size="large"
                :icon="VideoPlay"
                :loading="isAnalyzing"
                :disabled="!canAnalyze"
                class="analyze-button"
                @click="startAnalysis"
              >
                {{ isAnalyzing ? stageLabel : '开始 AI 多模态分析' }}
              </el-button>
              <el-button
                size="large"
                :icon="RefreshLeft"
                class="reset-button"
                @click="resetWorkspace"
              >
                重置 / 取消
              </el-button>
            </div>
          </div>        </section>

        <aside class="workspace-aside">
          <section class="guide-panel glass-panel">
            <div class="panel-heading panel-heading--compact">
              <div>
                <span class="panel-index">02</span>
                <h2>分析流程</h2>
              </div>
            </div>

            <ol class="process-list">
              <li>
                <span>1</span>
                <div>
                  <strong>影像校验</strong>
                  <small>检查格式、大小与可解码性</small>
                </div>
              </li>
              <li>
                <span>2</span>
                <div>
                  <strong>ResNet50 推理</strong>
                  <small>输入 224×224，ONNX Runtime CPU 推理</small>
                </div>
              </li>
              <li>
                <span>3</span>
                <div>
                  <strong>临床晚期融合</strong>
                  <small>临床风险加权生成 final_prob</small>
                </div>
              </li>
              <li>
                <span>4</span>
                <div>
                  <strong>阈值判定</strong>
                  <small>联合概率 ≥ 0.5101 判为 PNEUMONIA</small>
                </div>
              </li>
              <li>
                <span>5</span>
                <div>
                  <strong>结果展示</strong>
                  <small>影像概率、联合风险与原图对比</small>
                </div>
              </li>
            </ol>
          </section>

          <section class="privacy-panel glass-panel">
            <span class="privacy-panel__icon">
              <el-icon><Aim /></el-icon>
            </span>
            <div>
              <strong>辅助筛查边界</strong>
              <p>
                系统只输出 NORMAL / PNEUMONIA 二分类参考，不解析 DICOM，
                不生成临床诊断或治疗建议。
              </p>
            </div>
          </section>
        </aside>
      </div>
    </template>
  </main>
</template>
<style scoped>
.workspace-page {
  width: 100%;
}

.workspace-heading {
  display: flex;
  gap: 28px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 22px;
}

.workspace-heading .page-description {
  max-width: 720px;
}

.workspace-status {
  display: flex;
  flex: 0 0 auto;
  gap: 10px;
  align-items: center;
  padding: 13px 16px;
  background: color-mix(in srgb, var(--success) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--success) 20%, transparent);
  border-radius: 12px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.workspace-status > div {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.workspace-status strong {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 650;
}

.workspace-status small {
  margin-top: 3px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 12px;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.7fr);
  gap: 18px;
  align-items: start;
}

.upload-panel {
  padding: clamp(20px, 2.5vw, 30px);
}

.panel-heading {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.panel-heading > div {
  display: flex;
  gap: 10px;
  align-items: center;
}

.panel-heading h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 20px;
  font-weight: 650;
}

.panel-index {
  color: var(--brand);
  font-family: var(--font-mono);
  font-size: 9px;
}

.panel-hint {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 13px;
}

.panel-heading--compact {
  margin-bottom: 18px;
}

.file-input {
  display: none;
}

.dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  justify-content: center;
  min-height: 250px;
  padding: 24px 30px;
  overflow: hidden;
  isolation: isolate;
  cursor: pointer;
  background:
    radial-gradient(circle at 50% 44%, color-mix(in srgb, var(--brand) 9%, transparent), transparent 42%),
    color-mix(in srgb, var(--bg-card) 62%, transparent);
  border: 1px dashed color-mix(in srgb, var(--brand) 28%, transparent);
  border-radius: 18px;
  outline: none;
  transition:
    background var(--transition-base),
    border-color var(--transition-base),
    transform var(--transition-base);
}

.dropzone::before {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 0;
  width: min(560px, 125%);
  aspect-ratio: 1;
  pointer-events: none;
  content: '';
  background: conic-gradient(
    from 0deg,
    transparent 0deg 252deg,
    color-mix(in srgb, var(--brand) 9%, transparent) 292deg,
    color-mix(in srgb, var(--brand) 18%, transparent) 326deg,
    transparent 360deg
  );
  border-radius: 50%;
  opacity: 0.62;
  transform: translate(-50%, -50%);
  animation: radar-sweep 8s linear infinite;
  mask-image: radial-gradient(circle, #000 0 58%, transparent 74%);
  -webkit-mask-image: radial-gradient(circle, #000 0 58%, transparent 74%);
}

.dropzone::after {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  content: '';
  background: linear-gradient(
    112deg,
    transparent 34%,
    color-mix(in srgb, var(--brand) 3%, transparent) 44%,
    color-mix(in srgb, var(--brand) 10%, transparent) 50%,
    color-mix(in srgb, var(--brand) 3%, transparent) 56%,
    transparent 66%
  );
  background-size: 240% 100%;
  opacity: 0.85;
  animation: upload-edge-flow 7s linear infinite;
}

.dropzone > * {
  position: relative;
  z-index: 2;
}

@keyframes radar-sweep {
  to {
    transform: translate(-50%, -50%) rotate(360deg);
  }
}

@keyframes upload-edge-flow {
  from {
    background-position: 180% 0;
  }

  to {
    background-position: -80% 0;
  }
}

.dropzone:hover,
.dropzone:focus-visible,
.dropzone.is-dragging {
  background:
    radial-gradient(circle at 50% 44%, color-mix(in srgb, var(--brand) 15%, transparent), transparent 45%),
    color-mix(in srgb, var(--bg-card) 76%, transparent);
  border-color: color-mix(in srgb, var(--brand) 52%, transparent);
  transform: translateY(-2px);
}

.dropzone__icon {
  display: grid;
  width: 62px;
  height: 62px;
  margin-bottom: 16px;
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 24%, transparent);
  border-radius: 18px;
  font-size: 26px;
  place-items: center;
  box-shadow:
    inset 0 0 25px color-mix(in srgb, var(--brand) 7%, transparent),
    0 0 30px color-mix(in srgb, var(--brand) 10%, transparent);
}

.dropzone strong {
  color: var(--text-primary);
  font-size: 20px;
  font-weight: 650;
}

.dropzone p {
  margin: 8px 0 16px;
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.6;
}

.dropzone__formats {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  justify-content: center;
}

.dropzone__formats span {
  padding: 4px 9px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 13px;
  background: color-mix(in srgb, var(--text-secondary) 8%, transparent);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-pill);
}
.selected-preview {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.preview-frame {
  position: relative;
  display: grid;
  min-height: 250px;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% 46%, color-mix(in srgb, var(--brand) 7%, transparent), transparent 50%),
    color-mix(in srgb, var(--bg-card) 82%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 18px;
  place-items: center;
}

.preview-frame > img {
  width: 100%;
  height: 100%;
  max-height: 620px;
  object-fit: contain;
}

.preview-multi {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
  width: 100%;
  height: 100%;
  padding: 12px;
}

.preview-multi__item {
  position: relative;
  min-height: 220px;
  overflow: hidden;
  background: color-mix(in srgb, var(--bg-card) 72%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.preview-multi__item img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.preview-multi__index {
  position: absolute;
  bottom: 8px;
  left: 8px;
  z-index: 2;
  padding: 4px 8px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 12px;
  background: color-mix(in srgb, var(--bg-card) 80%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 22%, transparent);
  border-radius: 6px;
}

.multi-scan-status {
  position: absolute;
  bottom: 18px;
  left: 50%;
  z-index: 6;
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: min(380px, calc(100% - 40px));
  padding: 14px 18px;
  color: var(--text-primary);
  background: color-mix(in srgb, var(--bg-card) 88%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 30%, transparent);
  border-radius: 13px;
  box-shadow: var(--shadow-pop);
  transform: translateX(-50%);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.multi-scan-status > div {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.multi-scan-status strong {
  font-size: 18px;
  font-weight: 700;
}

.multi-scan-status small {
  margin-top: 4px;
  color: var(--brand);
  font-size: 14px;
}

.multi-scan-status__dot {
  width: 10px;
  height: 10px;
  background: var(--brand);
  border-radius: 50%;
  box-shadow: 0 0 14px color-mix(in srgb, var(--brand) 85%, transparent);
  animation: scan-pulse 1.1s ease-in-out infinite;
}

@keyframes scan-pulse {
  0%,
  100% {
    opacity: 0.45;
    transform: scale(0.85);
  }

  50% {
    opacity: 1;
    transform: scale(1.2);
  }
}

.preview-corner {
  position: absolute;
  z-index: 2;
  width: 24px;
  height: 24px;
  border-color: color-mix(in srgb, var(--brand) 56%, transparent);
  border-style: solid;
}

.preview-corner--tl {
  top: 16px;
  left: 16px;
  border-width: 1px 0 0 1px;
}

.preview-corner--tr {
  top: 16px;
  right: 16px;
  border-width: 1px 1px 0 0;
}

.preview-corner--bl {
  bottom: 16px;
  left: 16px;
  border-width: 0 0 1px 1px;
}

.preview-corner--br {
  right: 16px;
  bottom: 16px;
  border-width: 0 1px 1px 0;
}

.analysis-error {
  position: absolute;
  right: 18px;
  bottom: 18px;
  left: 18px;
  z-index: 6;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  color: var(--danger);
  background: color-mix(in srgb, var(--bg-card) 88%, var(--danger));
  border: 1px solid color-mix(in srgb, var(--danger) 32%, transparent);
  border-radius: 11px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.analysis-error strong {
  font-size: 10px;
}

.analysis-error span {
  font-size: 9px;
  opacity: 0.82;
}
.file-strip {
  display: flex;
  gap: 11px;
  align-items: center;
  padding: 11px 12px;
  background: color-mix(in srgb, var(--text-primary) 3.5%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.file-strip__icon {
  display: grid;
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 10%, transparent);
  border-radius: 9px;
  place-items: center;
}

.file-strip__copy {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}

.file-strip__copy strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-strip__copy small {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 13px;
}

.preview-badge {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 3;
  padding: 5px 10px;
  color: var(--brand);
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 0.04em;
  background: color-mix(in srgb, var(--bg-card) 78%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 26%, transparent);
  border-radius: var(--radius-pill);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.append-button {
  flex: 0 0 auto;
  padding: 7px 13px;
  color: var(--brand);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  background: color-mix(in srgb, var(--brand) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 22%, transparent);
  border-radius: 8px;
  transition:
    background var(--transition-base),
    border-color var(--transition-base);
}

.append-button:hover:not(:disabled) {
  background: color-mix(in srgb, var(--brand) 18%, transparent);
  border-color: color-mix(in srgb, var(--brand) 40%, transparent);
}

.append-button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.uploaded-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  gap: 9px;
}

.uploaded-item {
  position: relative;
  aspect-ratio: 1;
  margin: 0;
  overflow: hidden;
  background: color-mix(in srgb, var(--bg-card) 70%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 11px;
}

.uploaded-item.is-primary {
  border-color: color-mix(in srgb, var(--brand) 46%, transparent);
  box-shadow: 0 0 16px color-mix(in srgb, var(--brand) 14%, transparent);
}

.uploaded-item img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb-scanline {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
  width: 100%;
  height: 3px;
  pointer-events: none;
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, var(--brand) 92%, white),
    transparent
  );
  box-shadow:
    0 0 10px color-mix(in srgb, var(--brand) 85%, transparent),
    0 0 24px color-mix(in srgb, var(--brand) 50%, transparent);
  animation: thumb-scan 1.7s linear infinite;
}

@keyframes thumb-scan {
  0% {
    top: 0;
    opacity: 0;
  }

  10% {
    opacity: 1;
  }

  90% {
    opacity: 1;
  }

  100% {
    top: calc(100% - 3px);
    opacity: 0;
  }
}

.uploaded-item__tag {
  position: absolute;
  bottom: 6px;
  left: 6px;
  padding: 3px 7px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 11px;
  background: color-mix(in srgb, var(--bg-card) 78%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 24%, transparent);
  border-radius: 5px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.uploaded-item__remove {
  position: absolute;
  top: 5px;
  right: 5px;
  display: grid;
  width: 22px;
  height: 22px;
  padding: 0;
  color: var(--text-primary);
  cursor: pointer;
  background: color-mix(in srgb, var(--bg-card) 84%, transparent);
  border: 1px solid color-mix(in srgb, var(--danger) 28%, transparent);
  border-radius: 7px;
  place-items: center;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.uploaded-item__remove:hover:not(:disabled) {
  color: var(--danger);
  background: color-mix(in srgb, var(--bg-card) 72%, var(--danger));
  border-color: color-mix(in srgb, var(--danger) 50%, transparent);
}

.uploaded-item__remove:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.uploaded-add {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  justify-content: center;
  aspect-ratio: 1;
  color: var(--text-tertiary);
  cursor: pointer;
  background:
    radial-gradient(circle at 50% 40%, color-mix(in srgb, var(--brand) 8%, transparent), transparent 62%),
    transparent;
  border: 1px dashed color-mix(in srgb, var(--brand) 28%, transparent);
  border-radius: 11px;
  transition:
    color var(--transition-base),
    background var(--transition-base),
    border-color var(--transition-base);
}

.uploaded-add .el-icon {
  color: var(--brand);
  font-size: 18px;
}

.uploaded-add span {
  font-size: 13px;
  font-weight: 600;
}

.uploaded-add small {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 11px;
}

.uploaded-add:hover:not(:disabled) {
  color: var(--text-secondary);
  background:
    radial-gradient(circle at 50% 40%, color-mix(in srgb, var(--brand) 15%, transparent), transparent 64%),
    transparent;
  border-color: color-mix(in srgb, var(--brand) 52%, transparent);
}

.uploaded-add:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.clinical-panel {
  position: relative;
  padding: 20px;
  margin-top: 18px;
  overflow: hidden;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--brand) 7%, transparent), transparent 48%),
    var(--surface-subtle);
  border: 1px solid var(--border-color);
  border-radius: 15px;
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--text-primary) 5%, transparent);
}

.clinical-panel__notice {
  position: relative;
  z-index: 1;
  padding: 12px 14px;
  margin-bottom: 16px;
  color: var(--warning-text);
  font-size: 15px;
  font-weight: 600;
  line-height: 1.6;
  background: var(--warning-bg);
  border: 1px solid color-mix(in srgb, var(--warning-text) 30%, transparent);
  border-radius: 10px;
}

.clinical-panel::after {
  position: absolute;
  top: -70px;
  right: -50px;
  width: 220px;
  height: 150px;
  pointer-events: none;
  content: '';
  background: radial-gradient(circle, color-mix(in srgb, var(--brand) 10%, transparent), transparent 68%);
}

.clinical-panel__header,
.clinical-panel__footer {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 18px;
  align-items: flex-start;
  justify-content: space-between;
}

.clinical-panel__header {
  padding-bottom: 15px;
  border-bottom: 1px solid var(--glass-border);
}

.clinical-panel__eyebrow {
  color: var(--brand);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
}

.clinical-panel__header h3 {
  margin: 6px 0 0;
  color: var(--text-primary);
  font-size: 20px;
  font-weight: 650;
}

.clinical-panel__header p {
  margin: 7px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.clinical-panel__badge {
  flex: 0 0 auto;
  padding: 6px 10px;
  color: var(--brand);
  font-family: var(--font-mono);
  font-size: 12px;
  background: color-mix(in srgb, var(--brand) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 20%, transparent);
  border-radius: var(--radius-pill);
}

.clinical-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 13px;
  padding-top: 15px;
}

.patient-forms {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}

.patient-form {
  padding: 15px;
  background: color-mix(in srgb, var(--text-primary) 3.5%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.patient-form__head {
  display: flex;
  gap: 12px;
  align-items: center;
  padding-bottom: 12px;
  margin-bottom: 2px;
  border-bottom: 1px solid var(--border-color);
}

.patient-form__head img {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.patient-form__head > div {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  line-height: 1.4;
}

.patient-form__head strong {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 650;
}

.patient-form__head small {
  overflow: hidden;
  margin-top: 3px;
  color: var(--text-tertiary);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.patient-form__tag {
  flex: 0 0 auto;
  padding: 4px 9px;
  color: var(--brand);
  font-family: var(--font-mono);
  font-size: 12px;
  background: color-mix(in srgb, var(--brand) 9%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 20%, transparent);
  border-radius: var(--radius-pill);
}

.patient-form .clinical-grid {
  padding-top: 12px;
}

.patient-forms__empty {
  position: relative;
  z-index: 1;
  padding: 24px;
  margin-top: 16px;
  color: var(--text-tertiary);
  font-size: 14px;
  line-height: 1.6;
  text-align: center;
  background: color-mix(in srgb, var(--text-primary) 3%, transparent);
  border: 1px dashed var(--border-color);
  border-radius: 12px;
}

.clinical-field {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.clinical-field__label {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-bottom: 8px;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}

.clinical-field__label .el-icon {
  color: var(--brand);
  font-size: 16px;
}

.clinical-field__label small {
  color: var(--text-tertiary);
  font-size: 13px;
  font-weight: 500;
}

.clinical-field :deep(.el-input__wrapper) {
  background: var(--surface-subtle);
  border-radius: 9px;
  box-shadow: 0 0 0 1px var(--glass-border) inset;
}

.clinical-field :deep(.el-select__wrapper) {
  background: var(--surface-subtle);
  border-radius: 9px;
  box-shadow: 0 0 0 1px var(--glass-border) inset;
}

.clinical-field :deep(.el-select__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--glass-border-hover) inset;
}

.clinical-field :deep(.el-select__wrapper.is-focused) {
  box-shadow:
    0 0 0 1px var(--color-primary-strong) inset,
    0 0 16px rgba(6, 182, 212, 0.09);
}

.clinical-field :deep(.el-select__placeholder),
.clinical-field :deep(.el-select__selected-item) {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 14px;
}

.clinical-field :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--glass-border-hover) inset;
}

.clinical-field :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1px var(--color-primary-strong) inset,
    0 0 16px rgba(6, 182, 212, 0.09);
}

.clinical-field :deep(.el-input__inner) {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 14px;
}

.clinical-field__range {
  margin-top: 6px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.clinical-panel__footer {
  align-items: center;
  padding-top: 14px;
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.5;
}

.clinical-panel__error {
  color: var(--color-danger);
  font-weight: 600;
}
.analysis-actions {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  padding-top: 18px;
}

.analysis-actions__note {
  display: flex;
  gap: 7px;
  align-items: center;
  color: var(--text-tertiary);
  font-size: 14px;
  line-height: 1.5;
}

.analysis-actions__note .el-icon {
  color: var(--brand);
}

.analysis-buttons {
  display: flex;
  flex: 0 0 auto;
  gap: 10px;
  align-items: center;
}

.analyze-button {
  min-width: 178px;
  background: linear-gradient(
    105deg,
    var(--brand),
    color-mix(in srgb, var(--brand) 58%, var(--bg-elevated))
  );
  border: 0;
  box-shadow: 0 10px 28px color-mix(in srgb, var(--brand) 22%, transparent);
}

.reset-button {
  min-width: 128px;
}
.workspace-aside {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.guide-panel {
  padding: 22px;
}

.process-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
  margin: 0;
  list-style: none;
}

.process-list li {
  position: relative;
  display: flex;
  gap: 13px;
  padding: 15px 0;
}

.process-list li:not(:last-child) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.process-list li > span {
  display: grid;
  flex: 0 0 auto;
  width: 27px;
  height: 27px;
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 9px;
  background: rgba(6, 182, 212, 0.07);
  border: 1px solid rgba(6, 182, 212, 0.15);
  border-radius: 8px;
  place-items: center;
}

.process-list li > div {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.process-list strong {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}

.process-list small {
  margin-top: 5px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.privacy-panel {
  display: flex;
  gap: 13px;
  padding: 18px;
  background: rgba(6, 182, 212, 0.035);
  border-color: rgba(6, 182, 212, 0.12);
}

.privacy-panel__icon {
  display: grid;
  flex: 0 0 auto;
  width: 35px;
  height: 35px;
  color: var(--color-primary-strong);
  background: rgba(6, 182, 212, 0.08);
  border-radius: 10px;
  place-items: center;
}

.privacy-panel strong {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}

.privacy-panel p {
  margin: 7px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

@media (max-width: 1120px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .workspace-aside {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 760px) {
  .workspace-heading {
    flex-direction: column;
  }

  .workspace-status {
    width: fit-content;
  }

  .workspace-aside {
    grid-template-columns: 1fr;
  }

  .dropzone,
  .preview-frame {
    min-height: 220px;
  }

  .clinical-grid {
    grid-template-columns: 1fr;
  }

  .clinical-panel__header,
  .clinical-panel__footer {
    flex-direction: column;
  }

  .analysis-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .analysis-buttons {
    flex-direction: column;
    width: 100%;
  }

  .analyze-button,
  .reset-button {
    width: 100%;
  }
}
</style>