<script setup lang="ts">
import { watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useUiStore } from '@/stores/ui'

// 主题跟随 ui store，同步到 <html class="night">
const ui = useUiStore()
const { theme } = storeToRefs(ui)

watch(
  theme,
  (t) => {
    document.documentElement.classList.toggle('night', t === 'night')
  },
  { immediate: true }
)
</script>

<template>
  <router-view />
</template>
