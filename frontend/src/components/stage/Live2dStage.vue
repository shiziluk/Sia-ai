<script setup lang="ts">
/**
 * Live2D 舞台（对应 docs/08 清单）
 * 已完成：第 1 步 渲染/眨眼/点击/视线跟随；第 2 步 情绪→表情映射（已实机核准）
 *        + 点击身体部位 → 反应表情（戳头害羞 / 戳身不满，2s 后回到当前心情）
 *        + "人物时不时消失"的根治：单上下文约束 + 原地重载 + 帧级巡检（见下方 RECOVERY 段）
 * 待接入：第 3 步 口型同步（model.speak + edge-tts）
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Application, Ticker } from 'pixi.js'
import type { Mood } from '@/utils/emotionAnim'
// 只引 Cubism 4 子包：避免主入口强制要求 Cubism 2 runtime（live2d.min.js）
// Cubism 4 runtime 向下兼容 haru 这类 Cubism 3 模型
import { Live2DModel } from '@jannchie/pixi-live2d-display/cubism4'
// 模型路径与「心情→表情」「命中区→表情」映射统一放在 config/live2d.ts（换模型只改那一处）
import {
  MODEL_URL,
  MOOD_EXPRESSION,
  BLINK_OFF_EXPRESSIONS,
  HIT_REACTION,
  REACTION_MS
} from '@/config/live2d'

/** 当前心情（由 StageView 传入，驱动表情；对应清单第 2 步·情绪驱动接入） */
const props = defineProps<{ mood?: Mood }>()

/**
 * 统一套用表情（含眨眼开关处理）。传表情名（model3.json 里的 Name，如 'f06'）即可。
 */
function setExpression(id: string): void {
  if (!model) return
  model.setEyeBlinkEnabled(!BLINK_OFF_EXPRESSIONS.has(id))
  void model.expression(id)
}

/** 复位默认表情（并把眨眼恢复回来） */
function resetExpression(): void {
  if (!model) return
  model.setEyeBlinkEnabled(true)
  // ⚠️ 坑：model.expression() 无参不是"复位"，库内部走的是 setRandomExpression()（随机表情）。
  // 复位必须显式调 resetExpression()。
  const em = (model.internalModel as unknown as {
    motionManager?: { expressionManager?: { resetExpression(): void } }
  }).motionManager?.expressionManager
  em?.resetExpression()
}

/** 点击反应覆盖：非空时压过心情映射，到点清空 */
const reaction = ref<string | null>(null)
let reactionTimer = 0

/** 当前该显示的表情 id：点击反应优先 → 心情映射 → 都没有则 null（复位待机） */
function currentExpression(): string | null {
  if (reaction.value) return reaction.value
  const m = props.mood
  return m ? MOOD_EXPRESSION[m] : null
}

/** 把「当前该显示的表情」落到模型上 */
function applyCurrentExpression(): void {
  if (!model) return
  const id = currentExpression()
  if (id) setExpression(id)
  else resetExpression()
}

/** 触发一次点击反应：立即换表情，REACTION_MS 后自动回到当前心情 */
function triggerHitReaction(area: string | undefined): void {
  const expr = area ? HIT_REACTION[area] : undefined
  if (!expr) return
  reaction.value = expr
  applyCurrentExpression()
  window.clearTimeout(reactionTimer)
  reactionTimer = window.setTimeout(() => {
    reaction.value = null
    applyCurrentExpression()
  }, REACTION_MS)
}

// 心情变化 → 换表情；模型未就绪时 applyCurrentExpression 自动跳过，加载完在 initStage 里补一次
watch(() => props.mood, () => applyCurrentExpression())

const canvasHost = ref<HTMLDivElement | null>(null)
const ready = ref(false)

