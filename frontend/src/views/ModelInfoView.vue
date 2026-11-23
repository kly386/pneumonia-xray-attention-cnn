<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import {
  Aim,
  CircleCheckFilled,
  Cpu,
  DataAnalysis,
  TrendCharts,
  WarningFilled,
} from '@element-plus/icons-vue'

import {
  startPageTour,
  startPageTourOnce,
  onPageTourRequest,
} from '@/composables/usePageTour'
import { useTheme } from '@/composables/useTheme'
import {
  datasetFacts,
  e1Rows,
  e2Diagnosis,
  e2Rows,
  e3Rows,
  e7Rows,
  gradcamSamples,
  modelMetrics,
  trainingProtocol,
} from '@/data/modelInfo'

const { isDark } = useTheme()

const onlineFacts = [
  { label: '在线模型', value: 'resnet50_baseline' },
  { label: '部署格式', value: 'ONNX FP32' },
  { label: '输入形状', value: '[B, 3, 224, 224]' },
  { label: '输出', value: '2 类 logits + Softmax' },
  { label: '类别顺序', value: 'NORMAL / PNEUMONIA' },
  { label: '判定阈值', value: '0.5101' },
]

const sections = [
  { id: 'overview', label: '在线模型' },
  { id: 'method', label: '方法概览' },
  { id: 'e1', label: 'E1 骨干对比' },
  { id: 'e2', label: 'E2 注意力消融' },
  { id: 'e3', label: 'E3 数据增强' },
  { id: 'e7', label: 'E7 部署量化' },
  { id: 'gradcam', label: 'Grad-CAM' },
]

