<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRecorder } from '@/composables/useRecorder'
import CharacterSprite from '@/components/CharacterSprite.vue'
import MessageBubble from '@/components/MessageBubble.vue'
import SidePanel from '@/components/SidePanel.vue'
import TypingIndicator from '@/components/TypingIndicator.vue'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'

const chat = useChatStore()
const ui = useUiStore()

const draft = ref('')
const bodyEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)

// 底部轻提示（录音错误等）
const toast = ref('')
let toastTimer: number | undefined

function showToast(msg: string): void {
  toast.value = msg
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toast.value = ''
  }, 2600)
}

// 麦克风：识别成功填入输入框（用户确认后手动发送）
const { recording, busy, toggle } = useRecorder({
  onText: (text) => {
    draft.value = text
    inputEl.value?.focus()
  },
  onError: showToast
})

onMounted(() => {
  if (!chat.initialized) void chat.init()
})

// 消息列表或发送状态变化时滚动到底部
watch(
  () => [chat.messages.length, chat.sending] as const,
  () => {
    void nextTick(() => {
      const el = bodyEl.value
      if (el) el.scrollTop = el.scrollHeight
    })
  }
)

function send(): void {
  const text = draft.value
  if (!text.trim() || chat.sending) return
  draft.value = ''
  resetInputHeight()
  void chat.send(text)
}

function onKeydown(e: KeyboardEvent): void {
  // Enter 发送（输入法组合中除外），Shift+Enter 换行
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    send()
  }
}

/** 输入框随内容自动增高（上限 120px） */
function autoResize(): void {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 120)}px`
}

function resetInputHeight(): void {
  const el = inputEl.value
  if (el) el.style.height = 'auto'
}
</script>

<template>
  <div class="chat-page">
    <div class="chat-main">
      <!-- 顶部栏 -->
      <header class="topbar">
        <button
          class="icon-btn topbar__menu"
          type="button"
          aria-label="打开侧边栏"
          @click="ui.sidebarOpen = true"
        >
          ☰
        </button>
        <CharacterSprite class="topbar__avatar" :size="42" />
        <div class="topbar__title">
          <h1>希亚</h1>
          <span v-if="chat.context" class="topbar__sub">{{ chat.context.user_name }} 的专属女友</span>
        </div>
        <span
          v-if="chat.state"
          class="badge"
          :title="`好感度 ${chat.state.trust}/100`"
        >
          💗 {{ chat.state.trust }}/100 · {{ chat.state.intimacy_label }}
        </span>
        <span class="topbar__spacer"></span>
        <button class="icon-btn" type="button" :title="ui.theme === 'night' ? '切换到日间' : '切换到夜间'" @click="ui.toggleTheme">
          {{ ui.theme === 'night' ? '☀️' : '🌙' }}
        </button>
        <router-link class="icon-btn" to="/settings" title="设置">⚙️</router-link>
      </header>

      <!-- 消息区 -->
      <div ref="bodyEl" class="chat-body">
        <div class="chat-inner">
          <MessageBubble v-for="m in chat.messages" :key="m.id" :message="m" />
          <TypingIndicator v-if="chat.sending" class="typing-row" />
        </div>
        <!-- 装饰立绘：桌面端左下角，纯装饰不挡操作 -->
        <CharacterSprite class="corner-sprite" :size="110" />
      </div>

      <!-- 输入区 -->
      <footer class="composer">
        <button
          class="mic-btn"
          :class="{ 'mic-btn--rec': recording }"
          type="button"
          :disabled="busy"
          :title="recording ? '停止并识别' : '按住说话？点一下开始录音'"
          @click="toggle"
        >
          {{ busy ? '⏳' : recording ? '⏹' : '🎤' }}
        </button>
        <textarea
          ref="inputEl"
          v-model="draft"
          class="composer__input"
          rows="1"
          placeholder="和希亚说点什么…（Enter 发送，Shift+Enter 换行）"
          @keydown="onKeydown"
          @input="autoResize"
        ></textarea>
        <button class="send-btn" type="button" :disabled="chat.sending || !draft.trim()" @click="send">
          发送
        </button>
      </footer>

      <Transition name="fade">
        <div v-if="toast" class="toast">{{ toast }}</div>
      </Transition>
    </div>

    <!-- 侧边栏：桌面右侧 / 移动端抽屉 -->
    <SidePanel />
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  height: 100dvh;
  overflow: hidden;
}

.chat-main {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* ---- 顶部栏 ---- */
.topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--panel-bg);
  backdrop-filter: blur(10px);
}

.topbar__avatar {
  flex-shrink: 0;
}

.topbar__title h1 {
  margin: 0;
  font-size: 17px;
  line-height: 1.2;
  color: var(--text);
}

.topbar__sub {
  font-size: 11.5px;
  color: var(--text-soft);
}

.badge {
  margin-left: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--primary-soft-bg);
  color: var(--primary);
  font-size: 12px;
  white-space: nowrap;
}

.topbar__spacer {
  flex: 1;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 12px;
  background: transparent;
  font-size: 17px;
  cursor: pointer;
  text-decoration: none;
  color: var(--text);
}

.icon-btn:hover {
  background: var(--primary-soft-bg);
}

.topbar__menu {
  display: none;
}

/* ---- 消息区 ---- */
.chat-body {
  position: relative;
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.chat-inner {
  max-width: 860px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.typing-row {
  margin-left: 4px;
}

.corner-sprite {
  position: absolute;
  left: 16px;
  bottom: 10px;
  pointer-events: none;
  display: none;
  opacity: 0.9;
}

/* ---- 输入区 ---- */
.composer {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 10px 16px calc(10px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--border);
  background: var(--panel-bg);
  backdrop-filter: blur(10px);
}

.composer__input {
  flex: 1;
  min-width: 0;
  max-height: 120px;
  padding: 10px 14px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
  outline: none;
}

.composer__input:focus {
  border-color: var(--primary);
}

.mic-btn {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border: none;
  border-radius: 50%;
  background: var(--card);
  border: 1px solid var(--border);
  font-size: 17px;
  cursor: pointer;
}

.mic-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.mic-btn--rec {
  background: #ffe3ea;
  border-color: #e91e63;
  animation: mic-pulse 1.1s infinite;
}

@keyframes mic-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(233, 30, 99, 0.45);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(233, 30, 99, 0);
  }
}

.send-btn {
  flex-shrink: 0;
  padding: 10px 18px;
  border: none;
  border-radius: 999px;
  background: var(--bubble-user);
  color: var(--bubble-user-text);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* ---- toast 轻提示 ---- */
.toast {
  position: fixed;
  left: 50%;
  bottom: 92px;
  transform: translateX(-50%);
  padding: 8px 18px;
  border-radius: 999px;
  background: rgba(20, 15, 25, 0.8);
  color: #fff;
  font-size: 13px;
  z-index: 60;
  white-space: nowrap;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ---- 桌面端 ---- */
@media (min-width: 900px) {
  .corner-sprite {
    display: block;
  }
}

/* ---- 移动端 ---- */
@media (max-width: 899px) {
  .topbar__menu {
    display: inline-flex;
  }

  .topbar__sub {
    display: none;
  }

  .badge {
    font-size: 11px;
    padding: 3px 8px;
  }
}
</style>
