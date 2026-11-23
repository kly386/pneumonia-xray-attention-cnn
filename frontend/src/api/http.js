import axios from 'axios'

import router from '@/router'
import { pinia } from '@/stores'
import { TOKEN_KEY, useUserStore } from '@/stores/user'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 120000,
  headers: {
    Accept: 'application/json',
  },
})

let redirectingToLogin = false

http.interceptors.request.use(
  (config) => {
    const token = sessionStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status
    const backendMessage =
      typeof error.response?.data?.message === 'string'
        ? error.response.data.message
        : ''

    let message = backendMessage

    if (!message && error.code === 'ECONNABORTED') {
      message = '分析超时，请稍后重试或减少上传影像数量'
    } else if (!message && !error.response) {
      message = '无法连接后端服务，请确认后端已在 18080 端口启动'
    } else if (!message && [502, 503, 504].includes(status)) {
      message = '后端服务暂不可用，请确认 uvicorn 已正常启动'
    } else if (!message) {
      message = error.message || '请求失败，请稍后重试'
    }

    error.userMessage = message
    error.backendUnavailable = !error.response || [502, 503, 504].includes(status)

    if (status === 401) {
      const userStore = useUserStore(pinia)
      userStore.clearSession()

      const loginRequest = String(error.config?.url || '').includes('/auth/login')
      const alreadyOnLogin = router.currentRoute.value.name === 'login'

      if (!loginRequest && !alreadyOnLogin && !redirectingToLogin) {
        redirectingToLogin = true
        const redirect = router.currentRoute.value.fullPath

        try {
          await router.replace({
            name: 'login',
            query: { redirect },
          })
        } finally {
          redirectingToLogin = false
        }
      }
    }

    return Promise.reject(error)
  },
)

export default http