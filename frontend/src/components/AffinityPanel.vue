<script setup lang="ts">
import type { ChatState } from '@/api/types'

defineProps<{ state: ChatState | null }>()
</script>

<template>
  <section class="panel affinity">
    <h3 class="panel-title">💗 我们的关系</h3>
    <template v-if="state">
      <div class="affinity__head">
        <span class="affinity__label">{{ state.intimacy_label }}</span>
        <span class="affinity__num">{{ state.trust }}/100</span>
      </div>
      <div class="affinity__bar">
        <div class="affinity__fill" :style="{ width: `${Math.min(100, Math.max(0, state.trust))}%` }"></div>
      </div>
      <p v-if="state.tip" class="affinity__tip">💭 {{ state.tip }}</p>
    </template>
    <p v-else class="panel-empty">加载中…</p>
  </section>
</template>

<style scoped>
.affinity__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.affinity__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
}

.affinity__num {
  font-size: 12px;
  color: var(--text-soft);
  font-variant-numeric: tabular-nums;
}

.affinity__bar {
  height: 10px;
  border-radius: 999px;
  background: var(--bar-bg);
  overflow: hidden;
}

.affinity__fill {
  height: 100%;
  border-radius: 999px;
  background: var(--bar-fill);
  transition: width 0.6s ease;
}

.affinity__tip {
  margin: 10px 0 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-soft);
}
</style>