/**
 * ⚠️ 以下都是「模块级」变量：本组件全应用只会有一个实例（StageView 里与写实立绘互切，切换时旧实例先卸载），
 * 因此全局同一时刻只应存在一个 WebGL 上下文。registry 把这个约束显式化，用于兜住 HMR——
 * 热更新换掉模块后，旧模块 closure 持有的 Application 会变成无人认领的"孤儿"，其上下文不会被回收。
 * 上下文数量一旦逼近浏览器上限（约 8~16 个），浏览器就会强制回收最旧的那个 → "人物时不时消失"。
 */
interface StageRegistry { app: Application | null }
const registry: StageRegistry = (() => {
  const g = globalThis as unknown as { __siaLive2dStage?: StageRegistry }
  return (g.__siaLive2dStage ??= { app: null })
})()

let app: Application | null = null
let model: Live2DModel | null = null
let resizeObserver: ResizeObserver | null = null
/** 恢复防抖定时器 */
let recoverTimer = 0
/** 帧计数：每 HEALTH_CHECK_FRAMES 帧做一次 GL 健康检查 */
let healthFrame = 0
/** 连续读到 GL 错误的巡检次数（达到 HEALTH_ERROR_STREAK 才判定"静默失效"） */
let glErrStreak = 0
/** 本轮"原地重载模型"已尝试次数：>=1 说明重载没治好，下次直接整体重建 */
let silentReloads = 0
/** 是否正在恢复中（同一时刻只允许一次恢复流程） */
let recovering = false
/** 组件已卸载（含 HMR 换模块）：用于中断尚未完成的异步加载 */
let destroyed = false
/** 最近 60s 内的恢复时间戳，用于防"恢复→又失效"的高频循环 */
const recoveries: number[] = []

/** 每 N 帧巡检一次（约 0.5s @60fps）。getError() 是同步 GL 调用，不宜每帧调用 */
const HEALTH_CHECK_FRAMES = 30
/** 连续多少次巡检都读到 GL 错误才判定失效（避免偶发错误误触发） */
const HEALTH_ERROR_STREAK = 2
/** 检测到异常后延迟多久动手恢复（给浏览器/GPU 一点恢复时间） */
const RECOVER_DEBOUNCE_MS = 400
/** 60s 内允许的最大恢复次数，超过则停止自动恢复并提示手动刷新 */
const RECOVER_LIMIT = 4

/** 需要从动作里摘掉的"朝向"参数：它们与聚焦控制器抢占同一组参数 */
const HEAD_PARAMS = new Set(['ParamAngleX', 'ParamAngleY', 'ParamAngleZ'])

type MotionCurve = { id: string }
type MotionLike = { _motionData?: { curves?: MotionCurve[] } }
type MotionManagerLike = {
  motionGroups?: Record<string, Array<MotionLike | null>>
  on?: (event: string, fn: (group: string, index: number, motion: MotionLike) => void) => void
}

/**
 * 把动作曲线改名成不存在的参数 id —— 动作应用曲线时 getParameterIndex 会返回 -1 并跳过它。
 * 用途：待机/点击动作里烘焙的 ParamAngleX/Y/Z 会叠加在聚焦值上，导致左右跟随不对称；
 * 摘掉这几条后，头/身朝向完全由聚焦控制器驱动，天然左右对称。
 */
function muteHeadCurves(motion: MotionLike | null): void {
  const curves = motion?._motionData?.curves
  if (!curves) return
  for (const curve of curves) if (HEAD_PARAMS.has(curve.id)) curve.id = `__muted__${curve.id}`
}

/** 摘掉所有动作的朝向曲线（含之后懒加载完成的动作） */
function muteAllHeadCurves(): void {
  const mm = (model?.internalModel as unknown as { motionManager?: MotionManagerLike })?.motionManager
  if (!mm) return
  mm.on?.('motionLoaded', (_group, _index, motion) => muteHeadCurves(motion))
  for (const group of Object.values(mm.motionGroups ?? {})) for (const m of group) muteHeadCurves(m)
}

