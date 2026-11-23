<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Avatar,
  Cpu,
  Lock,
  Monitor,
  OfficeBuilding,
  Refresh,
  TrendCharts,
  User,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import http from '@/api/http'
import AppDisclaimer from '@/components/AppDisclaimer.vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const LAST_USERNAME_KEY = 'pneumonia_last_username'

const formRef = ref()
const registerFormRef = ref()
const loading = ref(false)
const registering = ref(false)
const backendOnline = ref(null)
const mode = ref('login')

const captcha = reactive({
  id: '',
  image: '',
  loading: false,
})

const agreementVisible = ref(false)
const agreementRead = ref(false)
const agreementChecked = ref(false)
const agreementCountdown = ref(5)
let agreementTimer = null

const form = reactive({
  username: '',
  password: '',
  captcha_code: '',
})

const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  full_name: '',
  title: '',
  department: '',
  hospital: '',
  license_no: '',
  phone: '',
})

const titleOptions = [
  '主任医师',
  '副主任医师',
  '主治医师',
  '住院医师',
  '教授',
  '副教授',
  '研究员',
  '副研究员',
]

const departmentOptions = [
  '呼吸与危重症医学科',
  '呼吸内科',
  '感染科',
  '急诊科',
  '放射科',
  '儿科',
  '全科医学科',
  '重症医学科',
]

const rules = {
  username: [
    { required: true, message: '请输入账号', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
  ],
  captcha_code: [
    { required: true, message: '请输入图形验证码', trigger: 'blur' },
  ],
}

function validateConfirmPassword(_rule, value, callback) {
  if (!value) {
    callback(new Error('请再次输入密码'))
    return
  }
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
    return
  }
  callback()
}

const registerRules = {
  username: [
    { required: true, message: '请输入登录账号', trigger: 'blur' },
    { min: 3, max: 64, message: '账号长度为 3–64 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 72, message: '密码长度为 6–72 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, validator: validateConfirmPassword, trigger: 'blur' },
  ],
  full_name: [
    { required: true, message: '请输入真实姓名', trigger: 'blur' },
  ],
  title: [
    { required: true, message: '请输入职称', trigger: 'blur' },
  ],
  department: [
    { required: true, message: '请输入科室', trigger: 'blur' },
  ],
  hospital: [
    { required: true, message: '请输入执业医院', trigger: 'blur' },
  ],
  license_no: [
    { required: true, message: '请输入执业证书编号', trigger: 'blur' },
  ],
}

const features = [
  {
    icon: Monitor,
    title: '二分类辅助筛查',
    description: 'NORMAL / PNEUMONIA 概率输出',
  },
  {
    icon: TrendCharts,
    title: 'ResNet50 + ONNX',
    description: '测试集 Accuracy 97.43%',
  },
  {
    icon: Cpu,
    title: 'Grad-CAM 可解释性',
    description: '展示模型关注区域，不替代诊断',
  },
]

function resolveRedirect() {
  const redirect = route.query.redirect

  if (
    typeof redirect === 'string' &&
    redirect.startsWith('/') &&
    !redirect.startsWith('//') &&
    redirect !== '/login'
  ) {
    return redirect
  }

  return '/workspace'
}

function fillDemoAccount() {
  mode.value = 'login'
  form.username = 'doctor'
  form.password = '123456'
  formRef.value?.clearValidate()
}

function switchMode(nextMode) {
  if (loading.value || registering.value) return
  mode.value = nextMode
  formRef.value?.clearValidate()
  registerFormRef.value?.clearValidate()
}

async function handleRegister() {
  if (registering.value) return

  if (!agreementChecked.value) {
    ElMessage.warning('请先阅读并同意《系统使用与职责声明》')
    return
  }

  const valid = await registerFormRef.value?.validate().catch(() => false)
  if (!valid) return

  registering.value = true

  try {
    await http.post('/auth/register', {
      username: registerForm.username.trim(),
      password: registerForm.password,
      full_name: registerForm.full_name.trim(),
      title: registerForm.title.trim(),
      department: registerForm.department.trim(),
      hospital: registerForm.hospital.trim(),
      license_no: registerForm.license_no.trim(),
      phone: registerForm.phone.trim() || null,
    })

    form.username = registerForm.username.trim()
    form.password = ''
    localStorage.setItem(LAST_USERNAME_KEY, form.username)
    mode.value = 'login'
    ElMessage.success('注册成功，医生资料已保存，请登录')
  } catch (error) {
    ElMessage.error(error.userMessage || error.message || '注册失败，请稍后重试')
  } finally {
    registering.value = false
  }
}

