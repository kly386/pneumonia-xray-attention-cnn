<template>
  <div class="holo-scene" @click="closeCard">
    <div class="holo-grid" aria-hidden="true"></div>
    <div class="holo-scanline" aria-hidden="true"></div>
    <div class="holo-aura" aria-hidden="true"></div>

    <span
      v-for="index in 8"
      :key="index"
      class="holo-particle"
      :class="`holo-particle--${index}`"
      aria-hidden="true"
    ></span>

    <header class="holo-heading">
      <p>HOLOGRAPHIC ANATOMY</p>
      <h1>全息肺部互动</h1>
      <span>拖拽旋转全息人体，点击胸部发光热区探索呼吸系统与肺炎知识。</span>
    </header>

    <nav id="tour-holo-tabs" class="system-tabs" aria-label="解剖系统切换" @click.stop>
      <span class="system-tabs__title">ANATOMY LAYERS</span>
      <button
        v-for="system in SYSTEM_TABS"
        :key="system.key"
        type="button"
        class="system-tab"
        :class="{ 'is-active': activeSystemKey === system.key }"
        :style="{ '--tab-accent': system.accent }"
        :aria-pressed="activeSystemKey === system.key"
        @click="selectSystem(system.key)"
      >
        <span class="system-tab__icon">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              v-for="(path, index) in system.iconPaths"
              :key="index"
              :d="path"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </span>
        <span class="system-tab__label">{{ system.label }}</span>
      </button>
    </nav>

    <div id="tour-holo-viewer" class="viewer-stage">
      <div ref="viewerRef" class="three-viewer"></div>

      <div v-if="loading" class="load-overlay">
        <div class="load-ring"></div>
        <strong>正在构建全息人体</strong>
        <span>{{ loadingProgress }}%</span>
        <div class="load-track">
          <i :style="{ width: `${loadingProgress}%` }"></i>
        </div>
      </div>

      <div v-if="loadError" class="load-error">
        <img src="/holo-human-cutout.png" alt="全息人体降级预览" />
        <div>
          <strong>3D 模型加载失败</strong>
          <span>{{ loadError }}</span>
        </div>
      </div>

      <div class="viewer-hint">
        <span class="viewer-hint__dot"></span>
        拖拽旋转 · 滚轮缩放 · 点击热点查看科普
      </div>
    </div>

    <aside id="tour-holo-controls" class="orbit-controls" aria-label="模型视角控制" @click.stop>
      <span class="orbit-controls__title">VIEW CONTROL</span>
      <button
        type="button"
        class="orbit-button"
        aria-label="向左旋转 45 度"
        title="向左旋转 45°"
        @click="rotateCamera(Math.PI / 4)"
      >
        &lt;
      </button>
      <button
        type="button"
        class="orbit-button orbit-button--reset"
        aria-label="恢复正面视角"
        title="恢复正面视角"
        @click="resetCamera"
      >
        复位
      </button>
      <button
        type="button"
        class="orbit-button"
        aria-label="向右旋转 45 度"
        title="向右旋转 45°"
        @click="rotateCamera(-Math.PI / 4)"
      >
        &gt;
      </button>
    </aside>
    <Transition name="holo-card">
      <aside
        v-if="cardVisible"
        class="lung-card spot-card"
        :style="{ '--system-accent': activeCard.accent }"
        aria-live="polite"
        @click.stop
      >
        <span class="card-line" aria-hidden="true"></span>
        <span class="card-corner card-corner--tl" aria-hidden="true"></span>
        <span class="card-corner card-corner--br" aria-hidden="true"></span>

        <div class="card-kicker">
          <span class="kicker-dot"></span>
          {{ cardKicker }}
        </div>

        <Transition name="spot-fade" mode="out-in">
          <div :key="`${cardMode}-${activeCard.key}`" class="spot-content">
            <figure class="spot-media">
              <el-image
                :src="activeCard.imageUrl"
                :alt="`${activeCard.label}示意图`"
                fit="cover"
                :preview-src-list="[activeCard.imageUrl]"
                preview-teleported
              />
              <figcaption>{{ activeCard.label }} · 科普示意图</figcaption>
            </figure>

            <h2>{{ activeCard.title }}</h2>
            <p>{{ activeCard.content }}</p>

            <div class="card-metrics">
              <div>
                <span>部位</span>
                <strong>{{ activeCard.label }}</strong>
              </div>
              <div>
                <span>交互提示</span>
                <strong>点击热点或左侧图层切换</strong>
              </div>
            </div>
          </div>
        </Transition>

        <div class="card-actions">
          <button class="card-action" type="button" @click="goScreening">
            <span>前往 AI 辅助筛查</span>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M5 12h14m-6-6 6 6-6 6"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </button>
        </div>
      </aside>
    </Transition>

    <footer class="holo-telemetry" aria-hidden="true">
      <span><i></i> HOLOGRAM ONLINE</span>
      <span>BIO-MEDICAL 3D MODULE</span>
      <span>X-RAY SCREENING LINK</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import { startPageTour, startPageTourOnce, onPageTourRequest } from '@/composables/usePageTour'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import {
  CSS2DObject,
  CSS2DRenderer,
} from 'three/addons/renderers/CSS2DRenderer.js'
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js'

const router = useRouter()
const { isDark } = useTheme()

const viewerRef = ref()
const cardVisible = ref(false)
const loading = ref(true)
const loadingProgress = ref(0)
const loadError = ref('')
const activeSystemKey = ref('respiratory')
const activeSpotKey = ref('lungs')

const SYSTEM_TABS = [
  {
    key: 'skeletal',
    label: '骨骼系统',
    index: '01',
    accent: '#fbbf24',
    title: '骨骼系统 (Skeletal)',
    content:
      '由骨、关节和韧带构成人体的力学支架，保护心、肺等重要脏器。评估胸片时，肋骨与胸骨可能遮挡部分肺野，需要结合多体位影像观察。',
    imageUrl: '/holo-hotspots/thorax.svg',
    iconPaths: [
      'M12 3v18',
      'M8 6h8',
      'M6.5 10h11',
      'M8 14h8',
      'M9.5 18h5',
    ],
  },
  {
    key: 'respiratory',
    label: '呼吸系统',
    index: '02',
    accent: '#22d3ee',
    title: '呼吸系统 (Respiratory)',
    content:
      '鼻腔、咽、喉、气管、支气管与肺泡共同完成通气与气体交换。发生肺炎时，肺泡内渗出物增多，X 光下常表现为白色实变或斑片状影。',
    imageUrl: '/model-samples/pneumonia-gradcam.png',
    iconPaths: [
      'M12 4v9',
      'M9 7c-2.4.3-4 2.4-4 5.2V16c0 2.2 1.8 4 4 4s3-1.6 3-4v-2',
      'M15 7c2.4.3 4 2.4 4 5.2V16c0 2.2-1.8 4-4 4s-3-1.6-3-4v-2',
    ],
  },
  {
    key: 'cardiovascular',
    label: '心血管系统',
    index: '03',
    accent: '#f472b6',
    title: '心血管系统 (Cardiovascular)',
    content:
      '心脏与血管构成全身循环运输网络。肺部感染可加重心肺循环负担，因此在肺炎评估中需要同时关注心率、血压与基础心肺疾病。',
    imageUrl: '/model-samples/normal-gradcam.png',
    iconPaths: [
      'M12 20.2S5 16 5 10.8C5 8.1 7.1 6 9.7 6c1.2 0 2 .5 2.3 1.2C12.3 6.5 13.1 6 14.3 6 16.9 6 19 8.1 19 10.8c0 5.2-7 9.4-7 9.4Z',
      'M8 12h3l1.2-2.2 1.6 4 1.2-1.8h2',
    ],
  },
]

