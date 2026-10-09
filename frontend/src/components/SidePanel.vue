<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useUiStore } from '@/stores/ui'
import { useChatStore } from '@/stores/chat'
import AffinityPanel from './AffinityPanel.vue'
import SearchPanel from './SearchPanel.vue'
import MemoryPanel from './MemoryPanel.vue'
import DiaryPanel from './DiaryPanel.vue'

const ui = useUiStore()
const { sidebarOpen, enableCritique } = storeToRefs(ui)
const chat = useChatStore()
</script>

<template>
  <!-- 移动端抽屉遮罩 -->
  <Transition name="fade">
    <div v-if="sidebarOpen" class="drawer-mask" @click="ui.sidebarOpen = false"></div>
  </Transition>

  <aside class="side" :class="{ 'side--open': sidebarOpen }">
    <div class="side__scroll">
      <!-- 好感度面板 -->
      <AffinityPanel :state="chat.state" />

      <!-- 人格自检开关 -->
      <section class="panel critique">
        <h3 class="panel-title">🪞 人格自检</h3>
        <label class="critique__row">
          <span>
            让希亚每句话后自我反省，回复更走心（略慢）
          </span>
          <input
            :checked="enableCritique"
            type="checkbox"
            class="critique__switch"
            @change="ui.toggleCritique"
          />
        </label>
      </section>

      <!-- 聊天记录搜索 -->
      <SearchPanel />

      <!-- 记忆库 -->
      <MemoryPanel />

      <!-- 今日情绪日记 -->
      <DiaryPanel />
    </div>
  </aside>
</template>

<style scoped>
.drawer-mask {
  display: none;
}

.side__scroll {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  overflow-y: auto;
  padding: 16px;
}

/* 桌面端：右侧常驻栏 */
@media (min-width: 900px) {
  .side {
    width: 340px;
    flex-shrink: 0;
    border-left: 1px solid var(--border);
    background: var(--panel-bg);
  }
}

/* 移动端：右侧抽屉 */
@media (max-width: 899px) {
  .drawer-mask {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.35);
    z-index: 40;
  }

  .side {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(88vw, 360px);
    background: var(--panel-bg);
    z-index: 50;
    transform: translateX(100%);
    transition: transform 0.28s ease;
    box-shadow: -8px 0 30px rgba(0, 0, 0, 0.18);
  }

  .side--open {
    transform: translateX(0);
  }
}

/* 抽屉遮罩淡入淡出 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