function pct(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`
}

function selectedRow({ row }) {
  return row.selected ? 'selected-row' : ''
}

const MODEL_TOUR_STEPS = [
  {
    element: '#tour-model-hero',
    popover: {
      title: '模型概览',
      description: '查看在线模型版本、部署格式和核心测试指标。',
    },
  },
  {
    element: '#tour-model-nav',
    popover: {
      title: '章节导航',
      description: '通过章节导航快速跳转到骨干对比、注意力消融、增强和量化实验。',
    },
  },
  {
    element: '#overview',
    popover: {
      title: '指标与实验结论',
      description: '查看 Accuracy、AUC、Recall 等指标，以及最终模型选择依据。',
    },
  },
]

let removeTourListener = null

onMounted(() => {
  startPageTourOnce({
    storageKey: 'hasSeenTour_model_info',
    isDark: isDark.value,
    delay: 700,
    steps: MODEL_TOUR_STEPS,
  })

  removeTourListener = onPageTourRequest(() => {
    startPageTour({
      storageKey: 'hasSeenTour_model_info',
      isDark: isDark.value,
      steps: MODEL_TOUR_STEPS,
    })
  }, '/model-info')
})

onBeforeUnmount(() => {
  removeTourListener?.()
})
</script>

<template>
  <main class="model-page">
    <header id="tour-model-hero" class="model-hero glass-panel">
      <div class="hero-copy">
        <p class="page-eyebrow">MODEL EXPLAINER · EXPERIMENT SNAPSHOT</p>
        <h1 class="page-title">模型信息与实验证据</h1>
        <p class="page-description">
          从骨干对比、注意力消融、数据增强到 ONNX 部署量化，完整呈现最终模型选型依据。
          项目名称保留“注意力机制增强 CNN”，但在线模型如实采用实验最优的无注意力基线。
        </p>
        <div class="hero-badges">
          <span class="hero-badge">
            <el-icon><CircleCheckFilled /></el-icon>
            测试集 Acc 97.43%
          </span>
          <span class="hero-badge">
            <el-icon><TrendCharts /></el-icon>
            AUC 99.46%
          </span>
          <span class="hero-badge hero-badge--warning">
            <el-icon><WarningFilled /></el-icon>
            E2 负结果保留
          </span>
        </div>
      </div>

      <div class="model-orbit">
        <span class="model-orbit__ring model-orbit__ring--outer"></span>
        <span class="model-orbit__ring model-orbit__ring--inner"></span>
        <span class="model-orbit__core">
          <el-icon><Cpu /></el-icon>
        </span>
        <div class="model-orbit__label">
          <span>ONLINE MODEL</span>
          <strong>ResNet50</strong>
          <small>baseline · ONNX FP32</small>
        </div>
      </div>
    </header>

    <nav id="tour-model-nav" class="model-nav glass-panel" aria-label="模型信息章节导航">
      <a v-for="section in sections" :key="section.id" :href="`#${section.id}`">
        {{ section.label }}
      </a>
      <span class="model-nav__version">exp-2026-11-10</span>
    </nav>

    <section id="overview" class="model-section">
      <header class="section-heading">
        <div>
          <p class="page-eyebrow">01 / DEPLOYED MODEL</p>
          <h2>在线模型概览</h2>
        </div>
        <p>测试集一次性评估口径</p>
      </header>

      <div class="metric-grid">
        <article v-for="(metric, index) in modelMetrics" :key="metric.label" class="metric-card glass-panel">
          <span class="metric-card__index">0{{ index + 1 }}</span>
          <span class="metric-card__label">{{ metric.label }}</span>
          <strong>{{ metric.display }}</strong>
          <small>{{ metric.caption }}</small>
        </article>
      </div>

      <div class="overview-grid">
        <section class="spec-card glass-panel">
          <div class="card-title">
            <el-icon><Cpu /></el-icon>
            <h3>部署事实</h3>
          </div>
          <dl class="spec-list">
            <div v-for="fact in onlineFacts" :key="fact.label">
              <dt>{{ fact.label }}</dt>
              <dd>{{ fact.value }}</dd>
            </div>
          </dl>
        </section>

        <article class="decision-card glass-panel">
          <span class="decision-card__icon"><el-icon><Aim /></el-icon></span>
          <div>
            <p class="page-eyebrow">FINAL DECISION</p>
            <h3>最终采用无注意力基线</h3>
            <p>
              E2 中 SE/CBAM 的所有变体均未在综合指标上超过基线；在医学场景重点关注的
              PNEUMONIA Recall 上，基线漏诊 8 例，少于所有注意力变体。
            </p>
            <strong>不为名称强行叠加注意力模块，选型以实验证据为准。</strong>
          </div>
        </article>
      </div>
    </section>

    <section id="method" class="model-section">
      <header class="section-heading">
        <div>
          <p class="page-eyebrow">02 / METHODOLOGY</p>
          <h2>数据与训练策略</h2>
        </div>
        <p>固定协议、固定 seed、测试集只评一次</p>
      </header>

      <div class="method-grid">
        <section class="method-card glass-panel">
          <div class="card-title">
            <el-icon><DataAnalysis /></el-icon>
            <h3>数据口径</h3>
          </div>
          <dl class="fact-list">
            <div v-for="fact in datasetFacts" :key="fact.label">
              <dt>{{ fact.label }}</dt>
              <dd>{{ fact.value }}</dd>
            </div>
          </dl>
        </section>

        <section class="method-card glass-panel">
          <div class="card-title">
            <el-icon><TrendCharts /></el-icon>
            <h3>训练协议</h3>
          </div>
          <div class="protocol-grid">
            <div v-for="item in trainingProtocol" :key="item.title">
              <span>{{ item.title }}</span>
              <strong>{{ item.value }}</strong>
              <small>{{ item.detail }}</small>
            </div>
          </div>
        </section>
      </div>
    </section>

    <section id="e1" class="model-section">
      <header class="section-heading">
        <div>
          <p class="page-eyebrow">03 / E1 BACKBONE COMPARISON</p>
          <h2>骨干网络对比</h2>
        </div>
        <p>单变量：只更换骨干网络</p>
      </header>

      <section class="table-card glass-panel">
        <el-table :data="e1Rows" :row-class-name="selectedRow" class="model-table">
          <el-table-column label="骨干网络" min-width="210">
            <template #default="{ row }">
              <span class="table-primary">{{ row.backbone }}</span>
              <span v-if="row.selected" class="selected-mark">SELECTED</span>
            </template>
          </el-table-column>
          <el-table-column label="Test Acc" width="120">
            <template #default="{ row }"><span class="mono">{{ pct(row.acc) }}</span></template>
          </el-table-column>
          <el-table-column label="Test F1" width="120">
            <template #default="{ row }"><span class="mono">{{ pct(row.f1) }}</span></template>
          </el-table-column>
          <el-table-column label="Test AUC" width="120">
            <template #default="{ row }"><span class="mono">{{ pct(row.auc) }}</span></template>
          </el-table-column>
          <el-table-column label="PNEUMONIA Recall" width="165">
            <template #default="{ row }"><span class="mono">{{ pct(row.positiveRecall) }}</span></template>
          </el-table-column>
          <el-table-column label="NORMAL Recall" width="150">
            <template #default="{ row }"><span class="mono">{{ pct(row.normalRecall) }}</span></template>
          </el-table-column>
        </el-table>
        <p class="table-note">
          结论：ResNet50 的 Test F1 与 AUC 均为最高；ImageNet1K_V2 预训练与大容量骨干在有限数据上表现更稳定。
        </p>
      </section>
    </section>

    <section id="e2" class="model-section">
      <header class="section-heading">
        <div>
          <p class="page-eyebrow">04 / E2 ATTENTION ABLATION</p>
          <h2>注意力消融：一个完整负结果</h2>
        </div>
        <p>SE / CBAM 逐步修复，仍未超过基线</p>
      </header>

      <article class="negative-callout glass-panel">
        <span class="negative-callout__icon"><el-icon><WarningFilled /></el-icon></span>
        <div>
          <strong>实验结论：注意力没有带来增益</strong>
          <p>
            三轮单变量实验（朴素插入 → 恒等初始化 → 注意力低学习率）均未超过无注意力基线。
            这不是实验失败，而是最终选型的重要证据。
          </p>
        </div>
      </article>

      <section class="table-card glass-panel">
        <el-table :data="e2Rows" :row-class-name="selectedRow" class="model-table">
          <el-table-column label="变体" min-width="225">
            <template #default="{ row }">
              <span class="table-primary">{{ row.variant }}</span>
              <span v-if="row.selected" class="selected-mark">SELECTED</span>
            </template>
          </el-table-column>
          <el-table-column label="最佳 Val F1" width="135">
            <template #default="{ row }"><span class="mono">{{ row.valF1.toFixed(4) }}</span></template>
          </el-table-column>
          <el-table-column label="Test Acc" width="115">
            <template #default="{ row }"><span class="mono">{{ pct(row.acc) }}</span></template>
          </el-table-column>
          <el-table-column label="Test F1" width="115">
            <template #default="{ row }"><span class="mono">{{ pct(row.f1) }}</span></template>
          </el-table-column>
          <el-table-column label="Test AUC" width="115">
            <template #default="{ row }"><span class="mono">{{ pct(row.auc) }}</span></template>
          </el-table-column>
          <el-table-column label="PNEUMONIA Recall" width="165">
            <template #default="{ row }"><span class="mono">{{ pct(row.positiveRecall) }}</span></template>
          </el-table-column>
        </el-table>
        <p class="table-note">
          基线（无注意力）PNEUMONIA Recall 为 98.12%，漏诊 8 例；所有注意力变体漏诊均更多。
        </p>
      </section>

      <div class="diagnosis-grid">
        <article v-for="item in e2Diagnosis" :key="item.step" class="diagnosis-card glass-panel">
          <span>{{ item.step }}</span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.description }}</p>
        </article>
      </div>

      <div class="e2-decision">
        <strong>最终决策：</strong>
        <span>
          <code>resnet50_baseline.pt</code> 为 E2 最佳模型并冻结交付；在线系统使用
          <code>resnet50_baseline</code>，不宣称使用 SE/CBAM 注意力增强。
        </span>
      </div>
    </section>

    <section id="e3" class="model-section">
      <header class="section-heading">
        <div>
          <p class="page-eyebrow">05 / E3 AUGMENTATION ABLATION</p>
          <h2>数据增强消融</h2>
        </div>
        <p>单变量：只改变训练增强策略</p>
      </header>

      <section class="table-card glass-panel">
        <el-table :data="e3Rows" :row-class-name="selectedRow" class="model-table">
          <el-table-column label="增强变体" min-width="210">
            <template #default="{ row }">
              <span class="table-primary">{{ row.variant }}</span>
              <span v-if="row.selected" class="selected-mark">SELECTED</span>
            </template>
          </el-table-column>
          <el-table-column label="Test Acc" width="120">
            <template #default="{ row }"><span class="mono">{{ pct(row.acc) }}</span></template>
          </el-table-column>
          <el-table-column label="Test F1" width="120">
            <template #default="{ row }"><span class="mono">{{ pct(row.f1) }}</span></template>
          </el-table-column>
          <el-table-column label="Test AUC" width="120">
            <template #default="{ row }"><span class="mono">{{ pct(row.auc) }}</span></template>
          </el-table-column>
          <el-table-column label="PNEUMONIA Recall" width="165">
            <template #default="{ row }"><span class="mono">{{ pct(row.positiveRecall) }}</span></template>
          </el-table-column>
        </el-table>
        <p class="table-note">
          去掉全部增强后 Test F1 从 0.9675 降至 0.9017；任何单项增强子集均无法追平全量组合。
        </p>
      </section>
    </section>

    <section id="e7" class="model-section">
      <header class="section-heading">
        <div>
          <p class="page-eyebrow">06 / E7 DEPLOYMENT</p>
          <h2>ONNX 部署与量化</h2>
        </div>
        <p>本机 CPU · batch 1 · 50 次平均</p>
      </header>

      <section class="table-card glass-panel">
        <el-table :data="e7Rows" :row-class-name="selectedRow" class="model-table">
          <el-table-column label="形态" min-width="180">
            <template #default="{ row }">
              <span class="table-primary">{{ row.format }}</span>
              <span v-if="row.selected" class="selected-mark">ONLINE</span>
            </template>
          </el-table-column>
          <el-table-column label="体积" width="100">
            <template #default="{ row }"><span class="mono">{{ row.size }}</span></template>
          </el-table-column>
          <el-table-column label="CPU 时延" width="120">
            <template #default="{ row }"><span class="mono">{{ row.latency }}</span></template>
          </el-table-column>
          <el-table-column label="Val Acc" width="105">
            <template #default="{ row }"><span class="mono">{{ pct(row.valAcc) }}</span></template>
          </el-table-column>
          <el-table-column label="Val F1" width="105">
            <template #default="{ row }"><span class="mono">{{ pct(row.valF1) }}</span></template>
          </el-table-column>
          <el-table-column label="Val AUC" width="105">
            <template #default="{ row }"><span class="mono">{{ pct(row.valAuc) }}</span></template>
          </el-table-column>
          <el-table-column label="用途" min-width="150">
            <template #default="{ row }">{{ row.note }}</template>
          </el-table-column>
        </el-table>
        <p class="table-note">
          FP32 ONNX 与 PyTorch 精度一致，CPU 时延约 28.3 ms；静态 INT8 体积缩小 4 倍，PNEUMONIA Recall 不变。
          以上为本机实验数据，不作为所有部署环境的生产 SLA。
        </p>
      </section>
    </section>

    <section id="gradcam" class="model-section">
      <header class="section-heading">
        <div>
          <p class="page-eyebrow">07 / EXPLAINABILITY</p>
          <h2>Grad-CAM 样例</h2>
        </div>
        <p>三联图：原图 / Jet 热力 / 叠加</p>
      </header>

      <div class="gradcam-grid">
        <article v-for="sample in gradcamSamples" :key="sample.label" class="gradcam-card glass-panel">
          <header>
            <div>
              <span :class="['sample-label', `is-${sample.tone}`]">{{ sample.label }}</span>
              <h3>{{ sample.title }}</h3>
            </div>
            <el-icon><Aim /></el-icon>
          </header>
          <el-image
            class="sample-image"
            :src="sample.image"
            :preview-src-list="[sample.image]"
            preview-teleported
            :alt="`${sample.title} 的 Grad-CAM 三联图`"
            fit="cover"
          />
          <p>{{ sample.description }}</p>
        </article>
      </div>

      <div class="gradcam-boundary">
        <el-icon><WarningFilled /></el-icon>
        <span>Grad-CAM 仅展示模型关注区域，不代表病灶边界，也不构成临床诊断依据。</span>
      </div>
    </section>

    <footer class="model-footer">
      <span>实验快照：exp-2026-11-10</span>
      <span>数据来源：项目 reports/ 实验报告</span>
      <span>在线模型：resnet50_baseline · ONNX FP32</span>
    </footer>
  </main>