const HOTSPOTS = [
  {
    key: 'trachea',
    label: '气管',
    index: 'A',
    accent: '#22d3ee',
    position: { x: 0, y: 0.86, z: 0.18 },
    title: '气管与支气管',
    content:
      '连接喉与肺的通道。肺炎常表现为支气管壁增厚或沿支气管分布的斑片状渗出影。',
    imageUrl: '/holo-hotspots/trachea.svg',
  },
  {
    key: 'lungs',
    label: '肺部',
    index: 'B',
    accent: '#67e8f9',
    position: { x: -0.22, y: 0.4, z: 0.26 },
    title: '肺部 (Lungs)',
    content:
      '气体交换的核心器官。发生肺炎时，肺泡内充满炎性渗出物，导致X光片下呈现白色实变影。',
    imageUrl: '/model-samples/pneumonia-gradcam.png',
  },
  {
    key: 'thorax',
    label: '胸廓',
    index: 'C',
    accent: '#fbbf24',
    position: { x: 0.42, y: 0.32, z: 0.12 },
    title: '胸廓 (Thorax)',
    content:
      '由肋骨与胸骨构成，保护内部脏器。下叶肺炎累及胸膜时，患者常感到明显的胸痛。',
    imageUrl: '/holo-hotspots/thorax.svg',
  },
]

const cardMode = ref('spot')
const activeSpot = computed(
  () => HOTSPOTS.find((spot) => spot.key === activeSpotKey.value) || HOTSPOTS[1],
)
const activeSystem = computed(
  () => SYSTEM_TABS.find((system) => system.key === activeSystemKey.value) || SYSTEM_TABS[1],
)
const activeCard = computed(() =>
  cardMode.value === 'system' ? activeSystem.value : activeSpot.value,
)
const cardKicker = computed(() =>
  cardMode.value === 'system'
    ? `ANATOMY LAYER · ${activeSystem.value.index}`
    : `ANATOMY HOTSPOT · ${activeSpot.value.index}`,
)

function selectSystem(key) {
  if (!SYSTEM_TABS.some((system) => system.key === key)) return
  activeSystemKey.value = key
  cardMode.value = 'system'
  cardVisible.value = true
  updateHotspotStates()
}

function selectSpot(key) {
  if (!HOTSPOTS.some((spot) => spot.key === key)) return
  activeSpotKey.value = key
  cardMode.value = 'spot'
  cardVisible.value = true
  updateHotspotStates()
}

const hotspotObjects = new Map()

function updateHotspotStates() {
  hotspotObjects.forEach(({ element }, key) => {
    element.classList.toggle(
      'is-active',
      cardMode.value === 'spot' && activeSpotKey.value === key,
    )
  })
}

function createHotspots() {
  if (!modelRoot) return

  hotspotObjects.forEach(({ object, element }) => {
    object.removeFromParent()
    element.remove()
  })
  hotspotObjects.clear()

  HOTSPOTS.forEach((spot) => {
    const element = document.createElement('button')
    element.type = 'button'
    element.className = 'body-hotspot'
    element.setAttribute('aria-label', `查看${spot.label}科普`)
    element.style.setProperty('--spot-accent', spot.accent)
    element.innerHTML = `
      <span class="body-hotspot__ring"></span>
      <span class="body-hotspot__ring body-hotspot__ring--delay"></span>
      <span class="body-hotspot__dot"></span>
      <span class="body-hotspot__tag">${spot.index} · ${spot.label}</span>
    `
    element.addEventListener('click', (event) => {
      event.stopPropagation()
      selectSpot(spot.key)
    })

    const object = new CSS2DObject(element)
    object.position.set(
      spot.position.x,
      spot.position.y,
      spot.position.z,
    )
    modelRoot.add(object)
    hotspotObjects.set(spot.key, { object, element })
  })

  updateHotspotStates()
}

let scene
let camera
let renderer
let labelRenderer
let controls
let composer
let bloomPass
let modelRoot
let ambientLight
let keyLight
let rimLight
let blueFill
let resizeObserver
let animationFrame = 0
let clock
let baseRing
let cameraTween = null

const defaultCameraPosition = new THREE.Vector3(0, 0.12, 4.2)
const yAxis = new THREE.Vector3(0, 1, 0)

function applySceneTheme() {
  if (!scene || !renderer) return

  const dark = isDark.value
  const backgroundColor = dark ? 0x0f172a : 0x0b1e36
  scene.background?.set(backgroundColor)
  scene.fog?.color?.set(backgroundColor)
  renderer.setClearColor(backgroundColor, 1)
  renderer.toneMappingExposure = dark ? 1.08 : 1

  if (scene.fog && 'density' in scene.fog) {
    scene.fog.density = dark ? 0.16 : 0.12
  }

  if (bloomPass) {
    bloomPass.strength = dark ? 0.24 : 0.07
  }

  if (ambientLight) {
    ambientLight.intensity = dark ? 0.4 : 0.78
    ambientLight.color.setHex(dark ? 0xffffff : 0xdbeafe)
  }

  if (keyLight) {
    keyLight.intensity = dark ? 2.1 : 2.8
    keyLight.color.setHex(dark ? 0xbfe9ff : 0xffffff)
  }

  if (rimLight) {
    rimLight.intensity = dark ? 3.2 : 1.6
    rimLight.color.setHex(dark ? 0x06b6d4 : 0x0369a1)
  }

  if (blueFill) {
    blueFill.intensity = dark ? 22 : 12
    blueFill.color.setHex(dark ? 0x3b82f6 : 0x1d4ed8)
  }

  updateMaterialTheme()
}

function closeCard() {
  cardVisible.value = false
}

function goScreening() {
  router.push('/workspace')
}

function startCameraTween(targetPosition) {
  if (!camera || !controls) return

  cameraTween = {
    from: camera.position.clone(),
    to: targetPosition.clone(),
    startedAt: performance.now(),
    duration: 560,
  }
  controls.enabled = false
}

function rotateCamera(angle) {
  if (!camera || !controls || cameraTween) return

  const offset = camera.position.clone().sub(controls.target)
  offset.applyAxisAngle(yAxis, angle)
  startCameraTween(controls.target.clone().add(offset))
}

function resetCamera() {
  if (!camera || !controls || cameraTween) return

  controls.target.set(0, 0, 0)
  startCameraTween(defaultCameraPosition)
}


// 全息材质：全漫反射（无高光）+ 明亮青色半透明，靠线框而非反光表现结构
const HOLO_BODY_COLOR = 0x06b6d4
const HOLO_EDGE_COLOR = 0x67e8f9

const MODEL_THEME = {
  light: {
    color: HOLO_BODY_COLOR,
    emissive: 0x0e7490,
    emissiveIntensity: 0.3,
    opacity: 0.6,
    roughness: 1,
    metalness: 0,
    edgeColor: HOLO_EDGE_COLOR,
    edgeOpacity: 0.88,
  },
  dark: {
    color: HOLO_BODY_COLOR,
    emissive: 0x0e7490,
    emissiveIntensity: 0.38,
    opacity: 0.6,
    roughness: 1,
    metalness: 0,
    edgeColor: HOLO_EDGE_COLOR,
    edgeOpacity: 0.96,
  },
}

function getModelTheme() {
  return isDark.value ? MODEL_THEME.dark : MODEL_THEME.light
}

function tintMaterial(material, palette = getModelTheme()) {
  if (!material) return material

  // 去掉原模型深色颜色/粗糙度/金属度贴图，避免人体看起来像一坨深色泥巴；
  // 只保留法线与 AO 贴图维持骨骼、肌肉的表面细节。
  if (material.isMeshStandardMaterial) {
    material.map = null
    material.roughnessMap = null
    material.metalnessMap = null
    material.emissiveMap = null
    material.color.setHex(palette.color)
    material.emissive.setHex(palette.emissive)
    material.emissiveIntensity = palette.emissiveIntensity
    material.transparent = true
    material.opacity = palette.opacity
    material.roughness = 1
    material.metalness = 0
    material.depthWrite = false
    material.side = THREE.FrontSide
    material.userData.holoTinted = true

    if (material.normalMap) {
      material.normalScale.set(0.45, 0.45)
    }

    material.needsUpdate = true
    return material
  }

  const tinted = new THREE.MeshStandardMaterial({
    normalMap: material.normalMap || null,
    aoMap: material.aoMap || null,
    alphaMap: material.alphaMap || null,
    color: palette.color,
    emissive: palette.emissive,
    emissiveIntensity: palette.emissiveIntensity,
    transparent: true,
    opacity: palette.opacity,
    roughness: 1,
    metalness: 0,
    side: THREE.FrontSide,
    vertexColors: material.vertexColors,
    depthWrite: false,
  })
  tinted.userData.holoTinted = true

  material.dispose()
  return tinted
}

