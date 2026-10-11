<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'
import { useParallax } from '@/composables/useParallax'
import { useDizzy } from '@/composables/useDizzy'
import { useTTS } from '@/composables/useTTS'
import { reactionMood } from '@/utils/emotionAnim'
import StageSprite from '@/components/stage/StageSprite.vue'
import Live2dStage from '@/components/stage/Live2dStage.vue'
import DialogBox from '@/components/stage/DialogBox.vue'
import HistoryOverlay from '@/components/stage/HistoryOverlay.vue'
import PanelsOverlay from '@/components/stage/PanelsOverlay.vue'
import SettingsDrawer from '@/components/stage/SettingsDrawer.vue'
import SiaIcon from '@/components/SiaIcon.vue'

const chat = useChatStore()
const ui = useUiStore()
const { overlay, ttsEnabled, useLive2d } = storeToRefs(ui)

// 视差（伪视线跟随）+ 发晕检测（nx/ny 同时供 2.5D 深度视差着色器使用）
const { nx, ny, speed, transform } = useParallax()
const { dizzy } = useDizzy(speed)

// TTS 语音回复
const { speaking, autoplayBlocked, speak, resume, stop } = useTTS(ttsEnabled)

/** HUD 触控条：平时隐藏，鼠标移到顶部区域才浮现，避免破坏沉浸感 */
const hudVisible = ref(false)
let hudHideTimer = 0

function onStagePointerMove(e: PointerEvent): void {
  window.clearTimeout(hudHideTimer)
  if (e.clientY < 88) {
    hudVisible.value = true
  } else if (hudVisible.value) {
    hudHideTimer = window.setTimeout(() => {
      hudVisible.value = false
    }, 320)
  }
}

onMounted(() => {
  if (!chat.initialized) void chat.init()
  window.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
})

/** 最新一条 assistant 回复（打字机与情绪动效的数据源） */
const lastReply = computed(() => {
  for (let i = chat.messages.length - 1; i >= 0; i -= 1) {
    if (chat.messages[i].role === 'assistant') return chat.messages[i]
  }
  return null
})

/** 回复序号：新 assistant 回复到达时 +1，驱动打字机重放与情绪动画重触发 */
const replyKey = ref(0)
watch(
  () => chat.messages.length,
  () => {
    const last = chat.messages[chat.messages.length - 1]
    if (last?.role === 'assistant') replyKey.value += 1
  }
)

/** 最新一条用户消息（她"对你的话做反应"的判定来源） */
const lastUserText = computed(() => {
  for (let i = chat.messages.length - 1; i >= 0; i -= 1) {
    if (chat.messages[i].role === 'user') return chat.messages[i].content
  }
  return ''
})

/** 当前心情：优先看你说了什么（撩/夸/惊叹 → 害羞/傲娇/惊讶），否则跟随你的情绪标签 */
const mood = computed(() => reactionMood(lastUserText.value, lastReply.value?.emotion))

/** 一轮发送结束 → 语音播报最新回复（初始化欢迎语不播） */
watch(
  () => chat.sending,
  (now, old) => {
    if (old && !now) {
      const last = chat.messages[chat.messages.length - 1]
      if (last?.role === 'assistant') void speak(last.content)
    }
  }
)

/** 关闭语音回复时立即停止当前播放 */
watch(ttsEnabled, (on) => {
  if (!on) stop()
})

/** ESC 关闭覆层 */
function onKey(e: KeyboardEvent): void {
  if (e.key === 'Escape') ui.closeOverlay()
}
</script>

<template>
  <div class="stage" @pointermove="onStagePointerMove">
    <!-- 全屏立绘舞台：Live2D（技术验证）与写实立绘可切换 -->
    <Live2dStage v-if="useLive2d" :mood="mood" />
    <StageSprite
      v-else
      :parallax="transform"
      :pointer-x="nx"
      :pointer-y="ny"
      :mood="mood"
      :mood-key="replyKey"
      :dizzy="dizzy"
    />

    <!-- 暗角：保证底部对话框文字可读；夜间加重 -->
    <div class="stage-shade"></div>

    <!-- HUD -->
    <header class="stage-hud" :class="{ 'is-visible': hudVisible }">
      <span v-if="chat.state" class="hud-badge" :title="`好感度 ${chat.state.trust}/100`">
        💗 {{ chat.state.trust }}/100 · {{ chat.state.intimacy_label }}
      </span>
      <span class="hud-spacer"></span>
      <button class="hud-btn" type="button" title="历史对话" @click="ui.openOverlay('history')">
        <SiaIcon name="history" />
      </button>
      <button class="hud-btn" type="button" title="关系与回忆" @click="ui.openOverlay('panels')">
        <SiaIcon name="heart" />
      </button>
      <button class="hud-btn" type="button" title="设置" @click="ui.openOverlay('settings')">
        <SiaIcon name="settings" />
      </button>
      <button
        class="hud-btn"
        type="button"
        :title="ttsEnabled ? '关闭语音回复' : '开启语音回复'"
        @click="ui.toggleTts"
      >
        <SiaIcon :name="ttsEnabled ? 'volume' : 'volumeMute'" />
      </button>
      <button
        class="hud-btn"
        type="button"
        :title="ui.theme === 'night' ? '切换到日间' : '切换到夜间'"
        @click="ui.toggleTheme"
      >
        <SiaIcon :name="ui.theme === 'night' ? 'sun' : 'moon'" />
      </button>
    </header>

    <!-- 立绘切换：始终可见的小悬浮按钮（右上角），保证功能可发现 -->
    <button
      class="render-toggle"
      type="button"
      :title="useLive2d ? '切换到写实立绘' : '切换到 Live2D 动态形象'"
      @click="ui.toggleRenderMode"
    >
      <SiaIcon name="user" />
    </button>

    <!-- 底部 galgame 对话框 -->
    <DialogBox
      class="stage-dialog"
      :reply="lastReply?.content ?? ''"
      :reply-key="replyKey"
      :tts-blocked="autoplayBlocked"
      :speaking="speaking"
      @play-tts="resume"
    />

    <!-- 覆层（互斥） -->
    <HistoryOverlay v-if="overlay === 'history'" />
    <PanelsOverlay v-else-if="overlay === 'panels'" />
    <SettingsDrawer v-else-if="overlay === 'settings'" />
  </div>
