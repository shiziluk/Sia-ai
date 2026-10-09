<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { EXPRESSION_DIFFS, MAIN_SPRITE } from '@/config/sprite'
import type { Mood } from '@/utils/emotionAnim'

// 发晕台词（触发时随机抽一条）
const DIZZY_LINES = [
  '好晕……你别晃那么快嘛',
  '呜……眼前全是星星',
  '头、头好晕……',
  '再摇我真的要站不稳了'
]

// 情绪反应台词：她对你的话做出的"口头上"的反应（随机抽一条，展示 2.6 秒）
const REACTION_LINES: Partial<Record<string, string[]>> = {
  tsundere: ['哼！才、才不是为了你呢…', '笨蛋，别误会了！', '哼，勉、勉强陪陪你吧', '谁、谁要关心你呀！'],
  shy: ['(⁄ ⁄•⁄ω⁄•⁄ ⁄) 突然这样说…', '讨、讨厌…脸好烫', '唔…让人怎么回答嘛', '你、你在看哪里呀'],
  surprised: ['欸欸欸？！', '诶——？！真的假的？', '吓、吓我一跳！']
}

const REACTION_ICONS: Partial<Record<string, string>> = {
  tsundere: '😤',
  shy: '😳',
  surprised: '😲'
}

const props = defineProps<{
  /** 视差 transform（useParallax 提供） */
  parallax: string
  /** 当前心情（驱动动效与滤镜；空串=呼吸待机） */
  mood?: Mood
  /** 回复序号：每条新回复 +1，用于重触发一次性情绪动画 */
  moodKey?: number
  /** 发晕状态 */
  dizzy?: boolean
}>()

/** 表情差分：配置了对应情绪的差分图则换图，否则用主立绘 */
const currentSrc = computed(() => {
  if (props.mood) {
    const diff = EXPRESSION_DIFFS[props.mood]
    if (diff) return diff
  }
  return MAIN_SPRITE
})

/** 一次性情绪动画的 key：mood 或序号变化时重挂载重放动画 */
const animKey = computed(() => `${props.mood ?? ''}-${props.moodKey ?? 0}`)

const dizzyLine = ref('')
watch(
  () => props.dizzy,
  (d) => {
    if (d) {
      dizzyLine.value = DIZZY_LINES[Math.floor(Math.random() * DIZZY_LINES.length)]
    }
  }
)

// 情绪反应气泡：新回复到来且心情有专属台词时展示
const reactionLine = ref('')
let bubbleTimer = 0
watch(
  () => [props.mood, props.moodKey] as const,
  ([mood]) => {
    const lines = mood ? REACTION_LINES[mood] : undefined
    if (!lines) return
    reactionLine.value = lines[Math.floor(Math.random() * lines.length)]
    window.clearTimeout(bubbleTimer)
    bubbleTimer = window.setTimeout(() => {
      reactionLine.value = ''
    }, 2600)
  }
)

/** 气泡内容：发晕优先，其次情绪反应 */
const bubbleText = computed(() => (props.dizzy ? dizzyLine.value : reactionLine.value))

const bubbleIcon = computed(() => {
  if (props.dizzy) return '😵‍💫'
  return (props.mood && REACTION_ICONS[props.mood]) || '💬'
})
</script>

<template>
  <div class="sprite-viewport">
    <!-- 视差层：随鼠标整体倾斜/位移 -->
    <div class="sprite-parallax" :style="{ transform: parallax }">
      <!-- 情绪动画层：一次性动效（bounce/摇晃…） -->
      <div
        :key="animKey"
        class="sprite-anim"
        :class="[mood ? `anim-${mood}` : '', dizzy ? 'anim-dizzy' : '']"
      >
        <!-- 立绘：呼吸待机常驻 + 心情滤镜 -->
        <img
          class="sprite-img"
          :class="mood ? `mood-${mood}` : ''"
          :src="currentSrc"
          alt="希亚"
          draggable="false"
        />
      </div>
    </div>

    <!-- 反应气泡：发晕 / 情绪台词 -->
    <Transition name="pop">
      <div v-if="bubbleText" class="reaction-bubble">{{ bubbleIcon }} {{ bubbleText }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.sprite-viewport {
  position: absolute;
  inset: 0;
  perspective: 1200px;
  overflow: hidden;
}

.sprite-parallax {
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  will-change: transform;
}

.sprite-anim {
  width: 100%;
  height: 100%;
  transform-origin: 50% 70%;
}

.sprite-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 50% 30%;
  user-select: none;
  /* 呼吸待机（放大 1.08 保证视差旋转时不露边） */
  animation: breathe 5.2s ease-in-out infinite;
  transition: filter 0.6s ease;
  will-change: transform, filter;
}

@keyframes breathe {
  0%,
  100% {
    transform: scale(1.08) translateY(0);
  }
  50% {
    transform: scale(1.088) translateY(-9px);
  }
}

/* ---- 心情滤镜（差分图的低成本近似） ---- */
.mood-happy {
  filter: saturate(1.18) brightness(1.04);
}

.mood-sad {
  filter: saturate(0.65) brightness(0.85);
}