// 给每个 mesh 叠加青色发光轮廓线，让骨架和肌肉边缘在深色背景上清晰透亮
function addEdgeLines(mesh, palette) {
  if (!mesh.geometry) return

  const edges = new THREE.EdgesGeometry(mesh.geometry, 16)
  const lines = new THREE.LineSegments(
    edges,
    new THREE.LineBasicMaterial({
      color: palette.edgeColor,
      transparent: true,
      opacity: palette.edgeOpacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  )
  lines.renderOrder = 2
  lines.userData.holoEdge = true
  mesh.add(lines)
}

function applyTechMaterial(model) {
  const palette = getModelTheme()

  model.traverse((object) => {
    if (!object.isMesh) return

    if (Array.isArray(object.material)) {
      object.material = object.material.map((material) =>
        tintMaterial(material, palette),
      )
    } else {
      object.material = tintMaterial(object.material, palette)
    }

    object.renderOrder = 1
    object.castShadow = false
    object.receiveShadow = false

    if (!object.children.some((child) => child.userData?.holoEdge)) {
      addEdgeLines(object, palette)
    }
  })
}

function updateMaterialTheme() {
  if (!modelRoot) return
  const palette = getModelTheme()

  modelRoot.traverse((object) => {
    // 轮廓线随主题同步亮度
    if (object.userData?.holoEdge && object.material) {
      object.material.color.setHex(palette.edgeColor)
      object.material.opacity = palette.edgeOpacity
      return
    }

    if (!object.isMesh || !object.material) return
    const materials = Array.isArray(object.material)
      ? object.material
      : [object.material]

    materials.forEach((material) => {
      if (!material?.userData?.holoTinted) return
      material.color.setHex(palette.color)
      material.emissive.setHex(palette.emissive)
      material.emissiveIntensity = palette.emissiveIntensity
      material.opacity = palette.opacity
      material.roughness = 1
      material.metalness = 0
      material.needsUpdate = true
    })
  })
}

function createGroundBase() {
  const group = new THREE.Group()
  group.position.y = -1.24

  const disc = new THREE.Mesh(
    new THREE.CircleGeometry(1.3, 96),
    new THREE.MeshBasicMaterial({
      color: 0x06b6d4,
      transparent: true,
      opacity: 0.03,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  )
  disc.rotation.x = -Math.PI / 2
  group.add(disc)

  const grid = new THREE.PolarGridHelper(
    1.3,
    16,
    8,
    64,
    0x06b6d4,
    0x0e7490,
  )
  grid.material.transparent = true
  grid.material.opacity = 0.26
  group.add(grid)

  const ring = new THREE.Mesh(
    new THREE.RingGeometry(1.02, 1.065, 96),
    new THREE.MeshBasicMaterial({
      color: 0x67e8f9,
      transparent: true,
      opacity: 0.66,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  )
  ring.rotation.x = -Math.PI / 2
  ring.position.y = 0.012
  group.add(ring)
  baseRing = ring

  scene.add(group)
}

function buildLights() {
  // 环境光负责整体明暗，方向光勾勒肌肉与骨骼细节。
  ambientLight = new THREE.AmbientLight(0xdbeafe, 0.78)
  scene.add(ambientLight)

  keyLight = new THREE.DirectionalLight(0xffffff, 2.8)
  keyLight.position.set(4, 5, 6)
  scene.add(keyLight)

  rimLight = new THREE.DirectionalLight(0x0369a1, 1.6)
  rimLight.position.set(-3, 2, -4)
  scene.add(rimLight)

  blueFill = new THREE.PointLight(0x1d4ed8, 12, 10, 2)
  blueFill.position.set(3, 0.5, 2.5)
  scene.add(blueFill)
}

function loadHumanModel() {
  const loader = new GLTFLoader()

  loader.load(
    '/models/human.glb',
    (gltf) => {
      const model = gltf.scene
      modelRoot = new THREE.Group()
      scene.add(modelRoot)

      const sourceBox = new THREE.Box3().setFromObject(model)
      const sourceSize = sourceBox.getSize(new THREE.Vector3())
      const targetHeight = 2.5
      const scale = targetHeight / Math.max(sourceSize.y, 0.001)
      model.scale.setScalar(scale)

      const scaledBox = new THREE.Box3().setFromObject(model)
      const scaledCenter = scaledBox.getCenter(new THREE.Vector3())
      model.position.x -= scaledCenter.x
      model.position.z -= scaledCenter.z
      model.position.y -= scaledBox.min.y + 1.24

      applyTechMaterial(model)
      modelRoot.add(model)
      createHotspots()

      loading.value = false
      controls.update()
    },
    (event) => {
      if (event.total > 0) {
        loadingProgress.value = Math.min(
          99,
          Math.round((event.loaded / event.total) * 100),
        )
      }
    },
    (error) => {
      loading.value = false
      loadError.value =
        error?.message || '无法加载 /models/human.glb，请检查文件是否存在。'
    },
  )
}


function animate() {
  animationFrame = requestAnimationFrame(animate)
  clock.getDelta()
  const elapsed = clock.elapsedTime

  if (modelRoot) {
    modelRoot.position.y = Math.sin(elapsed * 1.1) * 0.018
  }

  if (cameraTween && camera && controls) {
    const progress = Math.min(
      (performance.now() - cameraTween.startedAt) / cameraTween.duration,
      1,
    )
    const eased = 1 - Math.pow(1 - progress, 3)
    camera.position.lerpVectors(cameraTween.from, cameraTween.to, eased)
    camera.lookAt(controls.target)

    if (progress >= 1) {
      cameraTween = null
      controls.enabled = true
      controls.update()
    }
  } else {
    controls?.update()
  }

  if (baseRing) {
    baseRing.material.opacity = 0.55 + Math.sin(elapsed * 1.8) * 0.16
  }

  if (composer) {
    composer.render()
  } else if (renderer && scene && camera) {
    renderer.render(scene, camera)
  }

  if (labelRenderer && scene && camera) {
    labelRenderer.render(scene, camera)
  }
}

function handleResize() {
  if (!viewerRef.value || !renderer || !camera || !labelRenderer) return

  const width = viewerRef.value.clientWidth
  const height = viewerRef.value.clientHeight
  if (!width || !height) return

  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
  composer?.setSize(width, height)
  labelRenderer.setSize(width, height)
}

function initScene() {
  const container = viewerRef.value
  if (!container) return

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x0f172a)
  scene.fog = new THREE.FogExp2(0x0f172a, 0.16)

  camera = new THREE.PerspectiveCamera(
    36,
    container.clientWidth / Math.max(container.clientHeight, 1),
    0.1,
    100,
  )
  camera.position.copy(defaultCameraPosition)
  camera.lookAt(0, 0, 0)

  renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(container.clientWidth, container.clientHeight)
  renderer.setClearColor(0x0f172a, 1)
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05
  renderer.domElement.style.cursor = 'grab'
  renderer.domElement.style.touchAction = 'none'
  container.appendChild(renderer.domElement)

  labelRenderer = new CSS2DRenderer()
  labelRenderer.setSize(container.clientWidth, container.clientHeight)
  labelRenderer.domElement.style.position = 'absolute'
  labelRenderer.domElement.style.top = '0'
  labelRenderer.domElement.style.left = '0'
  labelRenderer.domElement.style.pointerEvents = 'none'
  labelRenderer.domElement.style.zIndex = '4'
  container.appendChild(labelRenderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 0, 0)
  controls.enableDamping = true
  controls.dampingFactor = 0.075
  controls.enablePan = false
  controls.minDistance = 3.1
  controls.maxDistance = 5.8
  controls.rotateSpeed = 0.72
  controls.zoomSpeed = 0.8
  controls.minPolarAngle = Math.PI * 0.24
  controls.maxPolarAngle = Math.PI * 0.76
  controls.update()

  buildLights()
  createGroundBase()

  // Bloom 只做轻微轮廓增强，避免吞掉骨骼和肌肉纹理
  composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))
  bloomPass = new UnrealBloomPass(
    new THREE.Vector2(container.clientWidth, container.clientHeight),
    0.22,
    0.24,
    0.68,
  )
  composer.addPass(bloomPass)

  clock = new THREE.Clock()
  applySceneTheme()
  loadHumanModel()

  resizeObserver = new ResizeObserver(handleResize)
  resizeObserver.observe(container)

  animate()
}

function disposeScene() {
  cancelAnimationFrame(animationFrame)
  resizeObserver?.disconnect()
  controls?.dispose()
  hotspotObjects.forEach(({ object, element }) => {
    object.removeFromParent()
    element.remove()
  })
  hotspotObjects.clear()
  labelRenderer?.domElement?.remove()
  composer?.dispose?.()
  renderer?.dispose()
  scene?.traverse((object) => {
    if (object.userData?.holoEdge) {
      object.geometry?.dispose()
      object.material?.dispose()
      return
    }
    if (!object.isMesh) return
    object.geometry?.dispose()
    const materials = Array.isArray(object.material)
      ? object.material
      : [object.material]

    materials.forEach((material) => {
      material?.map?.dispose?.()
      material?.normalMap?.dispose?.()
      material?.aoMap?.dispose?.()
      material?.roughnessMap?.dispose?.()
      material?.metalnessMap?.dispose?.()
      material?.emissiveMap?.dispose?.()
      material?.alphaMap?.dispose?.()
      material?.dispose?.()
    })
  })
}

watch(isDark, applySceneTheme)
watch([activeSpotKey, cardMode], updateHotspotStates)

const HOLO_TOUR_STEPS = [
  {
    element: '#tour-holo-tabs',
    popover: {
      title: '解剖图层',
      description: '切换呼吸、循环等解剖系统，查看对应结构与科普内容。',
    },
  },
  {
    element: '#tour-holo-viewer',
    popover: {
      title: '3D 全息模型',
      description: '拖拽旋转、滚轮缩放模型，点击气管、肺部、胸廓热点查看肺炎科普。',
    },
  },
  {
    element: '#tour-holo-controls',
    popover: {
      title: '视角控制',
      description: '使用左侧按钮快速左右翻转 45°，或一键恢复正面视角。',
    },
  },
]

let removeTourListener = null

onMounted(() => {
  initScene()
  startPageTourOnce({
    storageKey: 'hasSeenTour_holo_body',
    isDark: isDark.value,
    delay: 1000,
    steps: HOLO_TOUR_STEPS,
  })

  removeTourListener = onPageTourRequest(() => {
    startPageTour({
      storageKey: 'hasSeenTour_holo_body',
      isDark: isDark.value,
      steps: HOLO_TOUR_STEPS,
    })
  }, '/holo-body')
})

onBeforeUnmount(() => {
  disposeScene()
  removeTourListener?.()
})
</script>
<style scoped>
.holo-scene {
  position: relative;
  width: 100%;
  min-height: 760px;
  height: calc(100vh - 210px);
  overflow: hidden;
  isolation: isolate;
  background:
    radial-gradient(circle at 50% 40%, rgba(34, 211, 238, 0.09), transparent 31%),
    radial-gradient(circle at 82% 65%, rgba(59, 130, 246, 0.08), transparent 32%),
    linear-gradient(155deg, #020617 0%, #0f172a 50%, #07111f 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 22px;
  box-shadow: inset 0 0 100px rgba(2, 6, 23, 0.55);
}

.holo-scene::before {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  content: '';
  background:
    linear-gradient(rgba(34, 211, 238, 0.022) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.022) 1px, transparent 1px);
  background-size: 52px 52px;
  mask-image: radial-gradient(circle at 50% 44%, #000 0%, transparent 74%);
}

.holo-grid {
  position: absolute;
  right: -22%;
  bottom: -20%;
  left: -22%;
  z-index: 0;
  height: 50%;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(34, 211, 238, 0.14) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.14) 1px, transparent 1px);
  background-size: 48px 48px;
  opacity: 0.27;
  transform: perspective(580px) rotateX(63deg);
  transform-origin: center bottom;
  animation: floor-drift 9s linear infinite;
  mask-image: linear-gradient(to top, #000, transparent 88%);
}

.holo-scanline {
  position: absolute;
  top: 0;
  left: 8%;
  z-index: 2;
  width: 84%;
  height: 1px;
  pointer-events: none;
  background: linear-gradient(90deg, transparent, rgba(34, 211, 238, 0.28), transparent);
  box-shadow: 0 0 20px rgba(34, 211, 238, 0.16);
  animation: scene-scan 7s linear infinite;
}

.holo-aura {
  position: absolute;
  top: 46%;
  left: 50%;
  z-index: 0;
  width: min(680px, 70vw);
  height: min(680px, 70vw);
  pointer-events: none;
  background: radial-gradient(circle, rgba(6, 182, 212, 0.12), transparent 68%);
  border-radius: 50%;
  filter: blur(24px);
  transform: translate(-50%, -50%);
}

.holo-heading {
  position: absolute;
  top: 28px;
  left: 33px;
  z-index: 8;
  max-width: 520px;
  pointer-events: none;
}

.holo-heading p {
  margin: 0 0 7px;
  color: #67e8f9;
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.2em;
}

.holo-heading h1 {
  margin: 0;
  color: #f0fdfa;
  font-size: clamp(25px, 3.2vw, 41px);
  font-weight: 650;
  line-height: 1.15;
  letter-spacing: -0.04em;
  text-shadow: 0 0 30px rgba(34, 211, 238, 0.18);
}

.holo-heading span {
  display: block;
  max-width: 520px;
  margin-top: 9px;
  color: #cbd5e1;
  font-size: 14px;
  line-height: 1.75;
}

.holo-particle {
  position: absolute;
  z-index: 2;
  width: 3px;
  height: 3px;
  pointer-events: none;
  background: #67e8f9;
  border-radius: 50%;
  box-shadow: 0 0 9px rgba(103, 232, 249, 0.8);
  animation: particle-float 6s ease-in-out infinite;
}

.holo-particle--1 { top: 24%; left: 22%; animation-delay: -1.2s; }
.holo-particle--2 { top: 34%; left: 14%; animation-delay: -3.6s; }
.holo-particle--3 { top: 68%; left: 24%; animation-delay: -2.3s; }
.holo-particle--4 { top: 78%; left: 36%; animation-delay: -4.1s; }
.holo-particle--5 { top: 25%; right: 24%; animation-delay: -0.8s; }
.holo-particle--6 { top: 46%; right: 15%; animation-delay: -2.8s; }
.holo-particle--7 { top: 70%; right: 26%; animation-delay: -4.8s; }
.holo-particle--8 { top: 82%; right: 38%; animation-delay: -1.7s; }

@keyframes floor-drift {
  to { background-position: 0 48px, 0 48px; }
}

@keyframes scene-scan {
  0% { top: 0; opacity: 0; }
  8% { opacity: 1; }
  90% { opacity: 0.5; }
  100% { top: 100%; opacity: 0; }
}

@keyframes particle-float {
  0%, 100% { opacity: 0.25; transform: translateY(0) scale(0.8); }
  50% { opacity: 0.9; transform: translateY(-18px) scale(1.35); }
}
.viewer-stage {
  position: absolute;
  inset: 0;
  z-index: 3;
}

.three-viewer {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.three-viewer :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
  outline: none;
}
.load-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 12;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 260px;
  padding: 24px;
  color: #cbd5e1;
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(34, 211, 238, 0.18);
  border-radius: 16px;
  box-shadow: 0 20px 50px rgba(2, 6, 23, 0.5);
  transform: translate(-50%, -50%);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.load-ring {
  width: 46px;
  height: 46px;
  margin-bottom: 15px;
  border: 1px solid rgba(34, 211, 238, 0.16);
  border-top-color: #67e8f9;
  border-right-color: #22d3ee;
  border-radius: 50%;
  box-shadow: 0 0 18px rgba(34, 211, 238, 0.22);
  animation: load-spin 1s linear infinite;
}

.load-overlay strong {
  font-size: 12px;
  font-weight: 600;
}

.load-overlay > span {
  margin-top: 6px;
  color: #67e8f9;
  font-family: var(--font-mono);
  font-size: 10px;
}
.load-track {
  width: 190px;
  height: 3px;
  margin-top: 13px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.12);
  border-radius: 99px;
}

.load-track i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #06b6d4, #67e8f9);
  border-radius: inherit;
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.65);
  transition: width 200ms ease;
}

