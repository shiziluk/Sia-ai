import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { PARALLAX } from '@/config/sprite'

/**
 * 伪视线跟随视差：监听全窗口指针移动，归一化为 nx/ny∈[-1,1]，
 * rAF 循环内 lerp 平滑逼近目标，输出 CSS transform 字符串。
 * 触屏 / prefers-reduced-motion 时自动禁用（enabled=false，transform 恒为空）。
 * 同时暴露指针瞬时速度（px/s），供发晕检测使用。
 */
export function useParallax() {
  const nx = ref(0)
  const ny = ref(0)
  const speed = ref(0)

  const enabled =
    !window.matchMedia('(pointer: coarse)').matches &&
    !window.matchMedia('(prefers-reduced-motion: reduce)').matches

  let tx = 0
  let ty = 0
  let raf = 0
  let running = false
  let lastPos: { x: number; y: number; t: number } | null = null
  let speedTimer = 0

  function onMove(e: PointerEvent): void {
    tx = (e.clientX / window.innerWidth) * 2 - 1
    ty = (e.clientY / window.innerHeight) * 2 - 1

    // 瞬时速度采样：位移/时间差，120ms 无移动归零
    const now = performance.now()
    if (lastPos) {
      const dt = now - lastPos.t
      if (dt > 0) {
        const dist = Math.hypot(e.clientX - lastPos.x, e.clientY - lastPos.y)
        speed.value = (dist / dt) * 1000
      }
    }
    lastPos = { x: e.clientX, y: e.clientY, t: now }
    window.clearTimeout(speedTimer)
    speedTimer = window.setTimeout(() => {
      speed.value = 0
    }, 120)

    if (!running) {
      running = true
      raf = requestAnimationFrame(tick)
    }
  }

  /** 指针离开窗口：目标回正 */
  function onLeave(): void {
    tx = 0
    ty = 0
    if (!running && (nx.value !== 0 || ny.value !== 0)) {
      running = true
      raf = requestAnimationFrame(tick)
    }
  }

  function tick(): void {
    nx.value += (tx - nx.value) * PARALLAX.lerp
    ny.value += (ty - ny.value) * PARALLAX.lerp
    const settled =
      Math.abs(tx - nx.value) < PARALLAX.settleEpsilon &&
      Math.abs(ty - ny.value) < PARALLAX.settleEpsilon
    if (settled) {
      nx.value = tx
      ny.value = ty
      running = false
      return
    }
    raf = requestAnimationFrame(tick)
  }

  const transform = computed(() => {
    if (!enabled) return ''
    const ry = (nx.value * PARALLAX.maxRotateY).toFixed(3)
    const rx = (-ny.value * PARALLAX.maxRotateX).toFixed(3)
    const px = (nx.value * PARALLAX.maxTranslateX).toFixed(2)
    const py = (ny.value * PARALLAX.maxTranslateY).toFixed(2)
    return `rotateY(${ry}deg) rotateX(${rx}deg) translate3d(${px}px, ${py}px, 0)`
  })

  onMounted(() => {
    if (!enabled) return
    window.addEventListener('pointermove', onMove, { passive: true })
    document.documentElement.addEventListener('pointerleave', onLeave)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('pointermove', onMove)
    document.documentElement.removeEventListener('pointerleave', onLeave)
    cancelAnimationFrame(raf)
    window.clearTimeout(speedTimer)
  })

  return { nx, ny, speed, transform, enabled }
}
