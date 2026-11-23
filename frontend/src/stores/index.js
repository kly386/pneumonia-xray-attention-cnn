import { createPinia } from 'pinia'

// 单例 Pinia 实例，方便路由守卫和 Axios 拦截器在组件外访问 Store。
export const pinia = createPinia()