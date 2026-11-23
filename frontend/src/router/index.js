import { createRouter, createWebHistory } from 'vue-router'

import { pinia } from '@/stores'
import { useUserStore } from '@/stores/user'


const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: {
      title: '登录',
      guestOnly: true,
    },
  },
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    meta: {
      requiresAuth: true,
    },
    children: [
      {
        path: '',
        redirect: { name: 'workspace' },
      },
      {
        path: 'workspace',
        name: 'workspace',
        component: () => import('@/views/WorkspaceView.vue'),
        meta: {
          title: '辅助筛查工作台',
        },
      },
      {
        path: 'holo-body',
        name: 'holo-body',
        component: () => import('@/views/HoloBody.vue'),
        meta: {
          title: '全息人体',
        },
      },
      {
        path: 'history',
        name: 'history',
        component: () => import('@/views/HistoryView.vue'),
        meta: {
          title: '历史记录',
        },
      },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: {
          title: '数据看板',
        },
      },
      {
        path: 'model-info',
        name: 'model-info',
        component: () => import('@/views/ModelInfoView.vue'),
        meta: {
          title: '模型信息',
        },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: {
      title: '页面不存在',
    },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior() {
    return { top: 0, behavior: 'smooth' }
  },
})

router.beforeEach((to) => {
  const userStore = useUserStore(pinia)

  if (userStore.token && !userStore.isAuthenticated) {
    userStore.clearSession()
  }

  if (to.meta.requiresAuth && !userStore.isAuthenticated) {
    return {
      name: 'login',
      query: {
        redirect: to.fullPath,
      },
    }
  }

  if (to.meta.guestOnly && userStore.isAuthenticated) {
    return { name: 'workspace' }
  }

  return true
})

router.afterEach((to) => {
  document.title = to.meta.title
    ? `${to.meta.title} | 肺炎 X 光片智能辅助诊断系统`
    : '肺炎 X 光片智能辅助诊断系统'
})

export default router