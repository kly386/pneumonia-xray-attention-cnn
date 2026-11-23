<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  CircleCheckFilled,
  DataAnalysis,
  Refresh,
  TrendCharts,
  WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

import http from '@/api/http'
import { startPageTour, startPageTourOnce, onPageTourRequest } from '@/composables/usePageTour'
import { useTheme } from '@/composables/useTheme'

echarts.use([
  BarChart,
  PieChart,
  LineChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer,
])

const router = useRouter()
const { isDark } = useTheme()

const loading = ref(false)
const errorMessage = ref('')
const stats = ref(null)
const lastUpdated = ref('')
const pieRef = ref()
const lineRef = ref()
const ageRef = ref()
const genderRef = ref()
const perfRef = ref()

let pieChart = null
let lineChart = null
let ageChart = null
let genderChart = null
let perfChart = null

const GENDER_COLORS = {
  男性: 'var(--brand)',
  女性: 'var(--danger)',
  未填写: 'var(--text-tertiary)',
}

const PERF_METRIC_KEYS = ['latency', 'cpu', 'memory']
const AGE_GROUPS = ['0-18', '19-40', '41-65', '65+']
const AGE_MOCK = [
  { age_group: '0-18', normal: 46, pneumonia: 12 },
  { age_group: '19-40', normal: 88, pneumonia: 36 },
  { age_group: '41-65', normal: 64, pneumonia: 78 },
  { age_group: '65+', normal: 38, pneumonia: 112 },
]

const perfMetrics = reactive({
  latency: {
    label: '单张推理耗时',
    unit: 'ms',
    color: 'var(--brand)',
    decimals: 0,
    min: 42,
    max: 118,
    step: 12,
    target: 64,
    display: 64,
  },
  cpu: {
    label: 'CPU 占用率',
    unit: '%',
    color: 'var(--warning-text)',
    decimals: 1,
    min: 18,
    max: 82,
    step: 7,
    target: 34,
    display: 34,
  },
  memory: {
    label: '内存占用率',
    unit: '%',
    color: 'var(--text-tertiary)',
    decimals: 1,
    min: 44,
    max: 88,
    step: 4,
    target: 61,
    display: 61,
  },
})

const perfHistory = reactive({
  labels: [],
  latency: [],
  cpu: [],
  memory: [],
})

let perfTimer = 0
const metricFrames = {}
let perfTickCount = 0

const totalDiagnoses = computed(() => Number(stats.value?.total_diagnoses || 0))
const pneumoniaCount = computed(() => Number(stats.value?.pneumonia_count || 0))
const normalCount = computed(() => Number(stats.value?.normal_count || 0))
const pneumoniaRate = computed(() => Number(stats.value?.pneumonia_rate || 0))
const trend = computed(() => stats.value?.last_7_days || [])
const hasData = computed(() => totalDiagnoses.value > 0)

const ageDistribution = computed(() => stats.value?.age_distribution || [])
const genderDistribution = computed(() => stats.value?.gender_distribution || [])
const ageChartData = computed(() => {
  const rows = AGE_GROUPS.map((group) => {
    const source = ageDistribution.value.find(
      (item) => item.age_group === group,
    )
    return {
      age_group: group,
      normal: Number(source?.normal || 0),
      pneumonia: Number(source?.pneumonia || 0),
    }
  })

  const total = rows.reduce(
    (sum, item) => sum + item.normal + item.pneumonia,
    0,
  )
  return total > 0 ? rows : AGE_MOCK
})
const hasAgeData = computed(() =>
  ageChartData.value.some((item) => item.normal + item.pneumonia > 0),
)
const genderPieData = computed(() => {
  void isDark.value
  return genderDistribution.value
    .filter(
      (item) =>
        ['男性', '女性'].includes(item.gender) && item.pneumonia > 0,
    )
    .map((item) => ({
      name: item.gender,
      value: item.pneumonia,
      itemStyle: {
        color: resolveCssColor(GENDER_COLORS[item.gender], cssVar('--text-tertiary')),
      },
    }))
})
const hasGenderData = computed(() => genderPieData.value.length > 0)
const ageRecordTotal = computed(() =>
  ageChartData.value.reduce(
    (sum, item) => sum + item.normal + item.pneumonia,
    0,
  ),
)
const genderPneumoniaTotal = computed(() =>
  genderDistribution.value
    .filter((item) => ['男性', '女性'].includes(item.gender))
    .reduce((sum, item) => sum + item.pneumonia, 0),
)