/** 等比缩放 + 底部居中（galgame 立绘习惯：人物贴底） */
function fitModel(): void {
  if (!app || !model) return
  const screen = app.screen
  const baseW = model.internalModel?.width ?? 0
  const baseH = model.internalModel?.height ?? 0
  // ⚠️ 视口尺寸为 0 时必须直接返回：否则 scale 会算成 0，人物从此不可见
  // （这正是"人物突然消失、UI 还在、要 F5 才回来"的根因之一）
  if (!baseW || !baseH || screen.width < 1 || screen.height < 1) return
  const scale = (Math.min(screen.width / baseW, screen.height / baseH) * 1.35)
  model.scale.set(scale)
  model.anchor.set(0.5, 0.5)
  model.position.set(screen.width / 2, screen.height * 0.62)
}

/**
 * 把渲染尺寸同步到宿主容器，再重算缩放。
 * ⚠️ 为什么必须自己干：Pixi 的 ResizePlugin 只监听 window.resize，**不监听容器自身尺寸**。
 * 容器一旦被压成 0（面板显隐、布局切换、HMR 重建）renderer 就停在 0×0，
 * 之后即使容器恢复、只要没发生 window resize，画面就再也画不出来 —— 只能刷新页面。
 * 用 ResizeObserver 监听容器 + 健康轮询兜底，可让它在无刷新下自愈。
 */
function syncSize(): void {
  if (!app || !model) return
  const host = canvasHost.value
  if (!host) return
  const w = Math.floor(host.clientWidth)
  const h = Math.floor(host.clientHeight)
  if (w < 1 || h < 1) return
  if (app.screen.width !== w || app.screen.height !== h) app.renderer.resize(w, h)
  fitModel()
}

/**
 * 读取 WebGL 上下文是否已丢失。
 * 内嵌浏览器（IDE 的 webview）在窗口被遮挡时可能"静默"回收 GPU 上下文
 * 却不派发 webglcontextlost —— 所以除了监听事件，还必须主动轮询兜底。
 */
function isGlLost(): boolean {
  const gl = (app?.renderer as unknown as { gl?: WebGLRenderingContext } | undefined)?.gl
  return !!gl && typeof gl.isContextLost === 'function' && gl.isContextLost()
}

/**
 * 读取并清空 WebGL 错误码（0 = 无错误）。
 * ⚠️ 用途：识别"静默失效"——上下文既没 lost、也没派发 webglcontextlost，但 GPU 资源
 * （Cubism 纹理/缓冲）已被浏览器回收，于是每帧 `drawElements` 都报 INVALID_OPERATION(1282)。
 * 此时模型对象还在场景里、visible/scale 都正常，画面却整片空白（＝"人物没了、UI 还在"）。
 * 实测：健康态恒为 0；静默失效态持续返回 1282，是最可靠的判别信号。
 */
function getGlError(): number {
  const gl = (app?.renderer as unknown as { gl?: WebGLRenderingContext } | undefined)?.gl
  if (!gl || typeof gl.getError !== 'function') return 0
  return gl.getError()
}

/** 60 秒内恢复次数是否已超限（超限则停止自动恢复，提示手动刷新） */
function recoverTooOften(): boolean {
  const now = Date.now()
  while (recoveries.length && now - recoveries[0] > 60000) recoveries.shift()
  return recoveries.length >= RECOVER_LIMIT
}

/**
 * 统一恢复入口。
 * mode='lost'  ：上下文真的丢了（webglcontextlost / isContextLost()）→ 必须整体重建（换新上下文）
 * mode='silent'：上下文还活着，但每帧绘制都在报 GL 错误 1282（GPU 资源被回收的"静默失效"）
 *               → 优先「原地重载模型」：同一上下文里重新上传纹理，不新建上下文、不产生累积
 */