async function loadCaptcha() {
  if (captcha.loading) return
  captcha.loading = true

  try {
    const { data } = await http.get('/auth/captcha')
    captcha.id = data.captcha_id
    captcha.image = data.image
    form.captcha_code = ''
  } catch (error) {
    captcha.id = ''
    captcha.image = ''
    ElMessage.error(
      error.userMessage || error.message || '验证码加载失败，请确认后端已启动',
    )
  } finally {
    captcha.loading = false
  }
}

function openAgreement() {
  agreementVisible.value = true
  startAgreementCountdown()
}

function startAgreementCountdown() {
  if (agreementRead.value) return

  clearInterval(agreementTimer)
  agreementCountdown.value = 5
  agreementChecked.value = false

  agreementTimer = setInterval(() => {
    agreementCountdown.value -= 1
    if (agreementCountdown.value <= 0) {
      clearInterval(agreementTimer)
      agreementTimer = null
      agreementCountdown.value = 0
      agreementRead.value = true
    }
  }, 1000)
}

function onAgreementChecked(value) {
  if (value && !agreementRead.value) {
    agreementChecked.value = false
    ElMessage.warning('请先完整阅读职责声明并停留 5 秒后再勾选')
  }
}

function onAgreementClosed() {
  if (agreementRead.value) return
  clearInterval(agreementTimer)
  agreementTimer = null
  agreementCountdown.value = 5
}

async function checkBackendStatus() {
  try {
    await http.get('/health', { timeout: 5000 })
    backendOnline.value = true
  } catch {
    backendOnline.value = false
  }
}

async function handleLogin() {
  if (loading.value) return

  if (!agreementChecked.value) {
    ElMessage.warning('请先阅读并同意《系统使用与职责声明》')
    return
  }

  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true

  try {
    const { data } = await http.post('/auth/login', {
      username: form.username.trim(),
      password: form.password,
      captcha_id: captcha.id,
      captcha_code: form.captcha_code.trim(),
    })

    if (!data?.access_token) {
      throw new Error('登录响应缺少访问令牌')
    }

    backendOnline.value = true
    userStore.setSession(data)
    localStorage.setItem(LAST_USERNAME_KEY, form.username.trim())
    ElMessage.success(
      `欢迎回来，${data.user?.full_name || data.user?.username || '医生'}医生`,
    )
    await router.replace(resolveRedirect())
  } catch (error) {
    if (error.backendUnavailable) {
      backendOnline.value = false
    }
    ElMessage.error(error.userMessage || error.message || '登录失败，请稍后重试')
    loadCaptcha()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const lastUsername = localStorage.getItem(LAST_USERNAME_KEY)
  if (lastUsername && !form.username) {
    form.username = lastUsername
  }
  checkBackendStatus()
  loadCaptcha()
})

onBeforeUnmount(() => {
  clearInterval(agreementTimer)
})
</script>

