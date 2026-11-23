<script setup>
import { WarningFilled } from '@element-plus/icons-vue'

import { DISCLAIMER_TEXT } from '@/constants/app'

defineProps({
  compact: {
    type: Boolean,
    default: false,
  },
})
</script>

<template>
  <aside class="app-disclaimer" :class="{ 'app-disclaimer--compact': compact }">
    <el-icon class="app-disclaimer__icon"><WarningFilled /></el-icon>
    <p class="app-disclaimer__text">
      <strong>免责声明：</strong>{{ DISCLAIMER_TEXT }}
    </p>
  </aside>
</template>

<style scoped>
.app-disclaimer {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 16px 18px;
  color: var(--text-secondary);
  background: var(--warning-bg);
  border: 1px solid color-mix(in srgb, var(--warning-text) 30%, transparent);
  border-radius: var(--radius-md);
}

.app-disclaimer--compact {
  padding: 12px 14px;
}

.app-disclaimer__icon {
  flex: 0 0 auto;
  margin-top: 3px;
  color: var(--warning-text);
  font-size: 17px;
}

.app-disclaimer__text {
  margin: 0;
  font-size: 13px;
  line-height: 1.75;
}

.app-disclaimer__text strong {
  color: var(--warning-text);
}
</style>