</template>
<style scoped>
.model-page {
  width: 100%;
}

.model-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
  gap: 30px;
  align-items: center;
  min-height: 330px;
  padding: clamp(28px, 4vw, 48px);
  overflow: hidden;
}

.model-hero::before {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background:
    radial-gradient(circle at 88% 42%, rgba(6, 182, 212, 0.14), transparent 32%),
    linear-gradient(135deg, rgba(6, 182, 212, 0.03), transparent 50%);
}

.hero-copy {
  position: relative;
  z-index: 1;
}

.hero-copy .page-description {
  max-width: 760px;
}

.hero-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  margin-top: 24px;
}

.hero-badge {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  padding: 7px 10px;
  color: var(--color-text-soft);
  font-size: 9px;
  background: rgba(6, 182, 212, 0.06);
  border: 1px solid rgba(6, 182, 212, 0.14);
  border-radius: var(--radius-pill);
}

.hero-badge .el-icon {
  color: var(--color-primary-strong);
}

.hero-badge--warning {
  color: var(--warning-text);
  background: var(--warning-bg);
  border-color: color-mix(in srgb, var(--warning-text) 30%, transparent);
}

.hero-badge--warning .el-icon {
  color: var(--warning-text);
}

.model-orbit {
  position: relative;
  display: grid;
  min-height: 250px;
  place-items: center;
}

