<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <main class="page-shell not-found">
    <section class="glass-panel not-found__card">
      <p class="page-eyebrow">404 / ROUTE NOT FOUND</p>
      <h1 class="page-title">页面不存在</h1>
      <p class="page-description">请求的页面不存在或已被移动。</p>
      <el-button type="primary" @click="router.replace('/workspace')">
        返回工作台
      </el-button>
    </section>
  </main>
</template>

<style scoped>
.not-found {
  display: grid;
  min-height: 100vh;
  place-items: center;
}

.not-found__card {
  width: min(620px, 100%);
  padding: 56px;
  text-align: center;
}

.not-found__card .el-button {
  margin-top: 28px;
}
</style>