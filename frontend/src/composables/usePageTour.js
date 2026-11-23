import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'

const TOUR_CLASS = 'custom-tour-popover'
let activeTour = null

function buildTour({ storageKey, steps, isDark }) {
  return driver({
    showProgress: true,
    progressText: '第 {{current}} 步 / 共 {{total}} 步',
    nextBtnText: '下一步',
    prevBtnText: '上一步',
    doneBtnText: '完成',
    showButtons: ['next', 'previous'],
    stagePadding: 8,
    stageRadius: 12,
    overlayColor: isDark ? 'rgba(2, 6, 23, 0.82)' : 'rgba(2, 6, 23, 0.62)',
    popoverClass: TOUR_CLASS,
    steps,
    onPopoverRender(popover) {
      if (!popover.footer || popover.footer.querySelector('.custom-tour-skip')) {
        return
      }

      const skipButton = document.createElement('button')
      skipButton.type = 'button'
      skipButton.className = 'custom-tour-skip'
      skipButton.textContent = '跳过引导'
      skipButton.addEventListener('click', () => {
        activeTour?.destroy()
      })
      popover.footer.insertBefore(skipButton, popover.footer.firstChild)
    },
    onDestroyed() {
      if (storageKey) {
        localStorage.setItem(storageKey, 'true')
      }
      activeTour = null
    },
  })
}

export function startPageTour({ storageKey, steps, isDark = false }) {
  const availableSteps = (steps || []).filter(
    (step) => step.element && document.querySelector(step.element),
  )

  if (!availableSteps.length) return null

  if (activeTour) {
    activeTour.destroy()
    activeTour = null
  }

  activeTour = buildTour({
    storageKey,
    steps: availableSteps,
    isDark,
  })
  activeTour.drive()
  return activeTour
}

export function startPageTourOnce({
  storageKey,
  steps,
  isDark = false,
  delay = 600,
}) {
  if (!storageKey || localStorage.getItem(storageKey) === 'true') return null

  return window.setTimeout(() => {
    if (localStorage.getItem(storageKey) === 'true') return
    startPageTour({ storageKey, steps, isDark })
  }, delay)
}

export function stopPageTour() {
  if (activeTour) {
    activeTour.destroy()
    activeTour = null
  }
}

export function onPageTourRequest(callback, path) {
  const handler = (event) => {
    if (path && event.detail?.path && event.detail.path !== path) return
    callback()
  }
  window.addEventListener('pneumonia:start-page-tour', handler)
  return () => {
    window.removeEventListener('pneumonia:start-page-tour', handler)
  }
}

export function requestPageTour() {
  window.dispatchEvent(
    new CustomEvent('pneumonia:start-page-tour', {
      detail: { path: window.location.pathname },
    }),
  )
}
