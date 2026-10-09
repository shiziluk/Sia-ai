import { onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { DIZZY } from '@/config/sprite'

/**
 * 发晕状态机：idle → dizzy(DIZZY.dizzyMs) → 冷却(DIZZY.cooldownMs) → idle。
 * 触发条件：指针速度超过阈值的采样在时间窗口内累计达到次数。
 * 冷却期内重复超速一律忽略。
 */
export function useDizzy(speed: Ref<number>) {
  const dizzy = ref(false)

  let hits: number[] = []
  let dizzyTimer = 0
  let cooldownUntil = 0

  watch(speed, (v) => {
    if (dizzy.value || performance.now() < cooldownUntil) return
    if (v < DIZZY.speedThreshold) return

    const now = performance.now()
    hits = hits.filter((t) => now - t <= DIZZY.windowMs)
    hits.push(now)
    if (hits.length >= DIZZY.hitsNeeded) {
      hits = []
      dizzy.value = true
      cooldownUntil = now + DIZZY.dizzyMs + DIZZY.cooldownMs
      dizzyTimer = window.setTimeout(() => {
        dizzy.value = false
      }, DIZZY.dizzyMs)
    }
  })

  onBeforeUnmount(() => {
    window.clearTimeout(dizzyTimer)
  })

  return { dizzy }
}