function cssVar(name, fallback = '') {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim()
  return value || fallback
}

function resolveCssColor(value, fallback = '') {
  if (!value) return fallback
  if (!value.startsWith('var(')) return value
  const match = value.match(/^var\((--[^),\s]+)/)
  return match ? cssVar(match[1], fallback) : fallback
}

function withAlpha(color, alpha) {
  if (!color) return color
  if (color.startsWith('#')) {
    const hex = color.slice(1)
    const full = hex.length === 3
      ? hex.split('').map((char) => char + char).join('')
      : hex
    if (full.length === 6) {
      const red = Number.parseInt(full.slice(0, 2), 16)
      const green = Number.parseInt(full.slice(2, 4), 16)
      const blue = Number.parseInt(full.slice(4, 6), 16)
      return `rgba(${red}, ${green}, ${blue}, ${alpha})`
    }
  }
  const rgb = color.match(/rgba?\(([^)]+)\)/)
  if (rgb) {
    const [red, green, blue] = rgb[1].split(',').map((part) => part.trim())
    return `rgba(${red}, ${green}, ${blue}, ${alpha})`
  }
  return color
}

const chartPalette = computed(() => {
  void isDark.value
  return {
    text: cssVar('--text-secondary', '#475569'),
    axis: cssVar('--text-secondary', '#475569'),
    grid: cssVar('--border-color', 'rgba(100, 116, 139, 0.14)'),
    axisLine: cssVar('--border-strong', 'rgba(100, 116, 139, 0.22)'),
    border: cssVar('--bg-page', '#f4f8fc'),
    tooltipBg: cssVar('--bg-elevated', '#ffffff'),
    tooltipBorder: cssVar('--border-strong', 'rgba(15, 39, 66, 0.12)'),
    tooltipText: cssVar('--text-primary', '#0f2742'),
    brand: cssVar('--brand', '#0891b2'),
    success: cssVar('--success', '#16a34a'),
    danger: cssVar('--danger', '#dc2626'),
    warning: cssVar('--warning-text', '#92400e'),
    tertiary: cssVar('--text-tertiary', '#64748b'),
    track: cssVar('--border-strong', 'rgba(100, 116, 139, 0.22)'),
  }
})

const chartTextColor = computed(() => chartPalette.value.text)
const chartAxisColor = computed(() => chartPalette.value.axis)
const chartGridColor = computed(() => chartPalette.value.grid)
const chartAxisLineColor = computed(() => chartPalette.value.axisLine)
const pieBorderColor = computed(() => chartPalette.value.border)
const tooltipStyle = computed(() => ({
  backgroundColor: chartPalette.value.tooltipBg,
  borderColor: chartPalette.value.tooltipBorder,
  borderWidth: 1,
  textStyle: {
    color: chartPalette.value.tooltipText,
    fontSize: 14,
  },
}))

