<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  src: {
    type: String,
    default: '',
  },
  alt: {
    type: String,
    default: 'X 光片',
  },
  windowWidth: {
    type: Number,
    default: 255,
  },
  windowLevel: {
    type: Number,
    default: 128,
  },
  inverted: {
    type: Boolean,
    default: false,
  },
})

const canvasRef = ref()
const loadFailed = ref(false)
const MAX_CANVAS_SIDE = 1600

let sourceGray = null
let sourceAlpha = null
let outputData = null
let canvasWidth = 0
let canvasHeight = 0
let renderFrame = 0

const fallbackStyle = computed(() => {
  const brightness = 1 + (props.windowLevel - 128) / 512
  const contrast = 1 + (255 - props.windowWidth) / 255
  return {
    filter: `${props.inverted ? 'invert(1) ' : ''}brightness(${brightness}) contrast(${contrast})`,
  }
})

function scheduleRender() {
  cancelAnimationFrame(renderFrame)
  renderFrame = requestAnimationFrame(renderCanvas)
}

function renderCanvas() {
  if (!sourceGray || !outputData || !canvasRef.value) return

  const width = canvasWidth
  const height = canvasHeight
  const lower = props.windowLevel - props.windowWidth / 2
  const upper = props.windowLevel + props.windowWidth / 2
  const range = Math.max(1, upper - lower)
  const output = outputData.data

  for (let index = 0; index < sourceGray.length; index += 1) {
    const gray = sourceGray[index]
    let mapped = ((gray - lower) / range) * 255

    if (mapped < 0) mapped = 0
    if (mapped > 255) mapped = 255
    if (props.inverted) mapped = 255 - mapped

    const offset = index * 4
    output[offset] = mapped
    output[offset + 1] = mapped
    output[offset + 2] = mapped
    output[offset + 3] = sourceAlpha ? sourceAlpha[index] : 255
  }

  const context = canvasRef.value.getContext('2d')
  context?.putImageData(outputData, 0, 0)
  void width
  void height
}

function loadSource() {
  loadFailed.value = false
  sourceGray = null
  sourceAlpha = null
  outputData = null

  if (!props.src) return

  const image = new Image()
  image.decoding = 'async'
  image.onload = () => {
    const scale = Math.min(
      1,
      MAX_CANVAS_SIDE / Math.max(image.naturalWidth, image.naturalHeight),
    )
    canvasWidth = Math.max(1, Math.round(image.naturalWidth * scale))
    canvasHeight = Math.max(1, Math.round(image.naturalHeight * scale))

    const workCanvas = document.createElement('canvas')
    workCanvas.width = canvasWidth
    workCanvas.height = canvasHeight
    const workContext = workCanvas.getContext('2d', { willReadFrequently: true })
    if (!workContext) {
      loadFailed.value = true
      return
    }

    workContext.drawImage(image, 0, 0, canvasWidth, canvasHeight)
    const imageData = workContext.getImageData(0, 0, canvasWidth, canvasHeight)
    const pixels = imageData.data
    const pixelCount = canvasWidth * canvasHeight

    sourceGray = new Uint8ClampedArray(pixelCount)
    sourceAlpha = new Uint8ClampedArray(pixelCount)

    for (let index = 0; index < pixelCount; index += 1) {
      const offset = index * 4
      sourceGray[index] = Math.round(
        pixels[offset] * 0.299 +
          pixels[offset + 1] * 0.587 +
          pixels[offset + 2] * 0.114,
      )
      sourceAlpha[index] = pixels[offset + 3]
    }

    if (canvasRef.value) {
      canvasRef.value.width = canvasWidth
      canvasRef.value.height = canvasHeight
      outputData = workContext.createImageData(canvasWidth, canvasHeight)
    }

    scheduleRender()
  }
  image.onerror = () => {
    loadFailed.value = true
  }
  image.src = props.src
}

watch(
  () => props.src,
  loadSource,
  { immediate: true },
)

watch(
  () => [props.windowWidth, props.windowLevel, props.inverted],
  scheduleRender,
)

onBeforeUnmount(() => {
  cancelAnimationFrame(renderFrame)
  sourceGray = null
  sourceAlpha = null
  outputData = null
})
</script>

<template>
  <canvas
    v-if="!loadFailed"
    ref="canvasRef"
    class="medical-image-canvas"
    :aria-label="alt"
    role="img"
  ></canvas>
  <img
    v-else
    class="medical-image-canvas medical-image-canvas--fallback"
    :src="src"
    :alt="alt"
    :style="fallbackStyle"
    draggable="false"
  />
</template>

<style scoped>
.medical-image-canvas {
  display: block;
  width: 100%;
  height: 100%;
  max-height: 520px;
  object-fit: contain;
  pointer-events: none;
  image-rendering: auto;
}

.medical-image-canvas--fallback {
  user-select: none;
}
</style>