.model-orbit__ring {
  position: absolute;
  border: 1px solid rgba(34, 211, 238, 0.16);
  border-radius: 50%;
}

.model-orbit__ring--outer {
  width: 230px;
  height: 230px;
  border-style: dashed;
  animation: orbit-spin 24s linear infinite;
}

.model-orbit__ring--inner {
  width: 170px;
  height: 170px;
  border-color: rgba(59, 130, 246, 0.2);
  box-shadow:
    0 0 40px rgba(6, 182, 212, 0.07),
    inset 0 0 30px rgba(6, 182, 212, 0.04);
}

.model-orbit__core {
  position: relative;
  z-index: 2;
  display: grid;
  width: 72px;
  height: 72px;
  color: var(--color-primary-strong);
  font-size: 32px;
  background: rgba(6, 182, 212, 0.09);
  border: 1px solid rgba(34, 211, 238, 0.28);
  border-radius: 22px;
  place-items: center;
  box-shadow: 0 0 35px rgba(6, 182, 212, 0.15);
}

.model-orbit__label {
  position: absolute;
  bottom: -2px;
  left: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1.25;
  transform: translateX(-50%);
}

.model-orbit__label span {
  color: var(--color-text-faint);
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.12em;
}

.model-orbit__label strong {
  margin-top: 5px;
  color: var(--color-text);
  font-size: 18px;
}

