import { computed, ref } from 'vue'

const THEME_KEY = 'pneumonia_theme'
const theme = ref('light')

function readStoredTheme() {
  try {
    return localStorage.getItem(THEME_KEY)
  } catch {
    return null
  }
}

function applyTheme(nextTheme) {
  const normalized = nextTheme === 'dark' ? 'dark' : 'light'
  theme.value = normalized
  document.documentElement.classList.toggle('dark', normalized === 'dark')
  document.documentElement.dataset.theme = normalized

  const themeMeta = document.querySelector('meta[name="theme-color"]')
  if (themeMeta) {
    themeMeta.setAttribute('content', normalized === 'dark' ? '#0F172A' : '#F4F8FC')
  }

  try {
    localStorage.setItem(THEME_KEY, normalized)
  } catch {
    // 忽略隐私模式下的存储异常
  }
}

export function initTheme() {
  const stored = readStoredTheme()
  applyTheme(stored === 'dark' ? 'dark' : 'light')
}

export function useTheme() {
  const isDark = computed(() => theme.value === 'dark')

  function toggleTheme() {
    applyTheme(isDark.value ? 'light' : 'dark')
  }

  function setTheme(nextTheme) {
    applyTheme(nextTheme)
  }

  return {
    theme,
    isDark,
    toggleTheme,
    setTheme,
  }
}