function scheduleRecover(mode: 'lost' | 'silent', reason: string): void {
  if (recovering || destroyed) return
  if (recoverTooOften()) {
    console.error('[Live2dStage] 显卡上下文反复异常，已停止自动恢复，请手动刷新页面（F5）')
    return
  }
  recovering = true
  ready.value = false
  console.warn('[Live2dStage] 触发恢复：', mode, reason)
  window.clearTimeout(recoverTimer)
  recoverTimer = window.setTimeout(() => { void runRecover(mode) }, RECOVER_DEBOUNCE_MS)
}

/** 执行一次恢复：能原地重载就原地重载，否则整体重建；仍失败则提示手动刷新 */
async function runRecover(mode: 'lost' | 'silent'): Promise<void> {
  recoveries.push(Date.now())
  try {
    // 上下文已丢、或原地重载已试过（没治好）→ 整体重建（会释放旧上下文并新建）
    if (mode === 'lost' || silentReloads >= 1) {
      await initStage()
    } else {
      silentReloads += 1
      const ok = await reloadModel()
      if (!ok) await initStage()
    }
  } finally {
    recovering = false
  }
  if (!ready.value) console.error('[Live2dStage] 自动恢复失败，请手动刷新页面（F5）')
}

/**
 * 帧级健康巡检（挂在 app.ticker 上，随渲染每帧运行，比 setInterval 及时得多）。
 * 负责三件事：① 检测上下文丢失；② 检测"静默失效"（每帧 GL 错误 1282）；
 * ③ 兜底同步容器尺寸。异常通常十几帧内就会被读到，故最坏恢复时间从 ~6s 降到 ~1s。
 */
function healthTick(): void {
  if (!app || destroyed) return
  if (isGlLost()) {
    glErrStreak = 0
    scheduleRecover('lost', '巡检发现上下文已丢失')
    return
  }
  if (++healthFrame < HEALTH_CHECK_FRAMES) return
  healthFrame = 0
  const err = getGlError()
  if (err === 0) {
    // 健康：重置计数（silentReloads 归零 = 上次恢复确实生效了）
    glErrStreak = 0
    silentReloads = 0
  } else if (ready.value && !recovering) {
    glErrStreak += 1
    if (glErrStreak >= HEALTH_ERROR_STREAK) {
      glErrStreak = 0
      scheduleRecover('silent', `巡检连续读到 GL 错误 ${err}`)
      return
    }
  }
  // 容器尺寸变化若没触发 ResizeObserver / window resize（例如 HMR 后旧 observer 失联），在此兜底
  syncSize()
}

function onContextLost(e: Event): void {
  e.preventDefault()
  scheduleRecover('lost', 'webglcontextlost 事件')
}

/**
 * 切走再切回是最容易丢上下文/被回收 GPU 资源的时机，回到前台时立即补检一次。
 * 这里不只看 isContextLost（旧的静默失效它返回 false），也查 GL 错误码。
 */
function onVisibilityChange(): void {
  if (document.visibilityState !== 'visible' || !app) return
  if (isGlLost()) {
    scheduleRecover('lost', '页面回到前台且上下文已丢失')
    return
  }
  if (ready.value && !recovering && getGlError()) {
    glErrStreak = 0
    scheduleRecover('silent', '页面回到前台且检测到 GL 渲染错误')
  }
}

/** 把 offset 按 half 归一化，并夹到 [-1,1] */
function clampNorm(offset: number, half: number): number {
  if (!half) return 0
  return Math.max(-1, Math.min(1, offset / half))
}

/**
 * 鼠标视线跟随（自接管，替代库的 autoFocus）。
 * 库自带映射(resolveFocusTargetFromWorld)会对模型坐标先做 `坐标/宽*2-1` 再取 atan2 的单位向量，
 * 结果大小恒为 1 且带固定偏移 —— 手感上表现为左右跟随不对称（左侧转得多、右侧几乎不跟）。
 * 这里以模型在屏幕上的中心为原点，把指针位置直接归一化到 [-1,1]，左右天然对称。
 */