</template>

<style scoped>
.stage {
  position: relative;
  height: 100dvh;
  overflow: hidden;
}

/* ---- 暗角遮罩：底部压暗保证对话框可读，夜间整体加深 ---- */
.stage-shade {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(
    to bottom,
    rgba(0, 0, 0, 0.12) 0%,
    transparent 22%,
    transparent 52%,
    rgba(0, 0, 0, 0.38) 100%
  );
}

html.night .stage-shade {
  background: linear-gradient(
    to bottom,
    rgba(0, 0, 0, 0.4) 0%,
    rgba(0, 0, 0, 0.12) 22%,
    rgba(0, 0, 0, 0.1) 52%,
    rgba(0, 0, 0, 0.6) 100%
  );
}

/* ---- HUD：触控条，平时隐藏、鼠标移到顶部浮现，科幻风格 ---- */
.stage-hud {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 64px 14px 18px;
  z-index: 5;
  opacity: 0;
  transform: translateY(-12px);
  pointer-events: none;
  transition: opacity 0.35s ease, transform 0.35s ease;
}

.stage-hud.is-visible {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.hud-badge {
  padding: 5px 12px;
  border-radius: 999px;
  background: var(--hud-glass);
  backdrop-filter: blur(10px);
  border: 1px solid var(--cyber-border);
  color: var(--cyber-strong);
  font-size: 12.5px;
  letter-spacing: 0.3px;
  white-space: nowrap;
  box-shadow: inset 0 0 12px var(--cyber-soft);
}

.hud-spacer {
  flex: 1;
}

.hud-btn {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--cyber-border);
  border-radius: 9px;
  background: var(--hud-glass);
  backdrop-filter: blur(10px);
  color: var(--cyber-strong);
  font-size: 16px;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease,
    background 0.18s ease, color 0.18s ease;
}

.hud-btn:hover {
  transform: translateY(-1px);
  border-color: var(--cyber);
  color: #ffffff;
  background: var(--cyber-soft);
  box-shadow: var(--cyber-glow);
}

/* 立绘切换悬浮按钮：始终可见，与其他 HUD 按钮同款科幻风格 */
.render-toggle {
  position: absolute;
  top: 14px;
  right: 18px;
  z-index: 6;
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--cyber-border);
  border-radius: 9px;
  background: var(--hud-glass);
  backdrop-filter: blur(10px);
  color: var(--cyber-strong);
  font-size: 16px;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease,
    background 0.18s ease, color 0.18s ease;
}

.render-toggle:hover {
  transform: translateY(-1px);
  border-color: var(--cyber);
  color: #ffffff;
  background: var(--cyber-soft);
  box-shadow: var(--cyber-glow);
}

/* ---- 对话框位置 ---- */
.stage-dialog {
  position: absolute;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  z-index: 4;
}

/* ---- 移动端 ---- */
@media (max-width: 899px) {
  .stage-hud {
    padding: 10px 54px 10px 10px;
    gap: 6px;
  }

  .hud-btn {
    width: 34px;
    height: 34px;
    font-size: 15px;
  }

  .render-toggle {
    top: 10px;
    right: 10px;
    width: 34px;
    height: 34px;
    font-size: 15px;
  }

  .hud-badge {
    font-size: 11px;
    padding: 4px 9px;
  }

  .stage-dialog {
    bottom: 10px;
  }
}

/* ---- 触屏设备：无 hover，HUD 保持常显，避免找不到入口 ---- */
@media (pointer: coarse) {
  .stage-hud {
    opacity: 1;
    transform: none;
    pointer-events: auto;
  }
}
</style>
