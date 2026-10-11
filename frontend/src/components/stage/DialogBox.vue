<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useRecorder } from '@/composables/useRecorder'
import { useTypewriter } from '@/composables/useTypewriter'
import { useChatStore } from '@/stores/chat'
import SiaIcon from '@/components/SiaIcon.vue'

const props = defineProps<{
  /** 当前展示的回复文本（最新一条 assistant 消息） */
  reply: string
  /** 回复序号：每条新回复 +1，重放打字机 */
  replyKey: number
  /** TTS 自动播放被拦截（显示「点此播放」胶囊） */
  ttsBlocked?: boolean
  /** 希亚正在说话（名牌上显示小标记） */
  speaking?: boolean
}>()

const emit = defineEmits<{ (e: 'play-tts'): void }>()

const chat = useChatStore()
const { typedText, typing, start, skip } = useTypewriter()

// 新回复到来 → 重放打字机
watch(
  () => props.replyKey,
  () => start(props.reply),
  { immediate: true }
)

const draft = ref('')
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

/** 输入框随内容自动增高（上限 96px） */
function autoResize(): void {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 96)}px`
}

function resetInputHeight(): void {
  const el = inputEl.value
  if (el) el.style.height = 'auto'
}

/** 点击对话框正文：跳过打字机 */
function onTextClick(): void {
  if (typing.value) skip()
}

watch(draft, () => {
  void nextTick(autoResize)
})
</script>

<template>
  <div class="dialog-box">
    <!-- 名牌 -->
    <div class="dialog-name">
      希亚
      <Transition name="fade">
        <span v-if="speaking" class="dialog-name__speaking">🔊 说话中…</span>
      </Transition>
    </div>

    <!-- 回复正文：打字机 -->
    <div class="dialog-text" :class="{ 'dialog-text--skipable': typing }" @click="onTextClick">
      <template v-if="chat.sending">
        <span class="dots"><i></i><i></i><i></i></span>
      </template>
      <template v-else>{{ typedText }}</template>
    </div>

    <!-- TTS 被拦截的兜底胶囊 -->
    <Transition name="fade">
      <button v-if="ttsBlocked" class="tts-capsule" type="button" @click="emit('play-tts')">
        🔊 点此播放语音
      </button>
    </Transition>

    <!-- 输入行 -->
    <div class="dialog-input">
      <button
        class="mic-btn"
        :class="{ 'mic-btn--rec': recording }"
        type="button"
        :disabled="busy"
        :title="recording ? '停止并识别' : '点一下开始录音'"
        @click="toggle"
      >
        <SiaIcon :name="recording ? 'stop' : 'mic'" />
      </button>
      <textarea
        ref="inputEl"
        v-model="draft"
        class="dialog-input__field"
        rows="1"
        placeholder="和希亚说点什么…（Enter 发送）"
        @keydown="onKeydown"
      ></textarea>
      <button class="send-btn" type="button" :disabled="chat.sending || !draft.trim()" @click="send">
        <SiaIcon name="send" />
      </button>
    </div>

    <Transition name="fade">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.dialog-box {
  position: relative;
  width: min(880px, calc(100% - 32px));
  border-radius: 22px;
  background: var(--stage-glass);
  backdrop-filter: blur(14px);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  padding: 14px 18px calc(12px + env(safe-area-inset-bottom));
}

/* ---- 名牌 ---- */
.dialog-name {
  position: absolute;
  top: -16px;
  left: 22px;
  padding: 5px 18px;
  border-radius: 999px;
  background: var(--bubble-user);
  color: var(--bubble-user-text);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 2px;
  box-shadow: var(--shadow);
  display: flex;
  align-items: center;
  gap: 8px;
}

.dialog-name__speaking {
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0;
  opacity: 0.9;
}

/* ---- 正文 ---- */
.dialog-text {
  min-height: 58px;
  max-height: 168px;
  overflow-y: auto;
  padding: 10px 4px 8px;
  font-size: 15.5px;
  line-height: 1.75;
  color: var(--text);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  white-space: pre-wrap;
  word-break: break-word;
}

.dialog-text--skipable {
  cursor: pointer;
}

/* sending 时的省略号动效 */
.dots {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  height: 24px;
}

.dots i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--primary);
  opacity: 0.4;
  animation: dot-blink 1.2s infinite;
}

.dots i:nth-child(2) {
  animation-delay: 0.2s;
}

.dots i:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dot-blink {
  0%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-4px);
  }
}

/* ---- TTS 兜底胶囊 ---- */
.tts-capsule {
  position: absolute;
  top: 10px;
  right: 16px;
  padding: 6px 14px;
  border: none;
  border-radius: 999px;
  background: var(--primary);
  color: #fff;
  font-size: 12.5px;
  cursor: pointer;
  box-shadow: var(--shadow);
}

/* ---- 输入行 ---- */
.dialog-input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  border-top: 1px solid var(--border);
  padding-top: 10px;
}

.dialog-input__field {
  flex: 1;
  min-width: 0;
  max-height: 96px;
  padding: 9px 14px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
  outline: none;
}

.dialog-input__field:focus {
  border-color: var(--cyber);
}

.mic-btn {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 1px solid var(--cyber-border);
  background: var(--card);
  color: var(--cyber);
  font-size: 16px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
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
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border: none;
  border-radius: 50%;
  background: var(--cyber);
  color: #05262e;
  font-size: 16px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* ---- toast ---- */
.toast {
  position: fixed;
  left: 50%;
  bottom: 190px;
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

/* ---- 移动端 ---- */
@media (max-width: 899px) {
  .dialog-box {
    width: calc(100% - 20px);
    padding: 12px 12px calc(10px + env(safe-area-inset-bottom));
  }

  .dialog-text {
    font-size: 14.5px;
    min-height: 48px;
  }
}
</style>