.mood-angry {
  filter: saturate(1.25) brightness(0.96) hue-rotate(-8deg);
}

.mood-anxious {
  filter: contrast(1.06) brightness(0.93);
}

.mood-sleepy {
  filter: saturate(0.75) brightness(0.78);
}

.mood-shy {
  filter: saturate(1.12) brightness(1.07) hue-rotate(-6deg);
}

.mood-surprised {
  filter: contrast(1.08) brightness(1.05);
}

.mood-tsundere {
  filter: saturate(1.08) brightness(1.02);
}

/* ---- 一次性情绪动效 ---- */
.anim-happy {
  animation: anim-bounce 1.4s ease;
}

@keyframes anim-bounce {
  0%,
  100% {
    transform: translateY(0) scale(1);
  }
  30% {
    transform: translateY(-26px) scale(1.015);
  }
  55% {
    transform: translateY(0) scale(1);
  }
  75% {
    transform: translateY(-10px) scale(1.005);
  }
}

.anim-sad {
  animation: anim-sink 1.6s ease;
}

@keyframes anim-sink {
  0%,
  100% {
    transform: translateY(0);
  }
  40% {
    transform: translateY(14px) rotate(-0.8deg);
  }
  70% {
    transform: translateY(10px) rotate(-0.5deg);
  }
}

.anim-angry {
  animation: anim-shake 0.9s ease;
}

@keyframes anim-shake {
  0%,
  100% {
    transform: translateX(0);
  }
  20% {
    transform: translateX(-9px) rotate(-0.4deg);
  }
  40% {
    transform: translateX(8px) rotate(0.4deg);
  }
  60% {
    transform: translateX(-6px);
  }
  80% {
    transform: translateX(4px);
  }
}

.anim-anxious {
  animation: anim-tremble 1.4s ease-in-out;
}

@keyframes anim-tremble {
  0%,
  100% {
    transform: translate(0, 0);
  }
  25% {
    transform: translate(-3px, 1px);
  }
  50% {
    transform: translate(3px, -1px);
  }
  75% {
    transform: translate(-2px, 1px);
  }
}

.anim-sleepy {
  animation: anim-sway 2.2s ease-in-out;
}

@keyframes anim-sway {
  0%,
  100% {
    transform: rotate(0deg);
  }
  35% {
    transform: rotate(1.1deg) translateY(4px);
  }
  70% {
    transform: rotate(-0.9deg) translateY(6px);
  }
}

/* 害羞：缩成一团小幅度扭捏 */
.anim-shy {
  animation: anim-curl 1.6s ease-in-out;
}

@keyframes anim-curl {
  0%,
  100% {
    transform: scale(1) translateY(0);
  }
  30% {
    transform: scale(0.965) translateY(10px);
  }
  55% {
    transform: scale(0.955) translateY(12px) rotate(-0.6deg);
  }
  80% {
    transform: scale(0.965) translateY(9px);
  }
}

/* 惊讶：弹起后小抖 */
.anim-surprised {
  animation: anim-jolt 1.1s ease;
}

@keyframes anim-jolt {
  0%,
  100% {
    transform: translateY(0) scale(1);
  }
  18% {
    transform: translateY(-30px) scale(1.03);
  }
  38% {
    transform: translateY(0) scale(1);
  }
  52% {
    transform: translateY(-12px) scale(1.01);
  }
  70% {
    transform: translateY(0) scale(1);
  }
  82% {
    transform: translateX(-5px);
  }
  92% {
    transform: translateX(4px);
  }
}

/* 傲娇：扭过头去，又忍不住偷偷瞄回来 */
.anim-tsundere {
  animation: anim-turnaway 1.8s ease-in-out;
}

@keyframes anim-turnaway {
  0%,
  100% {
    transform: translateX(0) rotate(0deg);
  }
  25% {
    transform: translateX(26px) rotate(1.6deg);
  }
  45% {
    transform: translateX(22px) rotate(1.4deg);
  }
  65% {
    transform: translateX(-8px) rotate(-0.8deg);
  }
  82% {
    transform: translateX(14px) rotate(1deg);
  }
}

/* ---- 发晕：左右摇晃 + 轻微眩晕旋转 ---- */
.anim-dizzy {
  animation: anim-wobble 2.5s ease-in-out;
}

@keyframes anim-wobble {
  0% {
    transform: rotate(0deg);
  }
  15% {
    transform: rotate(-2.6deg) translateX(-10px);
  }
  35% {
    transform: rotate(2.4deg) translateX(10px);
  }
  55% {
    transform: rotate(-1.8deg) translateX(-7px);
  }
  75% {
    transform: rotate(1.4deg) translateX(5px);
  }
  100% {
    transform: rotate(0deg);
  }
}

/* ---- 反应气泡（发晕/情绪台词共用） ---- */
.reaction-bubble {
  position: absolute;
  top: 16%;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 20px;
  border-radius: 999px;
  background: var(--stage-glass);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
  box-shadow: var(--shadow);
  pointer-events: none;
  z-index: 3;
}

.pop-enter-active {
  transition: opacity 0.25s ease, transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.pop-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateX(-50%) scale(0.7);
}
</style>