.load-error {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 12;
  width: min(430px, calc(100% - 40px));
  padding: 18px;
  color: #fca5a5;
  text-align: center;
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 16px;
  transform: translate(-50%, -50%);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.load-error img {
  width: min(260px, 72%);
  margin: 0 auto 14px;
  filter:
    saturate(1.15)
    brightness(1.08)
    drop-shadow(0 0 18px rgba(34, 211, 238, 0.4));
}

.load-error > div {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.load-error strong {
  color: #fecaca;
  font-size: 12px;
}

.load-error span {
  color: #94a3b8;
  font-size: 9px;
  line-height: 1.6;
}
.viewer-hint {
  position: absolute;
  bottom: 45px;
  left: 50%;
  z-index: 7;
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 7px 11px;
  color: rgba(148, 163, 184, 0.82);
  font-family: var(--font-mono);
  font-size: 13px;
  white-space: nowrap;
  background: rgba(2, 6, 23, 0.48);
  border: 1px solid rgba(34, 211, 238, 0.12);
  border-radius: 999px;
  transform: translateX(-50%);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.three-viewer :deep(.body-hotspot) {
  position: absolute;
  display: grid;
  width: 38px;
  height: 38px;
  padding: 0;
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 50%;
  outline: none;
  pointer-events: auto;
  place-items: center;
}

.three-viewer :deep(.body-hotspot__ring) {
  position: absolute;
  inset: 1px;
  border: 1.5px solid var(--spot-accent);
  border-radius: 50%;
  opacity: 0;
  animation: hotspot-pulse 2.4s ease-out infinite;
}

.three-viewer :deep(.body-hotspot__ring--delay) {
  animation-delay: 1.2s;
}

.three-viewer :deep(.body-hotspot__dot) {
  position: relative;
  z-index: 2;
  width: 11px;
  height: 11px;
  background: #ecfeff;
  border: 2px solid var(--spot-accent);
  border-radius: 50%;
  box-shadow:
    0 0 10px 4px color-mix(in srgb, var(--spot-accent) 58%, transparent),
    0 0 26px 10px color-mix(in srgb, var(--spot-accent) 28%, transparent);
  animation: hotspot-breathe 1.9s ease-in-out infinite;
}

.three-viewer :deep(.body-hotspot.is-active .body-hotspot__dot) {
  background: var(--spot-accent);
  box-shadow:
    0 0 12px 5px color-mix(in srgb, var(--spot-accent) 72%, transparent),
    0 0 30px 12px color-mix(in srgb, var(--spot-accent) 38%, transparent);
}

.three-viewer :deep(.body-hotspot__tag) {
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  padding: 4px 9px;
  color: #e0f2fe;
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  background: rgba(2, 6, 23, 0.72);
  border: 1px solid color-mix(in srgb, var(--spot-accent) 48%, transparent);
  border-radius: 6px;
  transform: translateX(-50%);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.three-viewer :deep(.body-hotspot:hover .body-hotspot__tag),
.three-viewer :deep(.body-hotspot.is-active .body-hotspot__tag) {
  color: #ffffff;
  border-color: var(--spot-accent);
}

@keyframes hotspot-pulse {
  0% {
    opacity: 0.9;
    transform: scale(0.55);
  }
  100% {
    opacity: 0;
    transform: scale(2.6);
  }
}

@keyframes hotspot-breathe {
  0%, 100% {
    transform: scale(0.9);
  }
  50% {
    transform: scale(1.18);
  }
}

.viewer-hint__dot {
  width: 5px;
  height: 5px;
  background: #22d3ee;
  border-radius: 50%;
  box-shadow: 0 0 9px rgba(34, 211, 238, 0.9);
}

.three-viewer :deep(.chest-hotspot) {
  position: relative;
  display: grid;
  width: 32px;
  height: 32px;
  padding: 0;
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 50%;
  outline: none;
  pointer-events: auto;
  place-items: center;
  transform: translate(-50%, -50%);
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}

.three-viewer :deep(.chest-hotspot:hover) {
  transform: translate(-50%, -50%) scale(1.2);
}

.three-viewer :deep(.chest-core) {
  position: relative;
  z-index: 2;
  width: 9px;
  height: 9px;
  background: #ecfeff;
  border-radius: 50%;
  box-shadow:
    0 0 9px 4px rgba(165, 243, 252, 0.95),
    0 0 28px 10px rgba(34, 211, 238, 0.58);
  animation: chest-core 1.8s ease-in-out infinite;
}
.three-viewer :deep(.chest-ripple) {
  position: absolute;
  inset: 1px;
  border: 1px solid rgba(103, 232, 249, 0.82);
  border-radius: 50%;
  pointer-events: none;
  animation: chest-pulse 2.4s ease-out infinite;
}

.three-viewer :deep(.chest-ripple--2) {
  animation-delay: 0.8s;
}

.three-viewer :deep(.chest-ripple--3) {
  animation-delay: 1.6s;
}

.three-viewer :deep(.chest-label) {
  position: absolute;
  top: 50%;
  left: calc(100% + 9px);
  padding: 4px 7px;
  color: #a5f3fc;
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.08em;
  white-space: nowrap;
  background: rgba(2, 6, 23, 0.68);
  border: 1px solid rgba(34, 211, 238, 0.24);
  border-radius: 4px;
  transform: translateY(-50%);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.three-viewer :deep(.chest-hotspot:focus-visible)::after {
  position: absolute;
  inset: -7px;
  content: '';
  border: 1px dashed rgba(103, 232, 249, 0.72);
  border-radius: 50%;
}

.holo-telemetry {
  position: absolute;
  right: 30px;
  bottom: 18px;
  left: 30px;
  z-index: 7;
  display: flex;
  gap: 20px;
  align-items: center;
  justify-content: space-between;
  color: rgba(148, 163, 184, 0.8);
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 0.08em;
  pointer-events: none;
}

.holo-telemetry span {
  display: inline-flex;
  gap: 7px;
  align-items: center;
}

.holo-telemetry i {
  width: 6px;
  height: 6px;
  background: #22c55e;
  border-radius: 50%;
  box-shadow: 0 0 10px rgba(34, 197, 94, 0.9);
}

@keyframes load-spin {
  to { transform: rotate(360deg); }
}

@keyframes chest-core {
  0%, 100% { transform: scale(0.92); }
  50% { transform: scale(1.35); }
}

@keyframes chest-pulse {
  0% { opacity: 0.95; transform: scale(0.55); }
  100% { opacity: 0; transform: scale(3.9); }
}
.orbit-controls {
  position: absolute;
  top: 26px;
  right: 28px;
  z-index: 13;
  display: flex;
  flex-direction: row;
  gap: 8px;
  align-items: center;
  width: auto;
  padding: 9px 11px;
  background: rgba(15, 23, 42, 0.58);
  border: 1px solid rgba(103, 232, 249, 0.16);
  border-radius: 15px;
  box-shadow:
    0 18px 40px rgba(2, 6, 23, 0.38),
    inset 0 0 22px rgba(34, 211, 238, 0.035);
  backdrop-filter: blur(18px) saturate(1.25);
  -webkit-backdrop-filter: blur(18px) saturate(1.25);
}

.orbit-controls__title {
  margin: 0 6px 0 0;
  color: rgba(103, 232, 249, 0.86);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-align: center;
  white-space: nowrap;
}

.orbit-button {
  min-width: 36px;
  height: 38px;
  padding: 0 8px;
  color: #a5f3fc;
  font-family: var(--font-mono);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  background: rgba(6, 182, 212, 0.1);
  border: 1px solid rgba(103, 232, 249, 0.28);
  border-radius: 8px;
  transition:
    color 160ms ease,
    background 160ms ease,
    border-color 160ms ease,
    transform 160ms ease;
}

.orbit-button:hover {
  color: #ecfeff;
  background: rgba(6, 182, 212, 0.22);
  border-color: rgba(103, 232, 249, 0.55);
  transform: translateY(-1px);
}

.orbit-button--reset {
  color: #cbd5e1;
  font-size: 13px;
  letter-spacing: 0.05em;
}

.system-tabs {
  position: absolute;
  bottom: 92px;
  left: 28px;
  z-index: 13;
  display: flex;
  flex-direction: column;
  gap: 7px;
  width: 184px;
  padding: 12px 10px;
  background: rgba(15, 23, 42, 0.62);
  border: 1px solid rgba(103, 232, 249, 0.22);
  border-radius: 15px;
  box-shadow:
    0 18px 40px rgba(2, 6, 23, 0.38),
    inset 0 0 22px rgba(34, 211, 238, 0.035);
  backdrop-filter: blur(18px) saturate(1.25);
  -webkit-backdrop-filter: blur(18px) saturate(1.25);
}

.system-tabs__title {
  margin-bottom: 2px;
  color: rgba(103, 232, 249, 0.86);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-align: center;
}

.system-tab {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 9px;
  align-items: center;
  padding: 10px 9px;
  color: #cbd5e1;
  text-align: left;
  cursor: pointer;
  background: rgba(6, 182, 212, 0.06);
  border: 1px solid rgba(103, 232, 249, 0.18);
  border-radius: 9px;
  transition:
    color 160ms ease,
    background 160ms ease,
    border-color 160ms ease,
    transform 160ms ease,
    box-shadow 160ms ease;
}

.system-tab__icon {
  display: grid;
  width: 24px;
  height: 24px;
  color: var(--tab-accent);
  place-items: center;
}

.system-tab__icon svg {
  width: 100%;
  height: 100%;
}

.system-tab:hover {
  color: #f0fdfa;
  background: rgba(6, 182, 212, 0.16);
  border-color: color-mix(in srgb, var(--tab-accent) 48%, transparent);
  transform: translateX(2px);
}

.system-tab.is-active {
  color: #f0fdfa;
  background: color-mix(in srgb, var(--tab-accent) 16%, transparent);
  border-color: color-mix(in srgb, var(--tab-accent) 58%, transparent);
  box-shadow:
    0 0 16px color-mix(in srgb, var(--tab-accent) 18%, transparent),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.system-tab__label {
  overflow: hidden;
  font-size: 15px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lung-card {
  position: absolute;
  top: 50%;
  right: clamp(34px, 7vw, 110px);
  z-index: 14;
  width: min(380px, 33vw);
  min-width: 315px;
  max-height: calc(100vh - 210px);
  padding: 24px 24px 22px;
  overflow-x: hidden;
  overflow-y: auto;
  color: #e2e8f0;
  scrollbar-color: rgba(103, 232, 249, 0.28) transparent;
  scrollbar-width: thin;
  background:
    linear-gradient(145deg, rgba(30, 41, 59, 0.76), rgba(15, 23, 42, 0.68));
  border: 1px solid color-mix(in srgb, var(--system-accent, #67e8f9) 34%, transparent);
  border-radius: 17px;
  box-shadow:
    0 28px 70px rgba(2, 6, 23, 0.62),
    inset 0 0 38px rgba(34, 211, 238, 0.06),
    0 0 35px rgba(34, 211, 238, 0.1);
  transform: translateY(-50%);
  backdrop-filter: blur(20px) saturate(1.35);
  -webkit-backdrop-filter: blur(20px) saturate(1.35);
}

.lung-card::-webkit-scrollbar {
  width: 5px;
}

.lung-card::-webkit-scrollbar-thumb {
  background: rgba(103, 232, 249, 0.24);
  border-radius: 99px;
}

.lung-card::before {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 1px;
  content: '';
  background: linear-gradient(90deg, transparent, rgba(103, 232, 249, 0.78), transparent);
  box-shadow: 0 0 14px rgba(34, 211, 238, 0.45);
}

.card-line {
  position: absolute;
  top: 50%;
  right: 100%;
  width: clamp(42px, 5vw, 78px);
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(103, 232, 249, 0.55));
}

.card-corner {
  position: absolute;
  width: 18px;
  height: 18px;
  pointer-events: none;
  border-color: rgba(103, 232, 249, 0.72);
  border-style: solid;
}

.card-corner--tl {
  top: -1px;
  left: -1px;
  border-width: 2px 0 0 2px;
  border-radius: 17px 0 0;
}

.card-corner--br {
  right: -1px;
  bottom: -1px;
  border-width: 0 2px 2px 0;
  border-radius: 0 0 17px;
}

.card-anatomy {
  position: relative;
  margin: 0 0 15px;
  overflow: hidden;
  background: rgba(2, 6, 23, 0.5);
  border: 1px solid color-mix(in srgb, var(--system-accent, #67e8f9) 26%, transparent);
  border-radius: 12px;
}

.card-anatomy img {
  display: block;
  width: 100%;
  height: 160px;
  object-fit: cover;
  filter: saturate(0.82) contrast(1.06) brightness(0.82);
  transition: transform 600ms ease;
}

.card-anatomy:hover img {
  transform: scale(1.04);
}

.card-anatomy::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background:
    linear-gradient(180deg, transparent 42%, rgba(2, 6, 23, 0.82)),
    radial-gradient(circle at 50% 10%, rgba(34, 211, 238, 0.08), transparent 54%);
}

.card-anatomy__tag {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
  padding: 3px 7px;
  color: color-mix(in srgb, var(--system-accent, #67e8f9) 78%, #ffffff);
  font-family: var(--font-mono);
  font-size: 7px;
  letter-spacing: 0.08em;
  background: rgba(2, 6, 23, 0.66);
  border: 1px solid color-mix(in srgb, var(--system-accent, #67e8f9) 34%, transparent);
  border-radius: 999px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.card-anatomy figcaption {
  position: absolute;
  right: 11px;
  bottom: 9px;
  left: 11px;
  z-index: 2;
  color: #e2e8f0;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.card-kicker {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  padding: 4px 9px;
  color: color-mix(in srgb, var(--system-accent, #67e8f9) 82%, #ffffff);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.08em;
  background: color-mix(in srgb, var(--system-accent, #22d3ee) 9%, transparent);
  border: 1px solid color-mix(in srgb, var(--system-accent, #22d3ee) 26%, transparent);
  border-radius: 999px;
}

.spot-content {
  display: flex;
  flex-direction: column;
}

.spot-media {
  position: relative;
  margin: 14px 0 0;
  overflow: hidden;
  background: rgba(2, 6, 23, 0.55);
  border: 1px solid color-mix(in srgb, var(--system-accent, #67e8f9) 38%, transparent);
  border-radius: 12px;
}

.spot-media :deep(.el-image) {
  display: block;
  width: 100%;
  height: 160px;
}

.spot-media :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: saturate(1.05) contrast(1.06);
  transition: transform 500ms ease;
}

.spot-media:hover :deep(.el-image__inner) {
  transform: scale(1.04);
}

.spot-media figcaption {
  padding: 7px 10px;
  color: color-mix(in srgb, var(--system-accent, #67e8f9) 76%, #ffffff);
  font-size: 12px;
  font-weight: 600;
  background: rgba(2, 6, 23, 0.55);
}

.spot-content p {
  margin: 12px 0 0;
  color: #e2e8f0 !important;
  font-size: 14px;
  line-height: 1.8;
}

.spot-fade-enter-active,
.spot-fade-leave-active {
  transition:
    opacity 220ms ease,
    transform 220ms ease;
}

.spot-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.spot-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.kicker-dot {
  width: 5px;
  height: 5px;
  background: var(--system-accent, #22d3ee);
  border-radius: 50%;
  box-shadow: 0 0 9px color-mix(in srgb, var(--system-accent, #22d3ee) 90%, transparent);
}
.lung-card h2 {
  margin: 16px 0 0;
  color: #f0fdfa;
  font-size: 24px;
  font-weight: 650;
  line-height: 1.25;
  letter-spacing: -0.025em;
  text-shadow: 0 0 20px rgba(34, 211, 238, 0.18);
}

.lung-card > p {
  margin: 12px 0 0;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.9;
}

.card-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 19px;
}

.card-metrics > div {
  display: flex;
  flex-direction: column;
  padding: 9px 10px;
  line-height: 1.4;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 9px;
}

.card-metrics span {
  color: #cbd5e1;
  font-size: 13px;
}

.card-metrics strong {
  margin-top: 4px;
  color: #f0fdfa;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
}

.alveolus-demo {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 12px;
  margin-top: 16px;
  background: rgba(2, 6, 23, 0.3);
  border: 1px solid color-mix(in srgb, var(--system-accent, #22d3ee) 20%, transparent);
  border-radius: 12px;
}

.alveolus-visual {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  gap: 5px;
  align-items: center;
}

.alveolus {
  position: relative;
  width: 86px;
  height: 86px;
  overflow: hidden;
  background:
    radial-gradient(circle at 35% 30%, rgba(103, 232, 249, 0.12), rgba(2, 6, 23, 0.55));
  border: 1px solid rgba(103, 232, 249, 0.55);
  border-radius: 50%;
  box-shadow:
    inset 0 0 22px rgba(34, 211, 238, 0.15),
    0 0 18px rgba(34, 211, 238, 0.12);
}

.alveolus__liquid {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(56, 189, 248, 0.18), rgba(56, 189, 248, 0.74));
  transform: translateY(100%);
  animation: alveolus-fill 4.6s ease-in-out infinite;
}

.alveolus__liquid::before {
  position: absolute;
  top: -6px;
  left: -10%;
  width: 120%;
  height: 13px;
  content: '';
  background: rgba(186, 230, 253, 0.55);
  border-radius: 50%;
  filter: blur(1px);
}

.alveolus__bubble {
  position: absolute;
  width: 5px;
  height: 5px;
  background: rgba(186, 230, 253, 0.82);
  border-radius: 50%;
  opacity: 0;
  animation: alveolus-bubble 3.4s ease-in infinite;
}

.alveolus__bubble--1 {
  bottom: 16%;
  left: 30%;
  animation-delay: -0.4s;
}

.alveolus__bubble--2 {
  right: 27%;
  bottom: 12%;
  width: 4px;
  height: 4px;
  animation-delay: -1.6s;
}

.alveolus__bubble--3 {
  bottom: 18%;
  left: 54%;
  width: 3px;
  height: 3px;
  animation-delay: -2.4s;
}

.alveolus-visual__caption {
  color: rgba(148, 163, 184, 0.7);
  font-family: var(--font-mono);
  font-size: 7px;
  letter-spacing: 0.1em;
}

.alveolus-copy {
  min-width: 0;
}

.alveolus-copy strong {
  color: #e2e8f0;
  font-size: 11px;
  font-weight: 650;
}

.alveolus-copy p {
  margin: 5px 0 0;
  color: #94a3b8;
  font-size: 10px;
  line-height: 1.7;
}

@keyframes alveolus-fill {
  0% {
    transform: translateY(100%);
  }

  18% {
    transform: translateY(92%);
  }

  68% {
    transform: translateY(0);
  }

  86% {
    transform: translateY(0);
  }

  100% {
    transform: translateY(100%);
  }
}

@keyframes alveolus-bubble {
  0% {
    opacity: 0;
    transform: translateY(0) scale(0.8);
  }

  28% {
    opacity: 0.85;
  }

  100% {
    opacity: 0;
    transform: translateY(-58px) scale(1.15);
  }
}

.card-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 18px;
}

.card-actions .card-action {
  margin-top: 0;
}

.card-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 12px 15px;
  margin-top: 18px;
  color: #06202a;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  background: linear-gradient(110deg, #67e8f9, #22d3ee 56%, #38bdf8);
  border: 0;
  border-radius: 10px;
  box-shadow:
    0 10px 26px rgba(34, 211, 238, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.45);
  transition:
    transform 180ms ease,
    box-shadow 180ms ease,
    filter 180ms ease;
}

.card-action:hover {
  filter: brightness(1.08);
  box-shadow: 0 14px 34px rgba(34, 211, 238, 0.34);
  transform: translateY(-2px);
}

.card-action svg {
  transition: transform 180ms ease;
}

.card-action:hover svg {
  transform: translateX(4px);
}

.card-action--ghost {
  color: color-mix(in srgb, var(--system-accent, #67e8f9) 82%, #ffffff);
  background: color-mix(in srgb, var(--system-accent, #22d3ee) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--system-accent, #22d3ee) 34%, transparent);
  box-shadow: none;
}

.card-action--ghost:hover {
  background: color-mix(in srgb, var(--system-accent, #22d3ee) 16%, transparent);
  border-color: color-mix(in srgb, var(--system-accent, #22d3ee) 54%, transparent);
  box-shadow: 0 8px 20px color-mix(in srgb, var(--system-accent, #22d3ee) 14%, transparent);
  filter: none;
}

.holo-card-enter-active,
.holo-card-leave-active {
  transition:
    opacity 280ms ease,
    transform 320ms cubic-bezier(0.22, 1, 0.36, 1);
}

.holo-card-enter-from,
.holo-card-leave-to {
  opacity: 0;
  transform: translateY(-50%) translateX(28px) scale(0.97);
}

:global(.holo-compare-dialog.el-dialog) {
  overflow: hidden;
  background:
    linear-gradient(145deg, rgba(15, 23, 42, 0.97), rgba(2, 6, 23, 0.96));
  border: 1px solid rgba(103, 232, 249, 0.26);
  border-radius: 18px;
  box-shadow:
    0 30px 80px rgba(2, 6, 23, 0.7),
    0 0 40px rgba(34, 211, 238, 0.12);
}

:global(.holo-compare-dialog .el-dialog__title) {
  color: #f0fdfa;
  font-size: 16px;
  font-weight: 650;
}

:global(.holo-compare-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: #94a3b8;
}

:global(.holo-compare-dialog .el-dialog__body) {
  color: #cbd5e1;
}

.compare-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.compare-figure {
  margin: 0;
  overflow: hidden;
  background: rgba(2, 6, 23, 0.55);
  border: 1px solid rgba(103, 232, 249, 0.2);
  border-radius: 14px;
}

.compare-figure--pathology {
  border-color: rgba(248, 113, 113, 0.32);
}

.compare-figure img {
  display: block;
  width: 100%;
  height: 280px;
  object-fit: cover;
  filter: saturate(0.78) contrast(1.08) brightness(0.86);
}

.compare-figure figcaption {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 11px 13px;
}

.compare-figure figcaption strong {
  color: #f0fdfa;
  font-size: 12px;
  font-weight: 650;
}

.compare-figure figcaption span {
  color: #94a3b8;
  font-size: 10px;
}

.compare-figure--pathology figcaption strong {
  color: #fecaca;
}

.compare-note {
  margin: 14px 0 0;
  color: #94a3b8;
  font-size: 10px;
  line-height: 1.75;
}
@media (max-width: 1280px) {
  .lung-card {
    right: 28px;
    width: 320px;
    min-width: 0;
  }

  .card-line {
    display: none;
  }
}

@media (max-width: 980px) {
  .holo-scene {
    min-height: 860px;
    height: calc(100vh - 180px);
  }

  .viewer-stage {
    bottom: 260px;
  }

  .holo-heading {
    max-width: calc(100% - 44px);
  }

  .orbit-controls {
    top: auto;
    bottom: 330px;
    left: 18px;
    flex-direction: row;
    width: auto;
    transform: none;
  }

  .orbit-controls__title {
    display: none;
  }

  .orbit-button {
    min-width: 38px;
  }

  .system-tabs {
    top: 150px;
    bottom: auto;
    left: 18px;
    flex-direction: row;
    flex-wrap: wrap;
    width: auto;
    max-width: calc(100% - 36px);
    padding: 8px;
  }

  .system-tabs__title {
    display: none;
  }

  .system-tab {
    grid-template-columns: 1fr;
    padding: 8px 10px;
  }

  .system-tab__index {
    display: none;
  }

  .lung-card {
    top: auto;
    right: 50%;
    bottom: 58px;
    width: min(430px, calc(100% - 36px));
    max-height: min(64vh, 580px);
    transform: translateX(50%);
  }

  .holo-card-enter-from,
  .holo-card-leave-to {
    opacity: 0;
    transform: translateX(50%) translateY(24px) scale(0.97);
  }

  .holo-telemetry span:nth-child(2) {
    display: none;
  }

  .viewer-hint {
    bottom: 25px;
  }
}

@media (max-width: 620px) {
  .holo-scene {
    min-height: 840px;
  }

  .holo-heading {
    top: 22px;
    left: 21px;
  }

  .holo-heading span {
    font-size: 10px;
  }

  .system-tabs {
    top: 136px;
    gap: 5px;
  }

  .system-tab {
    padding: 7px 8px;
  }

  .system-tab__label {
    font-size: 9px;
  }

  .lung-card {
    bottom: 48px;
    padding: 23px 21px 20px;
  }

  .compare-grid {
    grid-template-columns: 1fr;
  }

  .compare-figure img {
    height: 200px;
  }

  .holo-telemetry {
    right: 20px;
    bottom: 16px;
    left: 20px;
    justify-content: center;
  }

  .holo-telemetry span:nth-child(2),
  .holo-telemetry span:last-child {
    display: none;
  }

  .viewer-hint {
    max-width: calc(100% - 36px);
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

@media (prefers-reduced-motion: reduce) {
  .holo-grid,
  .holo-scanline,
  .holo-particle,
  .load-ring,
  .three-viewer :deep(.chest-core),
  .three-viewer :deep(.chest-ripple),
  .alveolus__bubble {
    animation: none !important;
  }

  .alveolus__liquid {
    animation: none !important;
    transform: translateY(24%);
  }
}

/* 浅色主题下的全息页面适配 */
html:not(.dark) .holo-scene {
  background:
    radial-gradient(circle at 50% 40%, rgba(6, 182, 212, 0.08), transparent 32%),
    radial-gradient(circle at 82% 65%, rgba(37, 99, 235, 0.05), transparent 32%),
    linear-gradient(155deg, #f8fbff 0%, #eaf3fa 52%, #dceef8 100%) !important;
  border-color: rgba(15, 39, 66, 0.1);
  box-shadow: inset 0 0 100px rgba(148, 163, 184, 0.08);
}

html:not(.dark) .holo-heading h1 {
  color: var(--color-text) !important;
  text-shadow: none;
}

html:not(.dark) .holo-heading p {
  color: #0891b2;
}

html:not(.dark) .holo-heading span,
html:not(.dark) .holo-telemetry {
  color: var(--color-text-muted) !important;
}

html:not(.dark) .three-viewer :deep(canvas) {
  filter: contrast(1.1) saturate(1.16);
}

html:not(.dark) .three-viewer :deep(.body-hotspot__tag) {
  color: #0f2742;
  background: rgba(255, 255, 255, 0.92);
}

html:not(.dark) .three-viewer :deep(.body-hotspot__dot) {
  background: #ffffff;
}

html:not(.dark) .viewer-hint,
html:not(.dark) .orbit-controls,
html:not(.dark) .load-overlay {
  background: rgba(255, 255, 255, 0.82) !important;
  border-color: rgba(15, 39, 66, 0.14) !important;
  box-shadow: 0 14px 36px rgba(30, 64, 175, 0.1);
}

html:not(.dark) .viewer-hint {
  color: #334155;
}

html:not(.dark) .orbit-controls {
  border-color: rgba(8, 145, 178, 0.38) !important;
}

html:not(.dark) .orbit-controls__title {
  color: #0e7490;
}

html:not(.dark) .orbit-button {
  color: #ecfeff;
  font-weight: 700;
  background: #0e7490;
  border-color: #0e7490;
}

html:not(.dark) .orbit-button:hover {
  color: #ffffff;
  background: #0891b2;
  border-color: #0891b2;
}

html:not(.dark) .orbit-button--reset {
  color: #ecfeff;
  background: #155e75;
  border-color: #155e75;
}

html:not(.dark) .load-overlay strong {
  color: #0f2742;
}

html:not(.dark) .lung-card {
  color: #1e293b !important;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(236, 254, 255, 0.86)) !important;
  border-color: rgba(8, 145, 178, 0.32) !important;
  box-shadow:
    0 28px 70px rgba(30, 64, 175, 0.14),
    inset 0 0 38px rgba(6, 182, 212, 0.04);
}

html:not(.dark) .lung-card h2 {
  color: #1e293b !important;
  text-shadow: none;
}

/* 正文实际渲染在 .spot-content p 内，必须强制深色，否则白底浅字根本看不清 */
html:not(.dark) .spot-content p {
  color: #1e293b !important;
}

html:not(.dark) .card-kicker {
  color: #0e7490 !important;
}

html:not(.dark) .spot-media figcaption {
  color: #e0f2fe !important;
}

html:not(.dark) .card-metrics > div {
  background: rgba(255, 255, 255, 0.78);
  border-color: rgba(15, 39, 66, 0.1);
}

html:not(.dark) .card-metrics strong {
  color: #1e293b !important;
}

html:not(.dark) .card-metrics span {
  color: #475569 !important;
}

html:not(.dark) .three-viewer :deep(.chest-label) {
  color: #0e7490;
  background: rgba(255, 255, 255, 0.82);
  border-color: rgba(8, 145, 178, 0.22);
}

html:not(.dark) .system-tabs {
  background: rgba(255, 255, 255, 0.82);
  border-color: rgba(15, 39, 66, 0.12);
  box-shadow: 0 14px 36px rgba(30, 64, 175, 0.1);
}

html:not(.dark) .system-tabs__title {
  color: #0891b2;
}

html:not(.dark) .system-tab {
  color: #475569;
  background: rgba(6, 182, 212, 0.04);
  border-color: rgba(8, 145, 178, 0.14);
}

html:not(.dark) .system-tab:hover {
  color: #0f2742;
  background: rgba(6, 182, 212, 0.1);
}

html:not(.dark) .system-tab.is-active {
  color: #0f2742;
}

html:not(.dark) .card-anatomy {
  background: rgba(255, 255, 255, 0.68);
}

html:not(.dark) .card-anatomy figcaption {
  color: #0f2742;
}

html:not(.dark) .alveolus-demo {
  background: rgba(255, 255, 255, 0.6);
}

html:not(.dark) .alveolus {
  background:
    radial-gradient(circle at 35% 30%, rgba(6, 182, 212, 0.12), rgba(255, 255, 255, 0.72));
  border-color: rgba(8, 145, 178, 0.36);
}

html:not(.dark) .alveolus-copy strong {
  color: #334155;
}

html:not(.dark) .alveolus-copy p {
  color: #64748b;
}

html:not(.dark) .card-action--ghost {
  color: #0e7490;
  background: rgba(6, 182, 212, 0.06);
  border-color: rgba(8, 145, 178, 0.24);
}

:global(html:not(.dark) .holo-compare-dialog.el-dialog) {
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(236, 254, 255, 0.96));
  border-color: rgba(8, 145, 178, 0.2);
  box-shadow:
    0 30px 80px rgba(30, 64, 175, 0.18),
    0 0 40px rgba(6, 182, 212, 0.08);
}

:global(html:not(.dark) .holo-compare-dialog .el-dialog__title) {
  color: #0f2742;
}

:global(html:not(.dark) .holo-compare-dialog .el-dialog__body) {
  color: #475569;
}

html:not(.dark) .compare-figure figcaption strong {
  color: #0f2742;
}

html:not(.dark) .compare-figure figcaption span,
html:not(.dark) .compare-note {
  color: #64748b;
}

html:not(.dark) .compare-figure--pathology figcaption strong {
  color: #b91c1c;
}</style>
