<script setup>
defineProps({
  eyebrow: {
    type: String,
    default: 'MEDICAL AI',
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: '该模块将在后续阶段完成。',
  },
})
</script>

<template>
  <main class="page-shell placeholder-page">
    <section class="glass-panel placeholder-card">
      <p class="page-eyebrow">{{ eyebrow }}</p>
      <h1 class="page-title">{{ title }}</h1>
      <p class="page-description">{{ description }}</p>
      <div class="placeholder-status">
        <span class="status-dot"></span>
        第一阶段基础设施已就绪
      </div>
    </section>
  </main>
</template>

<style scoped>
.placeholder-page {
  display: grid;
  min-height: min(680px, calc(100vh - 250px));
  place-items: center;
}

.placeholder-card {
  width: min(760px, 100%);
  padding: clamp(32px, 6vw, 64px);
  text-align: center;
}

.placeholder-status {
  display: inline-flex;
  gap: 10px;
  align-items: center;
  padding: 9px 16px;
  margin-top: 28px;
  color: var(--color-primary-strong);
  font-size: 13px;
  background: rgba(6, 182, 212, 0.08);
  border: 1px solid rgba(6, 182, 212, 0.24);
  border-radius: var(--radius-pill);
}

.status-dot {
  width: 8px;
  height: 8px;
  background: var(--color-primary);
  border-radius: 50%;
  box-shadow: 0 0 14px var(--color-primary);
}
</style>