function onPointerMove(e: PointerEvent): void {
  if (!app || !model) return
  const fc = (model.internalModel as unknown as {
    focusController?: { focus(x: number, y: number): void }
  }).focusController
  if (!fc) return
  const rect = app.canvas.getBoundingClientRect()
  const nx = clampNorm(e.clientX - rect.left - model.position.x, app.screen.width / 2)
  const ny = clampNorm(model.position.y - (e.clientY - rect.top), app.screen.height / 2)
  fc.focus(nx, ny)
}

/**
 * 点击处理：直接监听 canvas 原生事件，绕开 PixiJS 的命中路由。
 * 原因：autoHitTest 依赖 pointertap（需命中路由），实测点击收不到；
 * 原生监听稳定，且坐标换算与库内 event.global 一致（默认 resolution=1、stage 无缩放）。
 */
function onCanvasPointerUp(e: PointerEvent): void {
  if (!app || !model) return
  const rect = app.canvas.getBoundingClientRect()
  model.tap(e.clientX - rect.left, e.clientY - rect.top)
}

/**
 * 彻底销毁一个 Application，并确保它占用的 WebGL 上下文被真正释放。
 * ⚠️ 关键：不释放上下文就会累积，一旦逼近浏览器上限（约 8~16 个），
 * 浏览器会强制回收最旧的上下文 → 正是"人物时不时消失"的根因之一。
 * Pixi 的 destroy 内部会调 WEBGL_lose_context.loseContext()，这里再做一次兜底校验。
 */
function hardDestroyApp(application: Application): void {
  const gl = (application.renderer as unknown as { gl?: WebGLRenderingContext } | undefined)?.gl
  try { application.destroy(true, { children: true }) } catch { /* 重复销毁时忽略 */ }
  try {
    if (gl && !gl.isContextLost()) gl.getExtension('WEBGL_lose_context')?.loseContext()
  } catch { /* 部分环境无该扩展，忽略 */ }
}

/** 销毁当前舞台（可重入：init / 重载前都会调用，确保同一时刻只有一个上下文） */
function destroyStage(): void {
  window.clearTimeout(recoverTimer)
  window.clearTimeout(reactionTimer)
  healthFrame = 0
  glErrStreak = 0
  resizeObserver?.disconnect()
  resizeObserver = null
  const application = app
  app = null
  model = null // app.destroy(children:true) 会销毁它，这里只解除引用
  if (registry.app === application) registry.app = null
  if (!application) return
  application.ticker.remove(healthTick)
  application.canvas.removeEventListener('pointerup', onCanvasPointerUp)
  application.canvas.removeEventListener('webglcontextlost', onContextLost)
  hardDestroyApp(application)
}

/** 新建渲染器（新建 WebGL 上下文）并挂到宿主容器 */
async function createApp(host: HTMLDivElement): Promise<void> {
  const application = new Application()
  await application.init({
    resizeTo: host,
    backgroundAlpha: 0,
    antialias: true,
  })
  app = application
  registry.app = application
  host.appendChild(application.canvas)
  application.canvas.addEventListener('webglcontextlost', onContextLost)
  // 点击走原生监听（见 onCanvasPointerUp 注释）
  application.canvas.addEventListener('pointerup', onCanvasPointerUp)
  // 容器自身尺寸变化（面板显隐/布局切换）时同步渲染尺寸，避免停在 0×0 后画面消失
  resizeObserver = new ResizeObserver(() => syncSize())
  resizeObserver.observe(host)
  // 健康巡检挂在 app.ticker 上（帧级，随渲染运行，比 setInterval 及时）
  application.ticker.add(healthTick)
}