<template>
  <main class="login-page">
    <div class="login-shell glass-panel">
      <section class="login-brand">
        <div class="brand-line">
          <span class="brand-mark">
            <span class="brand-mark__cross"></span>
          </span>
          <div>
            <strong>PNEUMO·AI</strong>
            <small>MEDICAL SCREENING CONSOLE</small>
          </div>
        </div>

        <div class="brand-copy">
          <p class="page-eyebrow">AI-ASSISTED CHEST X-RAY</p>
          <h1>让每一次初筛<br /><span>更清晰、更可信</span></h1>
          <p>
            面向医生的肺炎 X 光片智能辅助筛查工作台，提供二分类概率、
            固定阈值判定与 Grad-CAM 模型关注区域参考。
          </p>
        </div>

        <div class="feature-list">
          <div v-for="item in features" :key="item.title" class="feature-item">
            <span class="feature-item__icon">
              <el-icon><component :is="item.icon" /></el-icon>
            </span>
            <div>
              <strong>{{ item.title }}</strong>
              <small>{{ item.description }}</small>
            </div>
          </div>
        </div>

        <div class="brand-status">
          <span
            class="status-dot"
            :class="{
              'is-offline': backendOnline === false,
              'is-checking': backendOnline === null,
            }"
          ></span>
          <span v-if="backendOnline === true">AI 推理服务在线</span>
          <span v-else-if="backendOnline === false">后端服务未连接</span>
          <span v-else>正在检查 AI 服务…</span>
          <span class="brand-status__divider"></span>
          <span>Threshold 0.5101</span>
        </div>
      </section>

      <section class="login-panel">
        <div class="login-panel__header">
          <span class="secure-pill">
            <span class="secure-pill__dot"></span>
            SECURE DOCTOR ACCESS
          </span>
          <h2>{{ mode === 'login' ? '医生登录' : '医生注册' }}</h2>
          <p v-if="mode === 'login'">
            使用已注册的医生账号进入辅助筛查工作台。
          </p>
          <p v-else>
            完善真实医生资料后将持久保存到系统数据库，用于筛查记录归属。
          </p>
        </div>

        <div class="auth-switch" role="tablist" aria-label="登录或注册">
          <button
            type="button"
            class="auth-switch__item"
            :class="{ 'is-active': mode === 'login' }"
            @click="switchMode('login')"
          >
            登录
          </button>
          <button
            type="button"
            class="auth-switch__item"
            :class="{ 'is-active': mode === 'register' }"
            @click="switchMode('register')"
          >
            注册
          </button>
        </div>

        <el-form
          v-if="mode === 'login'"
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          class="login-form"
          @submit.prevent="handleLogin"
        >
          <el-form-item label="账号" prop="username">
            <el-input
              v-model="form.username"
              :prefix-icon="User"
              size="large"
              placeholder="请输入账号"
              autocomplete="username"
              clearable
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              :prefix-icon="Lock"
              size="large"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <el-form-item label="图形验证码" prop="captcha_code">
            <div class="captcha-row">
              <el-input
                v-model="form.captcha_code"
                placeholder="请输入 4 位验证码"
                maxlength="4"
                autocomplete="off"
                @keyup.enter="handleLogin"
              />
              <button
                class="captcha-image"
                type="button"
                title="点击刷新验证码"
                :disabled="captcha.loading"
                @click="loadCaptcha"
              >
                <img v-if="captcha.image" :src="captcha.image" alt="图形验证码" />
                <span v-else>{{ captcha.loading ? '加载中…' : '点击获取' }}</span>
              </button>
            </div>
            <small class="captcha-hint">
              看不清？点击验证码图片刷新
            </small>
          </el-form-item>

          <div class="agreement-row">
            <el-checkbox
              v-model="agreementChecked"
              :disabled="!agreementRead"
              @change="onAgreementChecked"
            >
              我已阅读并同意
            </el-checkbox>
            <button type="button" class="agreement-link" @click="openAgreement">
              《系统使用与职责声明》
            </button>
            <span v-if="!agreementRead" class="agreement-countdown">
              {{ agreementVisible ? `请阅读 ${agreementCountdown}s` : '点击声明并停留 5 秒' }}
            </span>
          </div>

          <el-button
            class="login-button"
            type="primary"
            size="large"
            :loading="loading"
            :disabled="!agreementChecked"
            @click="handleLogin"
          >
            {{ loading ? '正在验证身份…' : '进入辅助筛查系统' }}
          </el-button>
        </el-form>

        <el-form
          v-else
          ref="registerFormRef"
          :model="registerForm"
          :rules="registerRules"
          label-position="top"
          class="login-form register-form"
          @submit.prevent="handleRegister"
        >
          <div class="register-stack">
            <el-form-item label="昵称 / 登录账号" prop="username">
              <el-input
                v-model="registerForm.username"
                :prefix-icon="User"
                placeholder="至少 3 个字符"
                autocomplete="username"
              />
            </el-form-item>

            <el-form-item label="登录密码" prop="password">
              <el-input
                v-model="registerForm.password"
                :prefix-icon="Lock"
                type="password"
                placeholder="至少 6 个字符"
                autocomplete="new-password"
                show-password
              />
            </el-form-item>

            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input
                v-model="registerForm.confirmPassword"
                :prefix-icon="Lock"
                type="password"
                placeholder="再次输入密码"
                autocomplete="new-password"
                show-password
              />
            </el-form-item>

            <el-form-item label="真实姓名" prop="full_name">
              <el-input
                v-model="registerForm.full_name"
                :prefix-icon="Avatar"
                placeholder="请输入真实姓名"
              />
            </el-form-item>
          </div>

          <div class="register-grid">
            <el-form-item label="职称 / 执业资质" prop="title">
              <el-select
                v-model="registerForm.title"
                filterable
                allow-create
                default-first-option
                placeholder="请选择或输入职称"
                style="width: 100%"
              >
                <el-option
                  v-for="item in titleOptions"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="科室" prop="department">
              <el-select
                v-model="registerForm.department"
                filterable
                allow-create
                default-first-option
                placeholder="请选择或输入科室"
                style="width: 100%"
              >
                <el-option
                  v-for="item in departmentOptions"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="执业医院" prop="hospital">
              <el-input
                v-model="registerForm.hospital"
                :prefix-icon="OfficeBuilding"
                placeholder="请输入医院名称"
              />
            </el-form-item>

            <el-form-item label="执业证书编号" prop="license_no">
              <el-input
                v-model="registerForm.license_no"
                placeholder="请输入医师执业证书编号"
              />
            </el-form-item>

            <el-form-item label="联系电话（选填）" prop="phone">
              <el-input
                v-model="registerForm.phone"
                placeholder="用于账号联系"
              />
            </el-form-item>
          </div>

          <div class="agreement-row">
            <el-checkbox
              v-model="agreementChecked"
              :disabled="!agreementRead"
              @change="onAgreementChecked"
            >
              我已阅读并同意
            </el-checkbox>
            <button type="button" class="agreement-link" @click="openAgreement">
              《系统使用与职责声明》
            </button>
            <span v-if="!agreementRead" class="agreement-countdown">
              {{ agreementVisible ? `请阅读 ${agreementCountdown}s` : '点击声明并停留 5 秒' }}
            </span>
          </div>

          <el-button
            class="login-button"
            type="primary"
            size="large"
            :loading="registering"
            :disabled="!agreementChecked"
            @click="handleRegister"
          >
            {{ registering ? '正在保存医生资料…' : '注册并保存医生资料' }}
          </el-button>
        </el-form>

        <div class="demo-account">
          <span>课程演示账号</span>
          <button type="button" @click="fillDemoAccount">
            doctor / 123456
          </button>
        </div>
      </section>
    </div>

    <div class="login-disclaimer">
      <AppDisclaimer />
    </div>

    <el-dialog
      v-model="agreementVisible"
      title="系统使用与职责声明"
      width="min(620px, 92vw)"
      :close-on-click-modal="false"
      append-to-body
      @closed="onAgreementClosed"
    >
      <div class="agreement-content">
        <p class="agreement-intro">
          在使用本课程演示系统前，请完整阅读以下声明。阅读满 5 秒后方可勾选同意。
        </p>
        <ol>
          <li>
            本系统用于《人工智能原理与实践》课程演示、教学与科研参考，
            不构成医疗器械或临床诊断工具。
          </li>
          <li>
            AI 仅输出 NORMAL / PNEUMONIA 二分类概率、固定阈值判定和 Grad-CAM
            关注区域，结果不得替代执业医师结合病史、体征、实验室检查和影像学作出的综合判断。
          </li>
          <li>
            医生须对最终筛查意见负责；不得仅凭系统结果作出诊断、治疗或用药决定。
          </li>
          <li>
            禁止上传含患者姓名、身份证号、住院号等可识别身份的信息；
            上传影像仅用于本地辅助筛查，不发送至第三方云服务。
          </li>
          <li>
            系统不解析 DICOM，不接入 PACS / HIS，不建立患者主索引，
            不提供挂号、住院、随访等业务流程。
          </li>
          <li>
            因误用、超范围使用或忽视人工复核造成的后果，由使用者自行承担；
            系统开发者与课程组不承担临床责任。
          </li>
        </ol>
        <p class="agreement-countdown-hint">
          <template v-if="!agreementRead">
            请在文档上停留阅读，剩余 <strong>{{ agreementCountdown }}</strong> 秒后可勾选同意。
          </template>
          <template v-else>
            已阅读满 5 秒，可以勾选同意并继续。
          </template>
        </p>
      </div>

      <template #footer>
        <el-button @click="agreementVisible = false">关闭</el-button>
        <el-button
          type="primary"
          :disabled="!agreementRead"
          @click="agreementChecked = true; agreementVisible = false"
        >
          我已阅读，同意
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>
<style scoped>
.login-page {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 100vh;
  padding: 30px;
}

