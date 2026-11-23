<script setup>
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <div class="app-aurora app-aurora--cyan" aria-hidden="true"></div>
    <div class="app-aurora app-aurora--blue" aria-hidden="true"></div>

    <RouterView v-slot="{ Component, route }">
      <Transition name="page" mode="out-in">
        <component
          :is="Component"
          :key="route.matched[0]?.path || route.path"
        />
      </Transition>
    </RouterView>
  </div>
</template>