.model-orbit__label small {
  margin-top: 3px;
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 9px;
}

.model-nav {
  position: sticky;
  top: 12px;
  z-index: 10;
  display: flex;
  gap: 7px;
  align-items: center;
  padding: 9px 12px;
  margin: 16px 0 26px;
  overflow-x: auto;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-pill);
}

.model-nav a {
  flex: 0 0 auto;
  padding: 7px 11px;
  color: var(--color-text-muted);
  font-size: 9px;
  border-radius: var(--radius-pill);
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.model-nav a:hover {
  color: var(--color-primary-strong);
  background: rgba(6, 182, 212, 0.08);
}

.model-nav__version {
  flex: 0 0 auto;
  padding-left: 8px;
  margin-left: auto;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 8px;
  border-left: 1px solid var(--border-color);
}

.model-section {
  padding: 12px 0 38px;
  scroll-margin-top: 76px;
}

.section-heading {
  display: flex;
  gap: 20px;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 18px;
}

.section-heading h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 20px;
  letter-spacing: -0.02em;
}

.section-heading > p {
  margin: 0;
  color: var(--color-text-faint);
  font-size: 9px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.metric-card {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}

.metric-card::after {
  position: absolute;
  top: -30px;
  right: -25px;
  width: 110px;
  height: 110px;
  content: '';
  background: radial-gradient(circle, rgba(6, 182, 212, 0.12), transparent 68%);
}

.metric-card__index {
  color: var(--color-text-faint);
  font-family: var(--font-mono);
  font-size: 8px;
}

.metric-card__label {
  margin-top: 14px;
  color: var(--color-text-muted);
  font-size: 9px;
}

.metric-card strong {
  margin-top: 6px;
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: clamp(24px, 2.4vw, 34px);
  line-height: 1;
}

.metric-card small {
  margin-top: 8px;
  color: var(--color-text-faint);
  font-size: 8px;
}

@keyframes orbit-spin {
  to {
    transform: rotate(360deg);
  }
}
.overview-grid,
.method-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}

.spec-card,
.method-card {
  padding: 22px;
}

.card-title {
  display: flex;
  gap: 9px;
  align-items: center;
  padding-bottom: 15px;
  margin-bottom: 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.card-title .el-icon {
  color: var(--color-primary-strong);
}

.card-title h3 {
  margin: 0;
  color: var(--color-text-soft);
  font-size: 13px;
  font-weight: 650;
}

.spec-list,
.fact-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
  margin: 0;
}

.spec-list > div,
.fact-list > div {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 11px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.055);
  border-radius: 10px;
}

