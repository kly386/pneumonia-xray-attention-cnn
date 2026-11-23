<script setup>
defineProps({
  stage: {
    type: String,
    default: 'preprocess',
  },
})

const stageLabels = {
  preprocess: '正在预处理影像…',
  inference: '正在提取影像特征…',
  finalize: '正在生成辅助结果…',
}
</script>

<template>
  <div class="scan-overlay" aria-live="polite" aria-label="AI 正在分析 X 光片">
    <div class="scan-overlay__grid"></div>
    <div class="scan-overlay__line"></div>

    <span class="scan-corner scan-corner--tl"></span>
    <span class="scan-corner scan-corner--tr"></span>
    <span class="scan-corner scan-corner--bl"></span>
    <span class="scan-corner scan-corner--br"></span>

    <div class="scan-overlay__hud">
      <span class="scan-overlay__pulse"></span>
      <div>
        <strong>AI 正在分析影像特征</strong>
        <small>{{ stageLabels[stage] || stageLabels.preprocess }}</small>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scan-overlay {
  position: absolute;
  inset: 0;
  z-index: 5;
  overflow: hidden;
  background: rgba(2, 6, 23, 0.68);
  border-radius: inherit;
}

.scan-overlay__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(34, 211, 238, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.08) 1px, transparent 1px);
  background-size: 30px 30px;
  mask-image: linear-gradient(to bottom, transparent, #000 18%, #000 82%, transparent);
}

.scan-overlay__line {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, transparent, #22d3ee 18%, #67e8f9 50%, #22d3ee 82%, transparent);
  box-shadow:
    0 0 8px rgba(34, 211, 238, 0.95),
    0 0 22px rgba(6, 182, 212, 0.72);
  animation: scan-sweep 1.8s linear infinite;
}

.scan-overlay__line::before {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 72px;
  content: '';
  background: linear-gradient(to top, rgba(6, 182, 212, 0.22), transparent);
}

.scan-corner {
  position: absolute;
  z-index: 3;
  width: 28px;
  height: 28px;
  border-color: rgba(34, 211, 238, 0.85);
  border-style: solid;
}

.scan-corner--tl {
  top: 18px;
  left: 18px;
  border-width: 1px 0 0 1px;
}

.scan-corner--tr {
  top: 18px;
  right: 18px;
  border-width: 1px 1px 0 0;
}

.scan-corner--bl {
  bottom: 18px;
  left: 18px;
  border-width: 0 0 1px 1px;
}

.scan-corner--br {
  right: 18px;
  bottom: 18px;
  border-width: 0 1px 1px 0;
}

.scan-overlay__hud {
  position: absolute;
  bottom: 24px;
  left: 50%;
  display: flex;
  gap: 11px;
  align-items: center;
  min-width: min(320px, calc(100% - 40px));
  padding: 11px 15px;
  color: var(--color-text-soft);
  background: rgba(15, 23, 42, 0.86);
  border: 1px solid rgba(34, 211, 238, 0.24);
  border-radius: 12px;
  box-shadow: 0 12px 35px rgba(2, 6, 23, 0.36);
  transform: translateX(-50%);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.scan-overlay__hud > div {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.scan-overlay__hud strong {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
}

.scan-overlay__hud small {
  margin-top: 4px;
  color: var(--color-primary-strong);
  font-size: 14px;
}

.scan-overlay__pulse {
  width: 8px;
  height: 8px;
  background: var(--color-primary);
  border-radius: 50%;
  box-shadow: 0 0 14px rgba(6, 182, 212, 0.9);
  animation: scan-pulse 1.1s ease-in-out infinite;
}

@keyframes scan-sweep {
  0% {
    top: 0;
    opacity: 0;
  }

  8% {
    opacity: 1;
  }

  92% {
    opacity: 1;
  }

  100% {
    top: calc(100% - 2px);
    opacity: 0;
  }
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

@media (prefers-reduced-motion: reduce) {
  .scan-overlay__line {
    top: 50%;
    animation: none;
  }

  .scan-overlay__pulse {
    animation: none;
  }
}
</style>