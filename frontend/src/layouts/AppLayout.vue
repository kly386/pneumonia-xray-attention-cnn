<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'
import {
  Avatar,
  Clock,
  Cpu,
  EditPen,
  Expand,
  Monitor,
  Moon,
  Reading,
  Sunny,
  SwitchButton,
  TrendCharts,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import http from '@/api/http'
import AppDisclaimer from '@/components/AppDisclaimer.vue'
import { requestPageTour } from '@/composables/usePageTour'
import { useTheme } from '@/composables/useTheme'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { isDark, toggleTheme } = useTheme()
const sidebarCollapsed = ref(false)

function collapseSidebar() {
  sidebarCollapsed.value = true
}

function expandSidebar() {
  sidebarCollapsed.value = false
}

const profileVisible = ref(false)
const profileSaving = ref(false)


const profileForm = reactive({
  full_name: '',
  title: '',
  department: '',
  hospital: '',
  license_no: '',
  phone: '',
})

function openProfile() {
  const user = userStore.user || {}
  profileForm.full_name = user.full_name || ''
  profileForm.title = user.title || ''
  profileForm.department = user.department || ''
  profileForm.hospital = user.hospital || ''
  profileForm.license_no = user.license_no || ''
  profileForm.phone = user.phone || ''
  profileVisible.value = true
}

async function saveProfile() {
  if (profileSaving.value) return

  profileSaving.value = true

  try {
    const { data } = await http.patch('/auth/me', {
      full_name: profileForm.full_name.trim() || null,
      title: profileForm.title.trim() || null,
      department: profileForm.department.trim() || null,
      hospital: profileForm.hospital.trim() || null,
      license_no: profileForm.license_no.trim() || null,
      phone: profileForm.phone.trim() || null,
    })

    userStore.updateUser(data)
    profileVisible.value = false
    ElMessage.success('个人信息已保存')
  } catch (error) {
    ElMessage.error(error.userMessage || error.message || '保存失败，请稍后重试')
  } finally {
    profileSaving.value = false
  }
}

const navItems = [
  {
    label: '辅助筛查',
    caption: '影像上传与 AI 分析',
    path: '/workspace',
    icon: Monitor,
  },
  {
    label: '全息人体',
    caption: '肺部互动科普',
    path: '/holo-body',
    icon: Avatar,
  },
  {
    label: '历史记录',
    caption: '查看既往筛查结果',
    path: '/history',
    icon: Clock,
  },
  {
    label: '数据看板',
    caption: '筛查统计与趋势',
    path: '/dashboard',
    icon: TrendCharts,
  },
  {
    label: '模型信息',
    caption: '指标与实验结论',
    path: '/model-info',
    icon: Cpu,
  },
]

const pageTitle = computed(() => route.meta.title || '辅助筛查工作台')
const userInitial = computed(() => userStore.displayName.slice(0, 1).toUpperCase())

function logout() {
  userStore.clearSession()
  ElMessage.success('已安全退出')
  router.replace({ name: 'login' })
}
</script>

<template>
  <div class="app-layout" :class="{ 'is-sidebar-collapsed': sidebarCollapsed }">
    <aside class="layout-sidebar glass-panel">
      <RouterLink class="brand" to="/workspace" aria-label="返回辅助筛查工作台">
        <span class="brand__mark">
          <span class="brand__pulse"></span>
        </span>
        <span class="brand__text">
          <strong>PNEUMO·AI</strong>
          <small>智能辅助筛查系统</small>
        </span>
      </RouterLink>

      <div class="sidebar-section-label">WORKSPACE</div>

      <nav class="sidebar-nav" aria-label="主导航">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          active-class="is-active"
          @click="collapseSidebar"
        >
          <span class="nav-item__icon">
            <el-icon><component :is="item.icon" /></el-icon>
          </span>
          <span class="nav-item__copy">
            <strong>{{ item.label }}</strong>
            <small>{{ item.caption }}</small>
          </span>
        </RouterLink>
      </nav>

      <button
        class="sidebar-tutorial"
        type="button"
        title="查看当前页面的新手教程"
        @click="requestPageTour"
      >
        <span class="nav-item__icon">
          <el-icon><Reading /></el-icon>
        </span>
        <span class="nav-item__copy">
          <strong>新手教程</strong>
          <small>查看当前页面的操作引导</small>
        </span>
      </button>

      <div class="sidebar-spacer"></div>

      <div class="sidebar-status">
        <span class="status-dot"></span>
        <div>
          <strong>AI 服务在线</strong>
          <small>ResNet50 · ONNX FP32</small>
        </div>
      </div>

      <div class="sidebar-user">
        <button
          class="user-profile-button"
          type="button"
          title="填写 / 编辑个人信息"
          @click="openProfile"
        >
          <span class="user-avatar">{{ userInitial }}</span>
          <div class="user-copy">
            <strong>{{ userStore.displayName }}</strong>
            <small :title="userStore.doctorAffiliation">{{ userStore.doctorTitle }}</small>
          </div>
        </button>
        <button
          class="icon-button"
          type="button"
          title="退出登录"
          aria-label="退出登录"
          @click="logout"
        >
          <el-icon><SwitchButton /></el-icon>
        </button>
      </div>
    </aside>

    <section class="layout-main">
      <header class="layout-topbar">
        <div class="topbar-left">
          <button
            v-if="sidebarCollapsed"
            class="sidebar-toggle"
            type="button"
            title="展开导航栏"
            aria-label="展开导航栏"
            @click="expandSidebar"
          >
            <el-icon><Expand /></el-icon>
          </button>
          <div>
            <p class="topbar-eyebrow">MEDICAL AI CONSOLE</p>
            <h1 class="topbar-title">{{ pageTitle }}</h1>
          </div>
        </div>

        <div class="topbar-actions">
          <button
            class="theme-toggle"
            type="button"
            :title="isDark ? '切换到亮色模式' : '切换到暗色模式'"
            :aria-label="isDark ? '切换到亮色模式' : '切换到暗色模式'"
            @click="toggleTheme"
          >
            <el-icon>
              <Sunny v-if="isDark" />
              <Moon v-else />
            </el-icon>
          </button>

          <span class="model-chip">
            <span class="status-dot"></span>
            ResNet50 · 0.5101
          </span>
          <button
            class="topbar-user"
            type="button"
            :title="userStore.doctorAffiliation || '填写个人信息'"
            @click="openProfile"
          >
            <span class="user-avatar user-avatar--small">{{ userInitial }}</span>
            <span class="topbar-user__copy">
              <strong>{{ userStore.displayName }}</strong>
              <small>{{ userStore.doctorTitle }}</small>
            </span>
          </button>
        </div>
      </header>

      <nav class="mobile-nav" aria-label="移动端主导航">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="mobile-nav__item"
          active-class="is-active"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <main class="layout-content">
        <RouterView v-slot="{ Component, route: childRoute }">
          <Transition name="page" mode="out-in">
            <KeepAlive include="WorkspaceView">
              <component :is="Component" :key="childRoute.fullPath" />
            </KeepAlive>
          </Transition>
        </RouterView>
      </main>

      <footer class="layout-footer">
        <AppDisclaimer compact />
        <p class="footer-meta">
          © 2026 PNEUMO·AI · 课程演示系统 · 模型结果仅供辅助筛查参考
        </p>
      </footer>
    </section>

    <el-dialog
      v-model="profileVisible"
      title="医生个人信息"
      width="min(640px, 92vw)"
      class="profile-dialog"
      append-to-body
    >
      <div class="profile-form">
        <div class="profile-identity">
          <span class="user-avatar">{{ userInitial }}</span>
          <div class="profile-identity__copy">
            <strong>{{ userStore.displayName }}</strong>
            <small>
              登录账号 {{ userStore.user?.username || '—' }}
              <template v-if="userStore.user?.id"> · ID {{ userStore.user.id }}</template>
            </small>
            <small>{{ userStore.doctorAffiliation || '尚未填写执业医院与科室' }}</small>
          </div>
        </div>

        <p class="profile-hint">
          <el-icon><EditPen /></el-icon>
          以下资料由你自行填写，保存后将持久存储到系统数据库，并显示在左侧账号区域。
        </p>

        <div class="profile-grid">
          <label class="profile-field">
            <span>真实姓名</span>
            <el-input
              v-model="profileForm.full_name"
              size="large"
              placeholder="请输入姓名"
            />
          </label>
          <label class="profile-field">
            <span>职称 / 执业资质</span>
            <el-input
              v-model="profileForm.title"
              size="large"
              placeholder="如：主治医师"
            />
          </label>
          <label class="profile-field">
            <span>科室</span>
            <el-input
              v-model="profileForm.department"
              size="large"
              placeholder="如：呼吸内科"
            />
          </label>
          <label class="profile-field">
            <span>执业医院</span>
            <el-input
              v-model="profileForm.hospital"
              size="large"
              placeholder="请输入医院名称"
            />
          </label>
          <label class="profile-field">
            <span>执业证书编号</span>
            <el-input
              v-model="profileForm.license_no"
              size="large"
              placeholder="请输入证书编号"
            />
          </label>
          <label class="profile-field">
            <span>联系电话（选填）</span>
            <el-input
              v-model="profileForm.phone"
              size="large"
              placeholder="请输入联系电话"
            />
          </label>
        </div>
      </div>

      <template #footer>
        <el-button size="large" @click="profileVisible = false">取消</el-button>
        <el-button
          type="primary"
          size="large"
          :loading="profileSaving"
          @click="saveProfile"
        >
          保存个人信息
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
<style scoped>
.app-layout {
  display: grid;
  grid-template-columns: 252px minmax(0, 1fr);
  min-height: 100vh;
  padding: 18px;
  gap: 0;
}

.layout-sidebar {
  position: sticky;
  top: 18px;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 36px);
  padding: 22px 16px 16px;
  overflow: hidden;
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 0 8px 24px;
  border-bottom: 1px solid var(--border-color);
}