.spec-list dt,
.fact-list dt {
  color: var(--color-text-faint);
  font-size: 8px;
}

.spec-list dd,
.fact-list dd {
  margin: 5px 0 0;
  color: var(--color-text-soft);
  font-family: var(--font-mono);
  font-size: 9px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.decision-card {
  display: flex;
  gap: 17px;
  align-items: flex-start;
  padding: 25px;
  background:
    radial-gradient(circle at 90% 10%, rgba(245, 158, 11, 0.08), transparent 36%),
    var(--glass-bg);
  border-color: rgba(245, 158, 11, 0.14);
}

.decision-card__icon {
  display: grid;
  flex: 0 0 auto;
  width: 49px;
  height: 49px;
  color: var(--color-warning);
  background: rgba(245, 158, 11, 0.07);
  border: 1px solid rgba(245, 158, 11, 0.16);
  border-radius: 14px;
  font-size: 22px;
  place-items: center;
}

.decision-card h3 {
  margin: 2px 0 0;
  color: var(--color-text);
  font-size: 20px;
  font-weight: 650;
}

.decision-card p:not(.page-eyebrow) {
  margin: 10px 0;
  color: var(--color-text-muted);
  font-size: 11px;
  line-height: 1.8;
}

.decision-card strong {
  color: var(--warning-text);
  font-size: 13px;
  font-weight: 500;
}

.protocol-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
}

.protocol-grid > div {
  display: flex;
  flex-direction: column;
  padding: 11px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.055);
  border-radius: 10px;
}

.protocol-grid span {
  color: var(--color-text-faint);
  font-size: 8px;
}

.protocol-grid strong {
  margin-top: 4px;
  color: var(--color-text-soft);
  font-size: 10px;
  font-weight: 600;
}

.protocol-grid small {
  margin-top: 4px;
  color: var(--color-text-faint);
  font-size: 8px;
  line-height: 1.5;
}
.table-card {
  padding: 18px;
  overflow: hidden;
}

.model-table {
  width: 100%;
}

.model-table :deep(.selected-row > td.el-table__cell) {
  background: rgba(6, 182, 212, 0.075) !important;
}

.model-table :deep(.selected-row > td.el-table__cell:first-child) {
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.table-primary {
  color: var(--color-text-soft);
  font-size: 10px;
  font-weight: 600;
}

.selected-mark {
  display: inline-flex;
  padding: 2px 6px;
  margin-left: 8px;
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 7px;
  background: rgba(6, 182, 212, 0.08);
  border: 1px solid rgba(6, 182, 212, 0.16);
  border-radius: var(--radius-pill);
}

.table-note {
  margin: 15px 0 0;
  color: var(--color-text-faint);
  font-size: 9px;
  line-height: 1.7;
}

.negative-callout {
  display: flex;
  gap: 15px;
  align-items: flex-start;
  padding: 19px;
  margin-bottom: 16px;
  background:
    radial-gradient(circle at 92% 8%, rgba(245, 158, 11, 0.08), transparent 38%),
    var(--glass-bg);
  border-color: rgba(245, 158, 11, 0.16);
}

.negative-callout__icon {
  display: grid;
  flex: 0 0 auto;
  width: 42px;
  height: 42px;
  color: var(--color-warning);
  background: rgba(245, 158, 11, 0.07);
  border-radius: 12px;
  font-size: 19px;
  place-items: center;
}

.negative-callout strong {
  color: var(--warning-text);
  font-size: 13px;
  font-weight: 600;
}

.negative-callout p {
  margin: 5px 0 0;
  color: var(--color-text-muted);
  font-size: 10px;
  line-height: 1.7;
}

.diagnosis-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.diagnosis-card {
  padding: 18px;
}

.diagnosis-card > span {
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 8px;
}

.diagnosis-card h3 {
  margin: 9px 0 0;
  color: var(--color-text-soft);
  font-size: 12px;
  font-weight: 600;
}

.diagnosis-card p {
  margin: 7px 0 0;
  color: var(--color-text-faint);
  font-size: 9px;
  line-height: 1.7;
}

.e2-decision {
  display: flex;
  gap: 7px;
  padding: 13px 15px;
  margin-top: 14px;
  color: var(--color-text-muted);
  font-size: 10px;
  line-height: 1.7;
  background: rgba(6, 182, 212, 0.035);
  border: 1px solid rgba(6, 182, 212, 0.11);
  border-radius: 10px;
}

.e2-decision strong {
  flex: 0 0 auto;
  color: var(--color-primary-strong);
}
.gradcam-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.gradcam-card {
  padding: 18px;
}

.gradcam-card header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 13px;
}

