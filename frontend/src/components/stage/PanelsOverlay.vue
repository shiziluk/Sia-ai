<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'
import AffinityPanel from '@/components/AffinityPanel.vue'
import SearchPanel from '@/components/SearchPanel.vue'
import MemoryPanel from '@/components/MemoryPanel.vue'
import DiaryPanel from '@/components/DiaryPanel.vue'

const chat = useChatStore()
const ui = useUiStore()

const TABS = [
  { key: 'affinity', label: '💗 关系' },
  { key: 'search', label: '🔍 搜索' },
  { key: 'memory', label: '🧠 记忆' },
  { key: 'diary', label: '📔 日记' }
] as const

type TabKey = (typeof TABS)[number]['key']

const tab = ref<TabKey>('affinity')
</script>

<template>
  <Teleport to="body">
    <Transition name="fade" appear>
      <div class="panels-overlay" @click.self="ui.closeOverlay()">
        <div class="panels-card">
          <nav class="panels-tabs">
            <button
              v-for="t in TABS"
              :key="t.key"
              class="tab-btn"
              :class="{ 'tab-btn--active': tab === t.key }"
              type="button"
              @click="tab = t.key"
            >
              {{ t.label }}
            </button>
            <span class="tab-spacer"></span>
            <button class="close-btn" type="button" title="关闭（Esc）" @click="ui.closeOverlay()">
              ✕
            </button>
          </nav>

          <div class="panels-body">
            <AffinityPanel v-if="tab === 'affinity'" :state="chat.state" />
            <SearchPanel v-else-if="tab === 'search'" />
            <MemoryPanel v-else-if="tab === 'memory'" />
            <DiaryPanel v-else-if="tab === 'diary'" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.panels-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgba(10, 8, 16, 0.55);
  backdrop-filter: blur(6px);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 24px 16px;
}

.panels-card {
  width: min(680px, 100%);
  max-height: min(80dvh, 860px);
  display: flex;
  flex-direction: column;
  border-radius: 22px;
  background: var(--card);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  overflow: hidden;
}

.panels-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
}

.tab-btn {
  padding: 7px 14px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--text-soft);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.tab-btn:hover {
  color: var(--text);
  background: var(--card-soft);
}

.tab-btn--active {
  background: var(--primary-soft-bg);
  border-color: var(--border);
  color: var(--primary);
  font-weight: 600;
}

.tab-spacer {
  flex: 1;
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-soft);
  font-size: 15px;
  cursor: pointer;
}

.close-btn:hover {
  background: var(--primary-soft-bg);
  color: var(--primary);
}

.panels-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px calc(14px + env(safe-area-inset-bottom));
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