.brand__mark {
  position: relative;
  display: grid;
  width: 42px;
  height: 42px;
  overflow: hidden;
  place-items: center;
  background: linear-gradient(
    145deg,
    color-mix(in srgb, var(--brand) 24%, transparent),
    color-mix(in srgb, var(--brand) 10%, transparent)
  );
  border: 1px solid color-mix(in srgb, var(--brand) 34%, transparent);
  border-radius: 13px;
  box-shadow: inset 0 0 18px color-mix(in srgb, var(--brand) 14%, transparent);
}

.brand__mark::before,
.brand__mark::after {
  position: absolute;
  content: '';
  background: var(--brand);
  border-radius: 2px;
  box-shadow: 0 0 10px color-mix(in srgb, var(--brand) 70%, transparent);
}

.brand__mark::before {
  width: 18px;
  height: 2px;
}

.brand__mark::after {
  width: 2px;
  height: 18px;
}

.brand__pulse {
  position: absolute;
  width: 28px;
  height: 1px;
  background: color-mix(in srgb, var(--brand) 26%, transparent);
  transform: rotate(-32deg);
}

.brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.brand__text strong {
  color: var(--color-text);
  font-size: 17px;
  letter-spacing: 0.06em;
}

.brand__text small {
  margin-top: 5px;
  color: var(--color-text-soft);
  font-size: 12px;
  font-weight: 500;
}