.gradcam-card header .el-icon {
  color: var(--color-primary);
  font-size: 21px;
}

.sample-label {
  display: inline-flex;
  padding: 3px 7px;
  font-family: var(--font-mono);
  font-size: 7px;
  border: 1px solid;
  border-radius: var(--radius-pill);
}

.sample-label.is-normal {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 9%, transparent);
  border-color: color-mix(in srgb, var(--success) 22%, transparent);
}

.sample-label.is-danger {
  color: var(--danger);
  background: color-mix(in srgb, var(--danger) 9%, transparent);
  border-color: color-mix(in srgb, var(--danger) 22%, transparent);
}

.gradcam-card h3 {
  margin: 8px 0 0;
  color: var(--color-text);
  font-size: 14px;
  font-weight: 600;
}

.sample-image {
  display: block;
  width: 100%;
  overflow: hidden;
  cursor: zoom-in;
  background: rgba(2, 6, 23, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
}

.sample-image :deep(.el-image__inner) {
  display: block;
  width: 100%;
  height: auto;
  object-fit: contain;
  transition: transform 300ms ease;
}

.sample-image:hover :deep(.el-image__inner) {
  transform: scale(1.015);
}

.gradcam-card > p {
  margin: 11px 0 0;
  color: var(--color-text-faint);
  font-size: 9px;
  line-height: 1.65;
}

.gradcam-boundary {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  padding: 12px 14px;
  margin-top: 14px;
  color: var(--color-text-muted);
  font-size: 9px;
  background: rgba(245, 158, 11, 0.035);
  border: 1px solid rgba(245, 158, 11, 0.12);
  border-radius: 10px;
}

.gradcam-boundary .el-icon {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--color-warning);
}

.model-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  justify-content: space-between;
  padding: 24px 2px;
  color: var(--color-text-faint);
  font-family: var(--font-mono);
  font-size: 14px;
  line-height: 1.6;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

@media (max-width: 1080px) {
  .model-hero {
    grid-template-columns: 1fr;
  }

  .model-orbit {
    display: none;
  }

  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .overview-grid,
  .method-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .model-nav {
    border-radius: var(--radius-md);
  }

  .model-nav__version {
    display: none;
  }

  .section-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .metric-grid,
  .diagnosis-grid,
  .gradcam-grid {
    grid-template-columns: 1fr;
  }

  .spec-list,
  .fact-list,
  .protocol-grid {
    grid-template-columns: 1fr;
  }

  .e2-decision {
    flex-direction: column;
  }

  .model-footer {
    flex-direction: column;
    gap: 5px;
  }
}

/* ==========================================================================
   可读性重构：1080p 下清晰饱满的字号与间距
   ========================================================================== */
.model-page {
  overflow: visible;
}

.model-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  gap: 8px;
  justify-content: space-between;
  width: 100%;
  padding: 12px 16px;
  margin: 18px 0 28px;
  background: color-mix(in srgb, var(--bg-card) 94%, transparent);
  border-color: var(--border-strong);
  border-radius: 16px;
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.model-nav a {
  flex: 1 1 auto;
  min-width: 0;
  padding: 11px 12px;
  color: var(--text-secondary);
  font-size: 16px;
  font-weight: 600;
  line-height: 1.2;
  text-align: center;
  white-space: nowrap;
}

.model-nav a:hover {
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 10%, transparent);
}

.model-nav__version {
  padding-left: 12px;
  font-size: 12px;
}

.model-section {
  padding: 20px 0 48px;
  scroll-margin-top: 92px;
}

.section-heading {
  gap: 24px;
  margin-bottom: 24px;
}

.section-heading h2 {
  font-size: 26px;
  line-height: 1.3;
}

