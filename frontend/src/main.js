import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import '@/assets/base.css'
import '@/assets/main.css'

import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import { initTheme } from './composables/useTheme'
import router from './router'
import { pinia } from './stores'

initTheme()

const app = createApp(App)

app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')