.sidebar-section-label {
  padding: 24px 10px 10px;
  color: var(--color-text-soft);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.nav-item {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 11px 10px;
  color: var(--color-text-soft);
  border: 1px solid transparent;
  border-radius: 13px;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast),
    transform var(--transition-fast);
}

.nav-item:hover {
  color: var(--text-primary);
  background: var(--surface-hover);
  transform: translateX(2px);
}

.nav-item.is-active {
  color: var(--text-primary);
  background:
    linear-gradient(
      90deg,
      color-mix(in srgb, var(--brand) 16%, transparent),
      color-mix(in srgb, var(--brand) 5%, transparent)
    );
  border-color: color-mix(in srgb, var(--brand) 24%, transparent);
  box-shadow: inset 3px 0 0 var(--brand);
}

.nav-item__icon {
  display: grid;
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  color: var(--color-text-soft);
  place-items: center;
  background: color-mix(in srgb, var(--text-secondary) 14%, transparent);
  border-radius: 10px;
  font-size: 18px;
}

.nav-item.is-active .nav-item__icon {
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 14%, transparent);
}

.nav-item__copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}

.nav-item__copy strong {
  color: var(--color-text);
  font-size: 14px;
  font-weight: 650;
}

.nav-item__copy small {
  margin-top: 3px;
  overflow: hidden;
  color: var(--color-text-soft);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-spacer {
  flex: 1;
}

.sidebar-tutorial {
  display: flex;
  gap: 12px;
  align-items: center;
  width: 100%;
  padding: 10px;
  margin-top: 10px;
  color: var(--color-text-soft);
  text-align: left;
  cursor: pointer;
  background: color-mix(in srgb, var(--brand) 6%, transparent);
  border: 1px dashed color-mix(in srgb, var(--brand) 28%, transparent);
  border-radius: 13px;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.sidebar-tutorial:hover {
  color: var(--color-text);
  background: color-mix(in srgb, var(--brand) 12%, transparent);
  border-color: color-mix(in srgb, var(--brand) 45%, transparent);
}

.sidebar-tutorial .nav-item__icon {
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 12%, transparent);
}

.sidebar-status {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 13px 12px;
  margin-bottom: 10px;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--success) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--success) 20%, transparent);
  border-radius: 12px;
}