.login-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(380px, 0.88fr);
  width: min(1180px, 100%);
  min-height: 650px;
  margin: 0 auto;
  overflow: hidden;
  border-radius: var(--radius-xl);
}

.login-brand {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: clamp(36px, 5vw, 62px);
  overflow: hidden;
  background:
    radial-gradient(circle at 18% 22%, rgba(6, 182, 212, 0.17), transparent 36%),
    radial-gradient(circle at 76% 84%, rgba(59, 130, 246, 0.15), transparent 38%),
    linear-gradient(145deg, rgba(2, 6, 23, 0.78), rgba(15, 23, 42, 0.72));
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

.login-brand::before {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background-image:
    linear-gradient(rgba(34, 211, 238, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.035) 1px, transparent 1px);
  background-size: 36px 36px;
  mask-image: radial-gradient(circle at 28% 30%, #000 0%, transparent 70%);
}

.login-brand::after {
  position: absolute;
  right: -80px;
  bottom: -110px;
  width: 330px;
  height: 330px;
  pointer-events: none;
  content: '';
  border: 1px solid rgba(34, 211, 238, 0.1);
  border-radius: 50%;
  box-shadow:
    0 0 0 50px rgba(6, 182, 212, 0.025),
    0 0 0 100px rgba(6, 182, 212, 0.018);
}

.brand-line {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 13px;
  align-items: center;
}

.brand-line > div {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.brand-line strong {
  font-size: 18px;
  letter-spacing: 0.08em;
}

.brand-line small {
  margin-top: 5px;
  color: var(--color-text-muted);
  font-size: 11px;
  letter-spacing: 0.16em;
}

.brand-mark {
  position: relative;
  display: grid;
  width: 47px;
  height: 47px;
  background: linear-gradient(145deg, rgba(6, 182, 212, 0.22), rgba(59, 130, 246, 0.12));
  border: 1px solid rgba(34, 211, 238, 0.34);
  border-radius: 14px;
  place-items: center;
  box-shadow: 0 0 24px rgba(6, 182, 212, 0.16);
}

.brand-mark__cross::before,
.brand-mark__cross::after {
  position: absolute;
  top: 50%;
  left: 50%;
  content: '';
  background: var(--color-primary-strong);
  border-radius: 2px;
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.7);
  transform: translate(-50%, -50%);
}

.brand-mark__cross::before {
  width: 20px;
  height: 2px;
}

.brand-mark__cross::after {
  width: 2px;
  height: 20px;
}

.brand-copy {
  position: relative;
  z-index: 1;
  max-width: 570px;
  margin-top: clamp(30px, 4vw, 52px);
  padding-top: 0;
}

.brand-copy h1 {
  margin: 0;
  color: #f8fafc;
  font-size: clamp(36px, 4.3vw, 59px);
  font-weight: 700;
  line-height: 1.12;
  letter-spacing: -0.045em;
}

.brand-copy h1 span {
  color: transparent;
  background: linear-gradient(90deg, #67e8f9, #60a5fa);
  background-clip: text;
  -webkit-background-clip: text;
}

.brand-copy > p:last-child {
  max-width: 540px;
  margin: 22px 0 0;
  color: var(--color-text-soft);
  font-size: 16px;
  line-height: 1.9;
}
.feature-list {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 10px;
  max-width: 570px;
  margin-top: 34px;
}

.feature-item {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
}

.feature-item__icon {
  display: grid;
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  color: var(--color-primary-strong);
  background: rgba(6, 182, 212, 0.08);
  border-radius: 11px;
  font-size: 18px;
  place-items: center;
}

.feature-item > div {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.feature-item strong {
  color: var(--color-text);
  font-size: 14px;
  font-weight: 650;
}

.feature-item small {
  margin-top: 3px;
  color: var(--color-text-soft);
  font-size: 12px;
}

.brand-status {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 9px;
  align-items: center;
  margin-top: 28px;
  color: var(--color-text-soft);
  font-family: var(--font-mono);
  font-size: 11px;
}

.brand-status__divider {
  width: 1px;
  height: 11px;
  background: rgba(255, 255, 255, 0.13);
}

.login-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: clamp(34px, 4vw, 56px);
  background: rgba(15, 23, 42, 0.6);
}

.login-panel__header {
  margin-bottom: 30px;
}

.secure-pill {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  padding: 6px 10px;
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.12em;
  background: rgba(6, 182, 212, 0.06);
  border: 1px solid rgba(6, 182, 212, 0.16);
  border-radius: var(--radius-pill);
}

.secure-pill__dot {
  width: 6px;
  height: 6px;
  background: var(--color-primary);
  border-radius: 50%;
  box-shadow: 0 0 10px rgba(6, 182, 212, 0.85);
}

.login-panel__header h2 {
  margin: 18px 0 0;
  color: var(--color-text);
  font-size: 31px;
  font-weight: 650;
  letter-spacing: -0.025em;
}

.login-panel__header p {
  margin: 9px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.75;
}

.auth-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 5px;
  margin-bottom: 22px;
  background: rgba(2, 6, 23, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
}

.auth-switch__item {
  padding: 9px 12px;
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 9px;
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.auth-switch__item:hover {
  color: var(--color-text-soft);
}

.auth-switch__item.is-active {
  color: #06121f;
  background: linear-gradient(105deg, #22d3ee, #60a5fa);
  box-shadow: 0 6px 18px rgba(6, 182, 212, 0.24);
}

.register-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.register-stack {
  display: flex;
  flex-direction: column;
}

.register-stack :deep(.el-form-item) {
  margin-bottom: 14px;
}

.register-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 14px;
}

.register-grid__full {
  grid-column: 1 / -1;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 22px;
}

.login-form :deep(.el-form-item__label) {
  padding-bottom: 7px;
  color: var(--color-text-soft);
  font-size: 11px;
  font-weight: 600;
}

.login-form :deep(.el-input__wrapper) {
  padding: 3px 13px;
  background: rgba(2, 6, 23, 0.42);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 11px;
  box-shadow: none;
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.login-form :deep(.el-input__wrapper:hover) {
  border-color: rgba(34, 211, 238, 0.25);
}

.login-form :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(34, 211, 238, 0.48);
  box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.08);
}

.captcha-row {
  display: flex;
  gap: 10px;
  align-items: stretch;
  width: 100%;
}

.captcha-row :deep(.el-input) {
  flex: 1;
}

.captcha-image {
  display: grid;
  flex: 0 0 140px;
  height: 42px;
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  background: rgba(2, 6, 23, 0.42);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  place-items: center;
}

.captcha-image img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.captcha-image span {
  color: var(--color-text-muted);
  font-size: 12px;
}

.captcha-hint {
  display: block;
  margin-top: 6px;
  color: var(--color-text-faint);
  font-size: 10px;
}

.agreement-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  margin: 2px 0 14px;
  font-size: 11px;
}

.agreement-row :deep(.el-checkbox__label) {
  color: var(--color-text-soft);
  font-size: 11px;
}

.agreement-link {
  padding: 0;
  color: var(--color-primary-strong);
  font-size: 11px;
  cursor: pointer;
  background: transparent;
  border: 0;
}

.agreement-link:hover {
  text-decoration: underline;
}

.agreement-countdown {
  width: 100%;
  color: var(--color-warning);
  font-size: 10px;
}

.agreement-content {
  color: var(--color-text-soft);
  font-size: 13px;
  line-height: 1.85;
}

.agreement-intro {
  margin: 0 0 12px;
  padding: 10px 12px;
  color: var(--color-text-soft);
  background: color-mix(in srgb, var(--brand) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand) 20%, transparent);
  border-radius: 10px;
}

.agreement-content ol {
  padding-left: 20px;
  margin: 0;
}

.agreement-content li {
  margin-bottom: 8px;
}

.agreement-countdown-hint {
  margin: 14px 0 0;
  padding: 10px 12px;
  color: var(--color-warning);
  font-size: 12px;
  text-align: center;
  background: color-mix(in srgb, var(--color-warning) 10%, transparent);
  border: 1px dashed color-mix(in srgb, var(--color-warning) 35%, transparent);
  border-radius: 10px;
}

.login-button {
  width: 100%;
  height: 47px;
  margin-top: 5px;
  letter-spacing: 0.03em;
  background: linear-gradient(105deg, #06b6d4, #3b82f6);
  border: 0;
  box-shadow: 0 12px 30px rgba(6, 182, 212, 0.2);
}

.login-button:hover {
  background: linear-gradient(105deg, #22d3ee, #60a5fa);
  box-shadow: 0 14px 34px rgba(6, 182, 212, 0.28);
}

.demo-account {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  padding: 10px 12px;
  margin-top: 18px;
  font-size: 10px;
  color: var(--color-text-faint);
  background: rgba(6, 182, 212, 0.035);
  border: 1px dashed rgba(6, 182, 212, 0.15);
  border-radius: 10px;
}

.demo-account button {
  padding: 0;
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 10px;
  cursor: pointer;
  background: transparent;
  border: 0;
}

.demo-account button:hover {
  text-decoration: underline;
}

.login-disclaimer {
  width: min(1180px, 100%);
  margin: 16px auto 0;
}
@media (max-width: 960px) {
  .login-page {
    padding: 18px;
  }

  .login-shell {
    grid-template-columns: 1fr;
    max-width: 620px;
    min-height: 0;
  }

  .login-brand {
    padding: 34px;
    border-right: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .brand-copy {
    padding-top: 38px;
  }

  .brand-copy h1 {
    font-size: clamp(34px, 9vw, 48px);
  }

  .feature-list {
    display: none;
  }

  .brand-status {
    margin-top: 22px;
  }

  .login-panel {
    padding: 34px;
  }

  .login-disclaimer {
    max-width: 620px;
  }
}

@media (max-width: 560px) {
  .login-page {
    padding: 10px;
  }

  .login-brand,
  .login-panel {
    padding: 26px 21px;
  }

  .brand-copy {
    padding-top: 30px;
  }

  .brand-copy h1 {
    font-size: 35px;
  }

  .brand-copy > p:last-child {
    font-size: 14px;
  }

  .login-panel__header h2 {
    font-size: 27px;
  }

  .demo-account {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  padding: 10px 12px;
  margin-top: 18px;
  font-size: 10px;
  color: var(--color-text-faint);
  background: rgba(6, 182, 212, 0.035);
  border: 1px dashed rgba(6, 182, 212, 0.15);
  border-radius: 10px;
}

.demo-account button {
  padding: 0;
  color: var(--color-primary-strong);
  font-family: var(--font-mono);
  font-size: 10px;
  cursor: pointer;
  background: transparent;
  border: 0;
}

.demo-account button:hover {
  text-decoration: underline;
}

  .register-grid {
    grid-template-columns: 1fr;
  }

  .register-grid__full {
    grid-column: auto;
  }
}
.brand-status .status-dot.is-offline {
  background: var(--color-danger);
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.85);
}

.brand-status .status-dot.is-checking {
  background: var(--color-warning);
  box-shadow: 0 0 12px rgba(245, 158, 11, 0.78);
  animation: status-pulse 1.2s ease-in-out infinite;
}

@keyframes status-pulse {
  0%,
  100% {
    opacity: 0.45;
  }

  50% {
    opacity: 1;
  }
}</style>