.section-heading > p {
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.hero-copy .page-description {
  font-size: 15px;
  line-height: 1.75;
}

.hero-badges {
  gap: 12px;
  margin-top: 26px;
}

.hero-badge {
  gap: 9px;
  padding: 9px 13px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.4;
}

.model-orbit__label span {
  color: var(--text-tertiary);
  font-size: 11px;
}

.model-orbit__label strong {
  font-size: 20px;
}

.model-orbit__label small {
  color: var(--brand);
  font-size: 12px;
}

.metric-grid {
  gap: 18px;
  margin-bottom: 24px;
}

.metric-card {
  padding: 24px;
}

.metric-card__index {
  color: var(--text-tertiary);
  font-size: 12px;
}

.metric-card__label {
  margin-top: 14px;
  color: var(--text-secondary);
  font-size: 14px;
}

.metric-card strong {
  margin-top: 8px;
  color: var(--brand);
  font-size: clamp(28px, 2.6vw, 38px);
  font-weight: 700;
}

.metric-card small {
  margin-top: 8px;
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.5;
}

.overview-grid,
.method-grid {
  gap: 22px;
}

.spec-card,
.method-card {
  padding: 24px;
}

.card-title {
  gap: 10px;
  padding-bottom: 16px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--border-color);
}

.card-title h3 {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 650;
}

.spec-list,
.fact-list {
  gap: 16px;
}

.spec-list > div,
.fact-list > div {
  padding: 16px;
  background: color-mix(in srgb, var(--text-primary) 4%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.spec-list dt,
.fact-list dt {
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.5;
}

.spec-list dd,
.fact-list dd {
  margin: 7px 0 0;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.6;
}

.decision-card {
  gap: 20px;
  padding: 24px;
}

.decision-card h3 {
  color: var(--text-primary);
  font-size: 22px;
  line-height: 1.35;
}

.decision-card p:not(.page-eyebrow) {
  margin: 12px 0;
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.6;
}

.decision-card strong {
  font-size: 14px;
  line-height: 1.6;
}

.protocol-grid {
  gap: 16px;
}

.protocol-grid > div {
  padding: 16px;
  background: color-mix(in srgb, var(--text-primary) 4%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.protocol-grid span {
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.5;
}

.protocol-grid strong {
  margin-top: 6px;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.5;
}

.protocol-grid small {
  margin-top: 6px;
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.6;
}

.table-card {
  padding: 22px;
}

.model-table {
  font-size: 14px;
}

.model-table :deep(.el-table__cell) {
  padding: 13px 0;
  font-size: 14px;
  line-height: 1.5;
}

.model-table :deep(.el-table__header .el-table__cell) {
  font-size: 14px;
  font-weight: 650;
}

.table-primary {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}

.selected-mark {
  padding: 3px 8px;
  margin-left: 9px;
  color: var(--brand);
  font-size: 11px;
  background: color-mix(in srgb, var(--brand) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 22%, transparent);
}

.table-note {
  margin: 18px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.negative-callout {
  gap: 18px;
  padding: 22px;
  margin-bottom: 20px;
}

.negative-callout strong {
  font-size: 16px;
  line-height: 1.5;
}

.negative-callout p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.65;
}

.diagnosis-grid {
  gap: 18px;
  margin-top: 20px;
}

.diagnosis-card {
  padding: 20px;
}

.diagnosis-card > span {
  color: var(--brand);
  font-size: 12px;
}

.diagnosis-card h3 {
  margin: 10px 0 0;
  color: var(--text-primary);
  font-size: 16px;
  line-height: 1.45;
}

.diagnosis-card p {
  margin: 9px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.65;
}

.e2-decision {
  gap: 8px;
  padding: 16px 18px;
  margin-top: 18px;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.e2-decision strong {
  color: var(--brand);
}

.gradcam-grid {
  gap: 20px;
}

.gradcam-card {
  padding: 22px;
}

.gradcam-card header {
  gap: 16px;
  margin-bottom: 16px;
}

.sample-label {
  padding: 4px 9px;
  font-size: 12px;
}

.gradcam-card h3 {
  margin: 10px 0 0;
  color: var(--text-primary);
  font-size: 18px;
  line-height: 1.4;
}

.gradcam-card > p {
  margin: 14px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.65;
}

.gradcam-boundary {
  gap: 10px;
  padding: 15px 17px;
  margin-top: 18px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.65;
}

.model-footer {
  gap: 18px;
  padding: 24px 2px;
  color: var(--text-tertiary);
  font-size: 14px;
  line-height: 1.6;
  border-top: 1px solid var(--border-color);
}

@media (max-width: 760px) {
  .model-nav {
    top: 0;
    border-radius: var(--radius-md);
  }

  .model-nav a {
    flex: 0 0 auto;
    padding: 8px 11px;
    font-size: 14px;
    text-align: left;
  }

  .section-heading h2 {
    font-size: 24px;
  }

  .model-footer {
    flex-direction: column;
    gap: 8px;
  }
}
</style>