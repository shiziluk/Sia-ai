<script setup lang="ts">
import { ref } from 'vue'
import { textToSpeech } from '@/api/voice'
import type { ChatMessage } from '@/stores/chat'
import { emotionEmoji } from '@/utils/emoji'
import { shortTime } from '@/utils/format'

defineProps<{ message: ChatMessage }>()

// 朗读状态管理
const speaking = ref(false)
let audio: HTMLAudioElement | null = null

/** 点击朗读：请求 TTS 拿到 audio/mpeg Blob 后播放 */
async function speak(content: string): Promise<void> {
  if (speaking.value) {
    stopSpeak()
    return
  }
  speaking.value = true
  try {
    const blob = await textToSpeech(content)
    const url = URL.createObjectURL(blob)
    audio = new Audio(url)
    audio.onended = () => stopSpeak()
    audio.onerror = () => stopSpeak()
    await audio.play()
  } catch {
    speaking.value = false
  }
}

/** 停止朗读并释放资源 */
function stopSpeak(): void {
  if (audio) {
    audio.pause()
    URL.revokeObjectURL(audio.src)
    audio = null
  }
  speaking.value = false
}
</script>

<template>
  <!-- 系统提示（记忆/错误）：居中小胶囊 -->
  <div v-if="message.role === 'system'" class="msg-system">
    <span>{{ message.content }}</span>
  </div>

  <!-- 用户消息：右侧气泡，情绪 emoji 在气泡右侧 -->
  <div v-else-if="message.role === 'user'" class="msg-row msg-row--user">
    <div class="msg-bubble msg-bubble--user">
      <p class="msg-text">{{ message.content }}</p>
      <span v-if="message.time" class="msg-time">{{ shortTime(message.time) }}</span>
    </div>
    <span class="msg-emoji" :title="message.emotion || ''">{{
      emotionEmoji(message.emotion)
    }}</span>
  </div>

  <!-- 希亚消息：左侧气泡 + 朗读按钮 -->
  <div v-else class="msg-row msg-row--assistant">
    <span class="msg-emoji" :title="message.emotion || ''">{{
      emotionEmoji(message.emotion)
    }}</span>
    <div class="msg-bubble msg-bubble--assistant">
      <p class="msg-text msg-text--pre">{{ message.content }}</p>
      <div class="msg-meta">
        <span v-if="message.time" class="msg-time">{{ shortTime(message.time) }}</span>
        <button
          class="msg-speak"
          type="button"
          :title="speaking ? '停止朗读' : '朗读'"
          @click="speak(message.content)"
        >
          {{ speaking ? '⏸' : '🔊' }}
          <span>{{ speaking ? '停止' : '朗读' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.msg-system {
  align-self: center;
  max-width: 85%;
  padding: 6px 14px;
  border-radius: 999px;
  background: var(--system-bg);
  color: var(--text-soft);
  font-size: 12.5px;
  text-align: center;
}

.msg-row {
  display: flex;
  align-items: flex-end;
  gap: 6px;
}

.msg-row--user {
  justify-content: flex-end;
}

.msg-row--assistant {
  justify-content: flex-start;
}

.msg-emoji {
  font-size: 20px;
  line-height: 1;
  margin-bottom: 4px;
  flex-shrink: 0;
}

.msg-bubble {
  max-width: min(72%, 520px);
  padding: 10px 14px;
  border-radius: 18px;
  box-shadow: var(--shadow);
  word-break: break-word;
}

.msg-bubble--user {
  background: var(--bubble-user);
  color: var(--bubble-user-text);
  border-bottom-right-radius: 6px;
}

.msg-bubble--assistant {
  background: var(--bubble-bot);
  color: var(--text);
  border-bottom-left-radius: 6px;
  border: 1px solid var(--border);
}

.msg-text {
  margin: 0;
  font-size: 14.5px;
  line-height: 1.65;
}

/* 希亚的欢迎语/回复保留换行 */
.msg-text--pre {
  white-space: pre-line;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
}

.msg-time {
  font-size: 11px;
  opacity: 0.55;
}

.msg-speak {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border: none;
  background: transparent;
  color: var(--primary);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 8px;
}

.msg-speak:hover {
  background: var(--primary-soft-bg);
}
</style>
