<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'

const chat = useChatStore()
const ui = useUiStore()

const listEl = ref<HTMLElement | null>(null)

onMounted(() => {
  // 进入时滚到最新一条
  void nextTick(() => {
    const el = listEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
})

function nameOf(role: string): string {
  if (role === 'user') return chat.context?.user_name ?? '我'
  if (role === 'assistant') return '希亚'
  return '提示'
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade" appear>
      <div class="history-overlay">
        <div class="history-panel">
          <header class="history-head">
            <h2>📜 历史对话</h2>
            <button class="close-btn" type="button" title="关闭（Esc）" @click="ui.closeOverlay()">
              ✕
            </button>
          </header>

          <div ref="listEl" class="history-list">
            <div
              v-for="m in chat.messages"
              :key="m.id"
              class="log"
              :class="`log--${m.role}`"
            >
              <div class="log__meta">
                <span class="log__name">{{ nameOf(m.role) }}</span>
                <span v-if="m.time" class="log__time">{{ m.time }}</span>
              </div>
              <p class="log__text">{{ m.content }}</p>
            </div>
            <p v-if="chat.messages.length === 0" class="history-empty">
              还没有对话，从下面跟希亚打个招呼吧～
            </p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.history-overlay {
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

.history-panel {
  width: min(860px, 100%);
  max-height: min(82dvh, 900px);
  display: flex;
  flex-direction: column;
  border-radius: 22px;
  background: var(--card);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  overflow: hidden;
}

.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
}

.history-head h2 {
  margin: 0;
  font-size: 16px;
  color: var(--text);
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

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* galgame backlog 式：名牌 + 正文，非气泡 */
.log {
  padding: 10px 14px;
  border-radius: 14px;
  border-left: 3px solid var(--border);
  background: var(--card-soft);
}

.log--user {
  border-left-color: var(--accent);
}

.log--assistant {
  border-left-color: var(--primary);
}

.log--system {
  border-left-color: transparent;
  background: var(--system-bg);
  opacity: 0.85;
}

.log__meta {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 4px;
}

.log__name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.log--assistant .log__name {
  color: var(--primary);
}

.log__time {
  font-size: 11px;
  color: var(--text-soft);
}

.log__text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
}

.history-empty {
  margin: 0;
  text-align: center;
  color: var(--text-soft);
  font-size: 13.5px;
  padding: 30px 0;
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