function formatRate(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`
}

function disposeCharts() {
  pieChart?.dispose()
  lineChart?.dispose()
  ageChart?.dispose()
  genderChart?.dispose()
  perfChart?.dispose()
  pieChart = null
  lineChart = null
  ageChart = null
  genderChart = null
  perfChart = null
}

function renderCharts() {
  if (!hasData.value) {
    disposeCharts()
    return
  }

  const palette = chartPalette.value

  if (pieRef.value) {
    pieChart?.dispose()
    pieChart = echarts.init(pieRef.value)
    pieChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        ...tooltipStyle.value,
        trigger: 'item',
        formatter: '{b}<br/>{c} 条（{d}%）',
      },
      legend: {
        bottom: 0,
        icon: 'circle',
        itemWidth: 8,
        itemHeight: 8,
        textStyle: {
          color: chartTextColor.value,
          fontSize: 14,
        },
      },
      series: [
        {
          type: 'pie',
          radius: ['76%', '80%'],
          center: ['50%', '44%'],
          silent: true,
          tooltip: { show: false },
          label: { show: false },
          data: [
            {
              value: 1,
              itemStyle: {
                color: palette.track,
              },
            },
          ],
          animation: false,
        },
        {
          name: '筛查结果',
          type: 'pie',
          radius: ['48%', '72%'],
          center: ['50%', '44%'],
          avoidLabelOverlap: true,
          itemStyle: {
            borderColor: pieBorderColor.value,
            borderWidth: 4,
            borderRadius: 4,
          },
          label: { show: false },
          emphasis: {
            scaleSize: 8,
            label: {
              show: true,
              color: palette.tooltipText,
              fontSize: 14,
              fontWeight: 600,
              formatter: '{b}\n{d}%',
            },
          },
          data: [
            {
              value: normalCount.value,
              name: 'NORMAL',
              itemStyle: { color: palette.success },
            },
            {
              value: pneumoniaCount.value,
              name: 'PNEUMONIA',
              itemStyle: { color: palette.danger },
            },
          ],
        },
      ],
      animationDuration: 800,
    }, true)
  }

  if (lineRef.value) {
    lineChart?.dispose()
    lineChart = echarts.init(lineRef.value)
    lineChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        ...tooltipStyle.value,
        trigger: 'axis',
      },
      legend: {
        top: 0,
        right: 0,
        icon: 'roundRect',
        itemWidth: 12,
        itemHeight: 3,
        textStyle: {
          color: chartTextColor.value,
          fontSize: 14,
        },
      },
      grid: {
        top: 40,
        right: 20,
        bottom: 40,
        left: 50,
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: trend.value.map((item) => item.date.slice(5)),
        axisLine: { lineStyle: { color: chartAxisLineColor.value } },
        axisTick: { show: false },
        axisLabel: { color: chartAxisColor.value, fontSize: 14 },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: chartAxisColor.value, fontSize: 14 },
        splitLine: {
          lineStyle: { color: chartGridColor.value },
        },
      },
      series: [
        {
          name: '总量',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: trend.value.map((item) => item.total),
          itemStyle: { color: palette.brand },
          lineStyle: {
            width: 1.5,
            color: palette.brand,
            type: 'dashed',
            opacity: 0.72,
          },
          z: 1,
        },
        {
          name: '正常',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          data: trend.value.map((item) => item.normal),
          itemStyle: { color: palette.success },
          lineStyle: { width: 2, color: palette.success },
          areaStyle: { color: withAlpha(palette.success, 0.08) },
        },
        {
          name: '肺炎',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          data: trend.value.map((item) => item.pneumonia),
          itemStyle: { color: palette.danger },
          lineStyle: { width: 2, color: palette.danger },
          areaStyle: { color: withAlpha(palette.danger, 0.08) },
        },
      ],
      animationDuration: 900,
    }, true)
  }
}

function renderPopulationCharts() {
  const palette = chartPalette.value

  if (ageRef.value) {
    ageChart?.dispose()
    ageChart = echarts.init(ageRef.value)
    ageChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        ...tooltipStyle.value,
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
      },
      legend: {
        top: 0,
        right: 0,
        icon: 'roundRect',
        itemWidth: 10,
        itemHeight: 6,
        textStyle: {
          color: chartTextColor.value,
          fontSize: 14,
        },
      },
      grid: {
        top: 48,
        right: 20,
        bottom: 36,
        left: 50,
      },
      xAxis: {
        type: 'category',
        data: ageChartData.value.map((item) => item.age_group),
        axisLine: { lineStyle: { color: chartAxisLineColor.value } },
        axisTick: { show: false },
        axisLabel: { color: chartAxisColor.value, fontSize: 14 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: chartAxisColor.value, fontSize: 14 },
        splitLine: { lineStyle: { color: chartGridColor.value } },
      },
      series: [
        {
          name: '阴性',
          type: 'bar',
          barWidth: 14,
          barGap: '18%',
          data: ageChartData.value.map((item) => item.normal),
          itemStyle: {
            borderRadius: [4, 4, 0, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: palette.success },
              { offset: 1, color: withAlpha(palette.success, 0.18) },
            ]),
          },
        },
        {
          name: '阳性',
          type: 'bar',
          barWidth: 14,
          data: ageChartData.value.map((item) => item.pneumonia),
          itemStyle: {
            borderRadius: [4, 4, 0, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: palette.danger },
              { offset: 1, color: withAlpha(palette.danger, 0.18) },
            ]),
          },
        },
      ],
      animationDuration: 900,
    }, true)
  }

  if (genderRef.value) {
    genderChart?.dispose()
    genderChart = echarts.init(genderRef.value)
    genderChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        ...tooltipStyle.value,
        trigger: 'item',
        formatter: '{b}<br/>{c} 人（{d}%）',
      },
      legend: {
        show: false,
      },
      series: [
        {
          name: '性别患病对比',
          type: 'pie',
          radius: ['48%', '70%'],
          center: ['50%', '52%'],
          itemStyle: {
            borderColor: pieBorderColor.value,
            borderWidth: 4,
            borderRadius: 6,
          },
          label: {
            color: chartTextColor.value,
            fontSize: 14,
            formatter: '{b}\n{d}%',
          },
          labelLine: {
            length: 12,
            length2: 10,
            lineStyle: { color: chartAxisLineColor.value },
          },
          emphasis: {
            scaleSize: 8,
            label: {
              show: true,
              color: palette.tooltipText,
              fontSize: 14,
              fontWeight: 600,
            },
          },
          data: genderPieData.value,
        },
      ],
      animationDuration: 900,
    }, true)
  }
}

function renderPerfChart() {
  if (!perfRef.value) return

  const palette = chartPalette.value
  const colorMap = {
    latency: palette.brand,
    cpu: palette.warning,
    memory: palette.tertiary,
  }

  perfChart?.dispose()
  perfChart = echarts.init(perfRef.value)
  perfChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      ...tooltipStyle.value,
      trigger: 'axis',
    },
    grid: {
      top: 36,
      right: 20,
      bottom: 34,
      left: 50,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: perfHistory.labels,
      axisLine: { lineStyle: { color: chartAxisLineColor.value } },
      axisTick: { show: false },
      axisLabel: { color: chartAxisColor.value, fontSize: 14, interval: 3 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 130,
      axisLabel: { color: chartAxisColor.value, fontSize: 14 },
      splitLine: { lineStyle: { color: chartGridColor.value } },
    },
    series: PERF_METRIC_KEYS.map((key) => ({
      name: perfMetrics[key].label,
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: perfHistory[key],
      lineStyle: {
        width: 1.8,
        color: colorMap[key],
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: withAlpha(colorMap[key], 0.2) },
          { offset: 1, color: withAlpha(colorMap[key], 0) },
        ]),
      },
    })),
    animationDuration: 500,
  }, true)
}

function updatePerfChart() {
  perfChart?.setOption({
    xAxis: { data: perfHistory.labels },
    series: PERF_METRIC_KEYS.map((key) => ({
      data: perfHistory[key],
    })),
  }, true)
}

function randomWalk(metric) {
  const delta = (Math.random() * 2 - 1) * metric.step
  return Math.min(metric.max, Math.max(metric.min, metric.target + delta))
}

function animateMetric(key) {
  const metric = perfMetrics[key]
  const from = metric.display
  const to = metric.target
  const startedAt = performance.now()
  const duration = 620

  cancelAnimationFrame(metricFrames[key])

  const tick = (now) => {
    const progress = Math.min((now - startedAt) / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)
    metric.display = from + (to - from) * eased

    if (progress < 1) {
      metricFrames[key] = requestAnimationFrame(tick)
    } else {
      metric.display = to
      metricFrames[key] = 0
    }
  }

  metricFrames[key] = requestAnimationFrame(tick)
}

function tickPerformance() {
  perfTickCount += 1
  const stamp = new Date()
  const label = new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(stamp)

  perfHistory.labels.push(label)
  if (perfHistory.labels.length > 24) perfHistory.labels.shift()

  for (const key of PERF_METRIC_KEYS) {
    const metric = perfMetrics[key]
    metric.target = randomWalk(metric)
    animateMetric(key)

    perfHistory[key].push(Number(metric.target.toFixed(metric.decimals)))
    if (perfHistory[key].length > 24) perfHistory[key].shift()
  }

  if (perfTickCount > 1) updatePerfChart()
}

function startPerformanceMonitor() {
  if (perfTimer) return

  tickPerformance()
  renderPerfChart()
  perfTimer = window.setInterval(tickPerformance, 1500)
}

function stopPerformanceMonitor() {
  if (perfTimer) {
    window.clearInterval(perfTimer)
    perfTimer = 0
  }
  Object.values(metricFrames).forEach((frame) => cancelAnimationFrame(frame))
}

function formatPerfValue(metric) {
  return metric.display.toFixed(metric.decimals)
}

function resizeCharts() {
  pieChart?.resize()
  lineChart?.resize()
  ageChart?.resize()
  genderChart?.resize()
  perfChart?.resize()
}

async function loadDashboard(showMessage = false) {
  loading.value = true
  errorMessage.value = ''

  try {
    const { data } = await http.get('/stats/dashboard')
    stats.value = data
    lastUpdated.value = new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(new Date())

    await nextTick()
    renderCharts()
    renderPopulationCharts()

    if (showMessage) ElMessage.success('看板数据已刷新')
  } catch (error) {
    errorMessage.value =
      error.userMessage || error.message || '统计数据加载失败，请稍后重试'
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function goWorkspace() {
  router.push('/workspace')
}

watch(
  () => isDark.value,
  async () => {
    await nextTick()
    renderCharts()
    renderPopulationCharts()
    renderPerfChart()
    resizeCharts()
  },
)

const DASHBOARD_TOUR_STEPS = [
  {
    element: '#tour-dashboard-kpi',
    popover: {
      title: '核心指标',
      description: '查看系统的总筛查数与阳性率概况。',
    },
  },
  {
    element: '#tour-dashboard-charts',
    popover: {
      title: '人群与趋势图表',
      description: '分析人群特征与近期的诊断趋势。',
    },
  },
]

let removeTourListener = null

onMounted(async () => {
  loadDashboard()
  window.addEventListener('resize', resizeCharts)

  await nextTick()
  renderPopulationCharts()
  startPerformanceMonitor()

  startPageTourOnce({
    storageKey: 'hasSeenTour_dashboard',
    isDark: isDark.value,
    delay: 800,
    steps: DASHBOARD_TOUR_STEPS,
  })

  removeTourListener = onPageTourRequest(() => {
    startPageTour({
      storageKey: 'hasSeenTour_dashboard',
      isDark: isDark.value,
      steps: DASHBOARD_TOUR_STEPS,
    })
  }, '/dashboard')
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  stopPerformanceMonitor()
  disposeCharts()
  removeTourListener?.()
})
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-heading">
      <div>
        <p class="page-eyebrow">DATA INSIGHT</p>
        <h1 class="page-title">筛查数据看板</h1>
        <p class="page-description">
          汇总当前医生的历史辅助筛查记录，展示阴阳性比例与最近 7 天诊断趋势。
        </p>
      </div>

      <div class="dashboard-actions">
        <span class="updated-at">最近更新：{{ lastUpdated || '—' }}</span>
        <el-button
          :icon="Refresh"
          :loading="loading"
          @click="loadDashboard(true)"
        >
          刷新数据
        </el-button>
      </div>
    </header>

    <div id="tour-dashboard-kpi" class="kpi-grid">
      <section class="kpi-card glass-panel">
        <span class="kpi-icon kpi-icon--cyan"><el-icon><DataAnalysis /></el-icon></span>
        <div>
          <span>总筛查数</span>
          <strong class="mono">{{ totalDiagnoses }}</strong>
          <small>当前账号全部记录</small>
        </div>
      </section>

      <section class="kpi-card glass-panel">
        <span class="kpi-icon kpi-icon--red"><el-icon><WarningFilled /></el-icon></span>
        <div>
          <span>肺炎记录</span>
          <strong class="mono kpi-value--danger">{{ pneumoniaCount }}</strong>
          <small>PNEUMONIA</small>
        </div>
      </section>

      <section class="kpi-card glass-panel">
        <span class="kpi-icon kpi-icon--green"><el-icon><CircleCheckFilled /></el-icon></span>
        <div>
          <span>正常记录</span>
          <strong class="mono kpi-value--success">{{ normalCount }}</strong>
          <small>NORMAL</small>
        </div>
      </section>

      <section class="kpi-card glass-panel">
        <span class="kpi-icon kpi-icon--blue"><el-icon><TrendCharts /></el-icon></span>
        <div>
          <span>肺炎占比</span>
          <strong class="mono">{{ formatRate(pneumoniaRate) }}</strong>
          <small>基于已保存记录</small>
        </div>
      </section>
    </div>

    <div v-if="errorMessage && !loading" class="dashboard-error">
      <span>{{ errorMessage }}</span>
      <el-button size="small" @click="loadDashboard()">重新加载</el-button>
    </div>

    <div v-if="loading && !stats" class="dashboard-skeleton">
      <div v-for="index in 2" :key="index" class="skeleton-card glass-panel"></div>
    </div>

    <div v-else-if="hasData" class="charts-grid">
      <section class="chart-card glass-panel">
        <header class="chart-header">
          <div>
            <p>RESULT DISTRIBUTION</p>
            <h2>阴阳性比例</h2>
          </div>
          <span>{{ totalDiagnoses }} 条记录</span>
        </header>
        <div ref="pieRef" class="chart-canvas"></div>
      </section>

      <section class="chart-card glass-panel">
        <header class="chart-header">
          <div>
            <p>7-DAY TREND</p>
            <h2>近 7 天诊断趋势</h2>
          </div>
          <span>按东八区自然日统计</span>
        </header>
        <div ref="lineRef" class="chart-canvas"></div>
      </section>
    </div>

    <section v-else-if="!loading && !errorMessage" class="dashboard-empty glass-panel">
      <span class="dashboard-empty__icon">
        <el-icon><DataAnalysis /></el-icon>
      </span>
      <strong>暂无统计数据</strong>
      <p>完成并保存第一条辅助筛查记录后，这里将展示分布和趋势。</p>
      <el-button type="primary" @click="goWorkspace">前往工作台</el-button>
    </section>

    <section id="tour-dashboard-charts" class="insight-section">
      <header class="section-heading">
        <div>
          <p class="page-eyebrow">POPULATION INSIGHT</p>
          <h2>人群特征分析</h2>
        </div>
        <span class="section-heading__badge">真实填写数据</span>
      </header>

      <div class="insight-grid">
        <section class="chart-card glass-panel">
          <header class="chart-header">
            <div>
              <p>AGE DISTRIBUTION</p>
              <h2>年龄段阴阳性分布</h2>
            </div>
            <span>{{ ageRecordTotal }} 人</span>
          </header>
          <div class="chart-stage">
            <div ref="ageRef" class="chart-canvas chart-canvas--compact"></div>
            <div v-if="!hasAgeData" class="chart-empty">
              暂未填写年龄信息
            </div>
          </div>
        </section>

        <section class="chart-card glass-panel">
          <header class="chart-header">
            <div>
              <p>GENDER COMPARISON</p>
              <h2>性别患病比例</h2>
            </div>
            <span>{{ genderPneumoniaTotal }} 例阳性</span>
          </header>
          <div class="chart-stage">
            <div ref="genderRef" class="chart-canvas chart-canvas--compact"></div>
            <div v-if="!hasGenderData" class="chart-empty">
              暂未填写性别信息
            </div>
          </div>
        </section>
      </div>
    </section>

    <section class="performance-panel glass-panel">
      <header class="performance-header">
        <div>
          <p class="page-eyebrow">SYSTEM MONITOR</p>
          <h2>系统性能实时监控</h2>
        </div>
        <span class="runtime-status">
          <span class="runtime-dot"></span>
          ONNX Runtime 运行中
        </span>
      </header>

      <div class="performance-body">
        <div class="perf-metrics">
          <article
            v-for="key in PERF_METRIC_KEYS"
            :key="key"
            class="perf-metric"
            :style="{ '--metric-color': perfMetrics[key].color }"
          >
            <span class="perf-metric__label">{{ perfMetrics[key].label }}</span>
            <strong class="perf-metric__value">
              {{ formatPerfValue(perfMetrics[key]) }}<small>{{ perfMetrics[key].unit }}</small>
            </strong>
            <span class="perf-metric__bar">
              <i
                :style="{
                  width: `${Math.min(Math.max(
                    (perfMetrics[key].display / perfMetrics[key].max) * 100,
                    4,
                  ), 100)}%`,
                }"
              ></i>
            </span>
          </article>
        </div>

        <div class="perf-chart-wrap">
          <div class="perf-chart-wrap__caption">
            <span>实时波动趋势</span>
            <small>每 1.5 秒刷新</small>
          </div>
          <div ref="perfRef" class="perf-chart"></div>
        </div>
      </div>
    </section>
  </main>
</template>
<style scoped>
.dashboard-page {
  width: 100%;
}

.dashboard-heading {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 22px;
}

.dashboard-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 12px;
  align-items: center;
}

.updated-at {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 13px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
  margin-bottom: 22px;
}

.kpi-card {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 20px;
}

.kpi-icon {
  display: grid;
  flex: 0 0 auto;
  width: 48px;
  height: 48px;
  border: 1px solid;
  border-radius: 14px;
  font-size: 22px;
  place-items: center;
}

.kpi-icon--cyan {
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 10%, transparent);
  border-color: color-mix(in srgb, var(--brand) 20%, transparent);
}

.kpi-icon--red {
  color: var(--danger);
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-color: color-mix(in srgb, var(--danger) 20%, transparent);
}

.kpi-icon--green {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 10%, transparent);
  border-color: color-mix(in srgb, var(--success) 20%, transparent);
}

.kpi-icon--blue {
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 10%, transparent);
  border-color: color-mix(in srgb, var(--brand) 20%, transparent);
}

.kpi-card > div {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}

.kpi-card span {
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.4;
}

.kpi-card strong {
  margin-top: 6px;
  color: var(--text-primary);
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
}

.kpi-card small {
  margin-top: 6px;
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.45;
}

.kpi-value--danger {
  color: var(--danger) !important;
}

.kpi-value--success {
  color: var(--success) !important;
}

.dashboard-error {
  display: flex;
  gap: 14px;
  align-items: center;
  justify-content: space-between;
  padding: 11px 14px;
  margin-bottom: 16px;
  color: var(--danger);
  font-size: 13px;
  background: color-mix(in srgb, var(--danger) 9%, transparent);
  border: 1px solid color-mix(in srgb, var(--danger) 24%, transparent);
  border-radius: 10px;
}
.charts-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.8fr) minmax(0, 1.2fr);
  gap: 18px;
}

.chart-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 320px;
  padding: 22px;
  background:
    radial-gradient(circle at 88% 8%, color-mix(in srgb, var(--brand) 6%, transparent), transparent 32%),
    var(--bg-card);
}

.chart-header {
  display: flex;
  flex: 0 0 auto;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.chart-header p {
  margin: 0 0 4px;
  color: var(--brand);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
}

.chart-header h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 20px;
  font-weight: 650;
}

.chart-header > span {
  color: var(--text-tertiary);
  font-size: 12px;
}

.chart-canvas {
  flex: 1;
  width: 100%;
  min-height: 0;
  height: 240px;
  margin-top: 8px;
}

.chart-canvas--compact {
  height: 240px;
}

.chart-stage {
  position: relative;
}

.chart-empty {
  position: absolute;
  inset: 0;
  display: grid;
  color: var(--text-tertiary);
  font-size: 13px;
  background: color-mix(in srgb, var(--bg-card) 40%, transparent);
  place-items: center;
  pointer-events: none;
}

.insight-section {
  margin-top: 22px;
}

.section-heading {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-heading h2 {
  margin: 4px 0 0;
  color: var(--text-primary);
  font-size: 20px;
  font-weight: 650;
}

.section-heading__badge {
  padding: 5px 10px;
  color: var(--brand);
  font-family: var(--font-mono);
  font-size: 12px;
  background: color-mix(in srgb, var(--brand) 9%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 20%, transparent);
  border-radius: var(--radius-pill);
}

.insight-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(300px, 0.85fr);
  gap: 18px;
}

.performance-panel {
  padding: 22px;
  margin-top: 18px;
  background:
    radial-gradient(circle at 92% 0%, color-mix(in srgb, var(--brand) 10%, transparent), transparent 34%),
    var(--bg-card);
}

.performance-header {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.performance-header h2 {
  margin: 4px 0 0;
  color: var(--text-primary);
  font-size: 20px;
  font-weight: 650;
}

.runtime-status {
  display: inline-flex;
  flex: 0 0 auto;
  gap: 8px;
  align-items: center;
  padding: 8px 13px;
  color: var(--success);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  background: color-mix(in srgb, var(--success) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--success) 24%, transparent);
  border-radius: var(--radius-pill);
}

.runtime-dot {
  width: 7px;
  height: 7px;
  background: var(--success);
  border-radius: 50%;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--success) 16%, transparent);
  animation: runtime-pulse 1.8s ease-in-out infinite;
}

.performance-body {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.4fr);
  gap: 18px;
  padding-top: 18px;
}

.perf-metrics {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.perf-metric {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 6px 16px;
  align-items: center;
  padding: 16px 18px;
  overflow: hidden;
  background: color-mix(in srgb, var(--text-primary) 4%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.perf-metric::after {
  position: absolute;
  top: 0;
  right: 0;
  width: 90px;
  height: 100%;
  pointer-events: none;
  content: '';
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--metric-color) 7%, transparent));
}

.perf-metric__label {
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.4;
}

.perf-metric__value {
  color: var(--metric-color);
  font-family: var(--font-mono);
  font-size: 32px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.03em;
  line-height: 1;
  text-shadow: 0 0 18px color-mix(in srgb, var(--metric-color) 46%, transparent);
}

.perf-metric__value small {
  margin-left: 4px;
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0;
}

.perf-metric__bar {
  grid-column: 1 / -1;
  height: 7px;
  margin-top: 6px;
  overflow: hidden;
  background: color-mix(in srgb, var(--text-secondary) 18%, transparent);
  border-radius: var(--radius-pill);
}

.perf-metric__bar i {
  display: block;
  height: 100%;
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--metric-color) 72%, transparent),
    var(--metric-color)
  );
  border-radius: inherit;
  box-shadow: 0 0 12px color-mix(in srgb, var(--metric-color) 52%, transparent);
  filter: saturate(1.15);
  transition: width 560ms cubic-bezier(0.22, 1, 0.36, 1);
}

.perf-chart-wrap {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 12px 14px 4px;
  background: color-mix(in srgb, var(--text-primary) 3%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 13px;
}

.perf-chart-wrap__caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px 4px;
}

.perf-chart-wrap__caption span {
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
}

.perf-chart-wrap__caption small {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 12px;
}

.perf-chart {
  width: 100%;
  height: 250px;
}

@keyframes runtime-pulse {
  0%,
  100% {
    opacity: 1;
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--success) 16%, transparent);
  }

  50% {
    opacity: 0.62;
    box-shadow: 0 0 0 6px color-mix(in srgb, var(--success) 4%, transparent);
  }
}

.dashboard-skeleton {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.skeleton-card {
  min-height: 430px;
  background:
    linear-gradient(
      100deg,
      color-mix(in srgb, var(--text-primary) 2%, transparent) 20%,
      color-mix(in srgb, var(--text-primary) 5%, transparent) 40%,
      color-mix(in srgb, var(--text-primary) 2%, transparent) 60%
    ),
    var(--bg-card);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.4s linear infinite;
}

.dashboard-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 430px;
  padding: 30px;
  text-align: center;
}

.dashboard-empty__icon {
  display: grid;
  width: 65px;
  height: 65px;
  margin-bottom: 17px;
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 18%, transparent);
  border-radius: 18px;
  font-size: 27px;
  place-items: center;
}

.dashboard-empty strong {
  color: var(--color-text-soft);
  font-size: 15px;
  font-weight: 600;
}

.dashboard-empty p {
  margin: 7px 0 20px;
  color: var(--color-text-faint);
  font-size: 10px;
}

@keyframes skeleton-shimmer {
  from {
    background-position: 200% 0;
  }

  to {
    background-position: -200% 0;
  }
}

@media (max-width: 1440px) {
  .chart-card,
  .performance-panel {
    padding: 18px;
  }

  .charts-grid,
  .insight-grid,
  .performance-body {
    gap: 14px;
  }
}

@media (max-width: 1150px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .charts-grid,
  .insight-grid,
  .performance-body {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .dashboard-heading {
    flex-direction: column;
  }

  .dashboard-actions {
    width: 100%;
    justify-content: space-between;
  }

  .kpi-grid,
  .dashboard-skeleton {
    grid-template-columns: 1fr;
  }

  .chart-canvas {
    height: 320px;
  }

  .chart-canvas--compact {
    height: 280px;
  }

  .section-heading,
  .performance-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .runtime-status {
    align-self: flex-start;
  }
}
</style>