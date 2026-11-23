<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  value: {
    type: Number,
    required: true,
  },
  duration: {
    type: Number,
    default: 1000,
  },
  decimals: {
    type: Number,
    default: 2,
  },
})

const displayValue = ref(0)
let animationFrame = 0

function stopAnimation() {
  if (animationFrame) {
    cancelAnimationFrame(animationFrame)
    animationFrame = 0
  }
}

function startAnimation() {
  stopAnimation()

  const target = Number(props.value) * 100
  if (!Number.isFinite(target)) {
    displayValue.value = 0
    return
  }

  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  if (reduceMotion) {
    displayValue.value = target
    return
  }

  const startedAt = performance.now()

  const tick = (now) => {
    const elapsed = now - startedAt
    const progress = Math.min(elapsed / props.duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)

    displayValue.value = target * eased

    if (progress < 1) {
      animationFrame = requestAnimationFrame(tick)
    } else {
      displayValue.value = target
      animationFrame = 0
    }
  }

  animationFrame = requestAnimationFrame(tick)
}

watch(
  () => [props.value, props.decimals, props.duration],
  startAnimation,
  { immediate: true },
)

onBeforeUnmount(stopAnimation)
</script>

<template>
  <span class="animated-percent" :aria-label="`${(value * 100).toFixed(decimals)}%`">
    {{ displayValue.toFixed(decimals) }}<small>%</small>
  </span>
</template>

<style scoped>
.animated-percent {
  color: #f8fafc;
  font-family: var(--font-mono);
  font-size: clamp(42px, 5vw, 62px);
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.06em;
  text-shadow: 0 0 26px rgba(34, 211, 238, 0.22);
  font-variant-numeric: tabular-nums;
}

.animated-percent small {
  margin-left: 4px;
  color: var(--color-primary-strong);
  font-size: 0.38em;
  letter-spacing: 0;
}
</style>