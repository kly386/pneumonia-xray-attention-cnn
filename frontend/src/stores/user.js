import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const TOKEN_KEY = 'pneumonia_access_token'
export const USER_KEY = 'pneumonia_user'
export const EXPIRES_AT_KEY = 'pneumonia_expires_at'

function readUser() {
  try {
    const raw = sessionStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function readTokenExpiry(token) {
  if (!token) return 0
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return Number(payload.exp || 0) * 1000
  } catch {
    return 0
  }
}

export const useUserStore = defineStore('user', () => {
  const initialToken = sessionStorage.getItem(TOKEN_KEY) || ''
  const storedExpiry = Number(sessionStorage.getItem(EXPIRES_AT_KEY) || 0)
  const tokenExpiry = storedExpiry || readTokenExpiry(initialToken)

  const token = ref(initialToken)
  const user = ref(readUser())
  const expiresAt = ref(tokenExpiry)

  const isAuthenticated = computed(() => {
    if (!token.value) return false
    return !expiresAt.value || expiresAt.value > Date.now()
  })

  const displayName = computed(
    () => user.value?.full_name || user.value?.username || '医生',
  )
  const doctorTitle = computed(() => user.value?.title || '医疗演示账号')
  const doctorAffiliation = computed(() => {
    const parts = [user.value?.department, user.value?.hospital].filter(Boolean)
    return parts.join(' · ')
  })
  const doctorLicense = computed(() => user.value?.license_no || '')
  const role = computed(() => user.value?.role || 'DOCTOR')

  function updateUser(userData) {
    if (!userData) return
    user.value = { ...(user.value || {}), ...userData }
    sessionStorage.setItem(USER_KEY, JSON.stringify(user.value))
  }

  function setSession(payload) {
    const accessToken = payload.accessToken ?? payload.access_token ?? ''
    const expiresIn = Number(payload.expiresIn ?? payload.expires_in ?? 7200)
    const userData = payload.user ?? null

    token.value = accessToken
    user.value = userData
    expiresAt.value = Date.now() + expiresIn * 1000

    sessionStorage.setItem(TOKEN_KEY, accessToken)
    sessionStorage.setItem(EXPIRES_AT_KEY, String(expiresAt.value))

    if (userData) {
      sessionStorage.setItem(USER_KEY, JSON.stringify(userData))
    } else {
      sessionStorage.removeItem(USER_KEY)
    }
  }

  function clearSession() {
    token.value = ''
    user.value = null
    expiresAt.value = 0

    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(USER_KEY)
    sessionStorage.removeItem(EXPIRES_AT_KEY)
  }

  return {
    token,
    user,
    expiresAt,
    isAuthenticated,
    displayName,
    doctorTitle,
    doctorAffiliation,
    doctorLicense,
    role,
    setSession,
    updateUser,
    clearSession,
  }
})