/** 加载 Live2D 模型到当前 app.stage（不新建上下文，供"原地重载"复用） */
async function loadModel(): Promise<void> {
  if (!app) throw new Error('app 尚未就绪')
  model = await Live2DModel.from(MODEL_URL, {
    ticker: Ticker.shared, // 挂到共享 ticker：模型自动更新（眨眼/呼吸/物理）
    autoHitTest: false, // 命中判定改由原生点击触发（见 onCanvasPointerUp）
    // 视线跟随也由我们自己接管（见 onPointerMove）：库的 autoFocus 映射会退化成单位方向向量且带偏移，
    // 实测左右跟随不对称（左侧转得多、右侧几乎不跟）
    autoFocus: false,
  })
  app.stage.addChild(model)
  syncSize()
  // 摘掉动作里的朝向曲线（见 muteHeadCurves），把视线完全交给聚焦控制器
  muteAllHeadCurves()
  // 模型就绪后按当前心情补一次表情（watch 可能在加载完成前已触发过）
  applyCurrentExpression()

  // 点击命中区域 → 播放 Tap 动作 + 按部位触发反应表情（戳头害羞 / 戳身不满）
  model.on('hit', (hitAreas: string[]) => {
    // tap() 只发 hit 事件、不会自己播动作，这里显式播放（Haru 的 Tap 组：戳头/戳身）
    void model?.motion('Tap')
    triggerHitReaction(hitAreas[0])
  })
}

/**
 * 原地重载模型：销毁旧模型、在**同一上下文**里重新加载。
 * 用于"静默失效"——上下文还活着，只是纹理等 GPU 资源被回收，重新上传资源即可恢复；
 * 无需（也不应）新建 WebGL 上下文，从根上避免上下文累积。
 */
async function reloadModel(): Promise<boolean> {
  if (!app) return false
  try {
    model?.destroy()
    model = null
    await loadModel()
    if (destroyed) return false
    ready.value = true
    glErrStreak = 0
    window.clearTimeout(recoverTimer)
    return true
  } catch (err) {
    console.warn('[Live2dStage] 原地重载模型失败，将整体重建：', err)
    return false
  }
}

/** 完整初始化：销毁旧舞台（含孤儿上下文）→ 新建上下文 → 加载模型 */
async function initStage(): Promise<void> {
  const host = canvasHost.value
  if (!host || destroyed) return
  try {
    destroyStage()
    // 兜底：清理可能残留的孤儿上下文（HMR 换模块后旧 closure 的实例）
    if (registry.app) {
      hardDestroyApp(registry.app)
      registry.app = null
    }
    ready.value = false
    await createApp(host)
    if (destroyed) return
    await loadModel()
    if (destroyed) return
    ready.value = true
    glErrStreak = 0
    silentReloads = 0
    healthFrame = 0
  } catch (err) {
    console.error('[Live2dStage] 加载失败：', err)
    ready.value = false
  }
}

onMounted(() => {
  destroyed = false
  window.addEventListener('resize', syncSize)
  window.addEventListener('pointermove', onPointerMove)
  document.addEventListener('visibilitychange', onVisibilityChange)
  void initStage()
})

onBeforeUnmount(() => {
  destroyed = true
  window.removeEventListener('resize', syncSize)
  window.removeEventListener('pointermove', onPointerMove)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  destroyStage()
})

/**
 * HMR 兜底：热更新会换掉整个模块，旧模块 closure 持有的 Application 会变成"孤儿"，
 * 其 WebGL 上下文不会被 onBeforeUnmount 回收。这里在模块被替换前主动销毁，杜绝上下文泄漏。
 * （生产构建里 import.meta.hot 为 undefined，本段不生效。）
 */
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    destroyed = true
    destroyStage()
  })
}
</script>

<template>
  <div class="live2d-viewport">
    <div ref="canvasHost" class="live2d-canvas-host"></div>
  </div>
</template>

<style scoped>
.live2d-viewport {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.live2d-canvas-host {
  position: absolute;
  inset: 0;
}

.live2d-canvas-host :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
