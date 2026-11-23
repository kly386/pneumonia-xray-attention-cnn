<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  src: {
    type: String,
    default: '',
  },
  alt: {
    type: String,
    default: '',
  },
  minScale: {
    type: Number,
    default: 1,
  },
  maxScale: {
    type: Number,
    default: 4,
  },
})

const scale = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const dragging = ref(false)
let lastX = 0
let lastY = 0

const imageStyle = computed(() => ({
  transform: `translate3d(${translateX.value}px, ${translateY.value}px, 0) scale(${scale.value})`,
}))

const zoomPercent = computed(() => Math.round(scale.value * 100))

function clampScale(value) {
  return Math.min(props.maxScale, Math.max(props.minScale, value))
}

function onWheel(event) {
  if (!props.src) return

  const factor = event.deltaY < 0 ? 1.14 : 0.88
  scale.value = clampScale(scale.value * factor)

  if (scale.value <= props.minScale) {
    translateX.value = 0
    translateY.value = 0
  }
}

function onPointerDown(event) {
  if (!props.src || event.button !== 0) return

  dragging.value = true
  lastX = event.clientX
  lastY = event.clientY
  event.currentTarget.setPointerCapture?.(event.pointerId)
}

function onPointerMove(event) {
  if (!dragging.value) return

  translateX.value += event.clientX - lastX
  translateY.value += event.clientY - lastY
  lastX = event.clientX
  lastY = event.clientY
}

function onPointerUp(event) {
  if (!dragging.value) return

  dragging.value = false
  event.currentTarget.releasePointerCapture?.(event.pointerId)
}

function resetView() {
  scale.value = 1
  translateX.value = 0
  translateY.value = 0
}

defineExpose({ resetView })
</script>

<template>
  <div
    class="interactive-image"
    :class="{ 'is-dragging': dragging }"
    @wheel.prevent="onWheel"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
  >
    <div class="interactive-image__canvas" :style="imageStyle">
      <slot name="base">
        <img
          v-if="src"
          class="interactive-image__base"
          :src="src"
          :alt="alt"
          draggable="false"
        />
      </slot>
      <slot></slot>
    </div>

    <span class="interactive-image__zoom" data-export-ignore="true">
      {{ zoomPercent }}%
    </span>

    <button
      class="interactive-image__reset"
      type="button"
      data-export-ignore="true"
      @pointerdown.stop
      @click.stop="resetView"
    >
      重置视图
    </button>
  </div>
</template>

<style scoped>
.interactive-image {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 330px;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.interactive-image.is-dragging {
  cursor: grabbing;
}

.interactive-image__canvas {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  transform-origin: center;
  transition: transform 140ms ease-out;
  will-change: transform;
}

.interactive-image.is-dragging .interactive-image__canvas {
  transition: none;
}

.interactive-image__base {
  width: 100%;
  height: 100%;
  max-height: 520px;
  object-fit: contain;
  pointer-events: none;
}

.interactive-image__zoom {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 6;
  padding: 4px 7px;
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 8px;
  background: rgba(2, 6, 23, 0.58);
  border: 1px solid rgba(34, 211, 238, 0.18);
  border-radius: 5px;
  pointer-events: none;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.interactive-image__reset {
  position: absolute;
  right: 10px;
  bottom: 10px;
  z-index: 6;
  padding: 5px 8px;
  color: var(--color-text-muted);
  font-size: 8px;
  cursor: pointer;
  background: rgba(2, 6, 23, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 6px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.interactive-image__reset:hover {
  color: var(--color-primary-strong);
  border-color: rgba(34, 211, 238, 0.32);
}

html:not(.dark) .interactive-image__zoom,
html:not(.dark) .interactive-image__reset {
  color: #0e7490;
  background: rgba(255, 255, 255, 0.8);
  border-color: rgba(8, 145, 178, 0.16);
}
</style>