.sidebar-status div {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.sidebar-status strong {
  color: var(--color-text);
  font-size: 12px;
  font-weight: 650;
}

.sidebar-status small {
  margin-top: 3px;
  color: var(--color-text-soft);
  font-size: 10px;
}

.status-dot {
  display: inline-block;
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  background: var(--success);
  border-radius: 50%;
  box-shadow: 0 0 12px color-mix(in srgb, var(--success) 82%, transparent);
}

.sidebar-user {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px 10px;
  background: color-mix(in srgb, var(--text-primary) 4%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 13px;
}

.user-avatar {
  display: grid;
  flex: 0 0 auto;
  width: 35px;
  height: 35px;
  color: var(--bg-card);
  font-size: 13px;
  font-weight: 700;
  background: linear-gradient(
    145deg,
    color-mix(in srgb, var(--brand) 72%, transparent),
    color-mix(in srgb, var(--brand) 42%, transparent)
  );
  border: 1px solid color-mix(in srgb, var(--brand) 38%, transparent);
  border-radius: 11px;
  place-items: center;
  box-shadow: 0 0 18px color-mix(in srgb, var(--brand) 18%, transparent);
}

.user-avatar--small {
  width: 30px;
  height: 30px;
  font-size: 11px;
  border-radius: 9px;
}

.user-copy {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}

.user-profile-button {
  display: flex;
  flex: 1;
  gap: 10px;
  align-items: center;
  min-width: 0;
  padding: 0;
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: 0;
}

.user-copy strong {
  overflow: hidden;
  color: var(--color-text);
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-copy small {
  margin-top: 2px;
  color: var(--color-text-soft);
  font-size: 10px;
}

.icon-button {
  display: grid;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  padding: 0;
  color: var(--color-text-muted);
  cursor: pointer;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 9px;
  place-items: center;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.icon-button:hover {
  color: var(--danger);
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-color: color-mix(in srgb, var(--danger) 22%, transparent);
}

.layout-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding-left: 22px;
}

.app-layout.is-sidebar-collapsed {
  grid-template-columns: minmax(0, 1fr);
}

.app-layout.is-sidebar-collapsed .layout-sidebar {
  display: none;
}

.app-layout.is-sidebar-collapsed .layout-main {
  padding-left: 0;
}

.topbar-left {
  display: flex;
  gap: 14px;
  align-items: center;
  min-width: 0;
}

.sidebar-toggle {
  display: grid;
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  padding: 0;
  color: var(--color-primary-strong);
  cursor: pointer;
  background: var(--surface-subtle);
  border: 1px solid var(--glass-border);
  border-radius: 11px;
  place-items: center;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast),
    transform var(--transition-fast);
}

.sidebar-toggle:hover {
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 12%, transparent);
  border-color: var(--glass-border-hover);
  transform: translateY(-1px);
}

.layout-topbar {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  min-height: 74px;
  padding: 12px 22px;
  background: var(--topbar-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.topbar-eyebrow {
  margin: 0 0 4px;
  color: var(--color-primary-strong);
  font-size: 11px;
  font-weight: 750;
  letter-spacing: 0.16em;
}

.topbar-title {
  margin: 0;
  color: var(--color-text);
  font-size: 22px;
  font-weight: 700;
  line-height: 1.25;
}

.topbar-actions {
  display: flex;
  gap: 16px;
  align-items: center;
}

.model-chip {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 7px 11px;
  color: var(--color-text-soft);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 550;
  background: color-mix(in srgb, var(--brand) 7%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 18%, transparent);
  border-radius: var(--radius-pill);
}

.topbar-user {
  display: flex;
  gap: 9px;
  align-items: center;
  padding: 0;
  color: var(--color-text);
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: 0;
}

.topbar-user__copy {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.topbar-user__copy strong {
  color: var(--color-text);
  font-size: 13px;
  font-weight: 650;
}

.topbar-user__copy small {
  color: var(--color-text-soft);
  font-size: 10px;
  font-weight: 500;
}

.mobile-nav {
  display: none;
}
.layout-content {
  flex: 1;
  min-width: 0;
  padding: 22px 2px 18px;
}

.layout-footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 2px 4px;
}

.footer-meta {
  margin: 0;
  color: var(--color-text-faint);
  font-size: 10px;
  text-align: right;
}

.profile-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

:deep(.profile-dialog .el-dialog__body) {
  padding-top: 12px;
}

.profile-identity {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 16px;
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--brand) 9%, transparent),
    color-mix(in srgb, var(--color-primary-strong) 5%, transparent)
  );
  border: 1px solid color-mix(in srgb, var(--brand) 22%, transparent);
  border-radius: 12px;
}

.profile-identity .user-avatar {
  width: 46px;
  height: 46px;
  font-size: 17px;
  border-radius: 13px;
}

.profile-identity__copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.5;
}

.profile-identity__copy strong {
  color: var(--color-text);
  font-size: 17px;
  font-weight: 700;
}

.profile-identity__copy small {
  color: var(--color-text-soft);
  font-size: 12px;
}

.profile-hint {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin: 0;
  padding: 12px 14px;
  color: var(--color-text-soft);
  font-size: 13px;
  line-height: 1.7;
  background: color-mix(in srgb, var(--brand) 7%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 20%, transparent);
  border-radius: 10px;
}

.profile-hint .el-icon {
  flex: 0 0 auto;
  margin-top: 3px;
  color: var(--brand);
}

.profile-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px 18px;
}

.profile-field {
  display: flex;
  flex-direction: column;
  gap: 9px;
  color: var(--color-text-soft);
  font-size: 13px;
  font-weight: 600;
}

@media (max-width: 560px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1080px) {
  .app-layout {
    grid-template-columns: 218px minmax(0, 1fr);
  }

  .brand__text small,
  .nav-item__copy small {
    display: none;
  }

  .topbar-actions {
    gap: 10px;
  }

  .model-chip {
    display: none;
  }
}

@media (max-width: 900px) {
  .app-layout {
    display: block;
    padding: 12px;
  }

  .layout-sidebar {
    display: none;
  }

  .layout-main {
    padding-left: 0;
  }

  .layout-topbar {
    min-height: 66px;
    padding: 10px 14px;
  }

  .topbar-title {
    font-size: 17px;
  }

  .topbar-user > span:last-child,
  .topbar-eyebrow {
    display: none;
  }

  .mobile-nav {
    display: flex;
    gap: 8px;
    padding: 10px 2px 0;
    overflow-x: auto;
  }

  .mobile-nav__item {
    display: inline-flex;
    gap: 7px;
    align-items: center;
    flex: 0 0 auto;
    padding: 8px 12px;
    color: var(--text-secondary);
    font-size: 11px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-pill);
  }

  .mobile-nav__item.is-active {
    color: var(--text-primary);
    background: color-mix(in srgb, var(--brand) 14%, transparent);
    border-color: color-mix(in srgb, var(--brand) 32%, transparent);
  }

  .layout-content {
    padding-top: 14px;
  }

  .footer-meta {
    text-align: left;
  }
}

@media (max-width: 560px) {
  .layout-topbar {
    align-items: flex-start;
  }

  .topbar-user {
    display: none;
  }
}

.theme-toggle {
  display: grid;
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  padding: 0;
  color: var(--color-primary-strong);
  cursor: pointer;
  background: var(--surface-subtle);
  border: 1px solid var(--glass-border);
  border-radius: 10px;
  place-items: center;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast),
    transform var(--transition-fast);
}

.theme-toggle:hover {
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 12%, transparent);
  border-color: var(--glass-border-hover);
  transform: translateY(-1px);
}</style>
