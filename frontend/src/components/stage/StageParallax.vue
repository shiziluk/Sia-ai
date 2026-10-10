<script setup lang="ts">
/**
 * 写实立绘 2.5D 深度视差（对应 docs/09_写实立绘2.5D深度视差调研与实施清单.md 第 4~7 步）
 *
 * 实现选型：PixiJS v8 Application + 单个全屏 Mesh + 自定义着色器。
 * - 用 Mesh 而不是 Filter：Mesh 的 aUV 本身就在「插画 UV 空间」里，
 *   插画与深度图共用同一套 UV 采样，天然像素级对位，不必在滤镜里反推屏幕↔图像坐标映射。
 * - 深度视差：uv += ndc * (d - 0.5) * uStrength（近处动得多、远处动得少）
 * - 鼠标视差 + 呼吸微动全部由 uniform 驱动，不换资源、不重建 WebGL 上下文
 * - 边缘保护：Mesh 四边形比视口外扩 margin，视差偏移采样到视口外时仍取到真实像素；片元里再 clamp UV
 * - 复用 Live2dStage 建立的全局单实例 WebGL 上下文注册表，保证任一时刻只有一个 Application；
 *   import.meta.hot.dispose() 在热更新前主动回收
 * - WebGL 不可用 / 上下文丢失 → emit('failed')，由 StageSprite 回退到现有 <img> + CSS 方案
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import {
  Application,
  Assets,
  GlProgram,
  Mesh,
  MeshGeometry,
  Shader,
  Ticker,
  UniformGroup
} from 'pixi.js'
import type { Texture } from 'pixi.js'
import { useUiStore } from '@/stores/ui'
import { PARALLAX_2D5, PARALLAX_SCENES } from '@/config/sprite'
import type { StageSceneKey } from '@/config/sprite'

const props = defineProps<{
  /** 指针归一化坐标（-1~1，useParallax 提供），驱动鼠标视差 */
  pointerX?: number
  pointerY?: number
}>()

const emit = defineEmits<{ failed: [] }>()

const { theme } = storeToRefs(useUiStore())
const host = ref<HTMLDivElement | null>(null)

/**
 * 顶点着色器：与 Pixi 默认网格着色器一致，用全局投影矩阵把「屏幕像素坐标」变换到裁剪空间。
 * uProjectionMatrix / uWorldTransformMatrix 由 Pixi 全局 uniform 系统按名字自动绑定。
 */
const VERTEX = `
in vec2 aPosition;
in vec2 aUV;
out vec2 vUV;

uniform mat3 uProjectionMatrix;
uniform mat3 uWorldTransformMatrix;

void main(void)
{
    vUV = aUV;
    mat3 mvp = uProjectionMatrix * uWorldTransformMatrix;
    gl_Position = vec4((mvp * vec3(aPosition, 1.0)).xy, 0.0, 1.0);
}
`

/**
 * 片元着色器：插画与深度图共用 aUV 空间（深度图白=近）。
 * uVisRect = 视口四角在插画 UV 空间中的矩形 (u0, v0, u1, v1)，用于把视差方向归一到可见区域。
 */
const FRAGMENT = `
in vec2 vUV;
out vec4 finalColor;

uniform sampler2D uIllustration;
uniform sampler2D uDepth;

uniform float uStrength;
uniform vec2 uPointer;
uniform float uBreath;
uniform vec4 uVisRect;

void main(void)
{
    float d = texture(uDepth, clamp(vUV, 0.0, 1.0)).r;
    float w = d - 0.5;

    vec2 visCenter = vec2((uVisRect.x + uVisRect.z) * 0.5, (uVisRect.y + uVisRect.w) * 0.5);
    vec2 visHalf = vec2((uVisRect.z - uVisRect.x) * 0.5, (uVisRect.w - uVisRect.y) * 0.5);
    vec2 ndc = (vUV - visCenter) / visHalf;

    vec2 uv = vUV;
    uv += ndc * w * uStrength;
    uv += uPointer * w * uStrength;
    uv += ndc * uBreath * (0.4 + d * 0.6);

    finalColor = texture(uIllustration, clamp(uv, 0.001, 0.999));
}
`

/**
 * ⚠️ 与 Live2dStage 共用同一份全局注册表（同一个 globalThis 键）：
 * 两条形象路线由 StageView 互斥切换，任一时刻全应用只应存在一个 WebGL Application。
 * 热更新换掉模块后旧 closure 的实例会变成无人认领的"孤儿"，靠这份注册表兜住回收。
 */
interface StageRegistry {
  app: Application | null
}
const registry: StageRegistry = (() => {
  const g = globalThis as unknown as { __siaLive2dStage?: StageRegistry }
  return (g.__siaLive2dStage ??= { app: null })
})()

let app: Application | null = null
let mesh: Mesh | null = null
let uniforms: UniformGroup | null = null
let resizeObserver: ResizeObserver | null = null
/** 呼吸相位累计（毫秒） */
let breathMs = 0
/** 组件已卸载（含 HMR 换模块）：用于中断尚未完成的异步加载 */
let destroyed = false
/** 当前已加载的场景（用于 theme 切换去重，日/夜同源时跳过重载） */
let loadedKey: StageSceneKey | null = null
/** 保留插画引用：fitGeometry 需要它的原始宽高 */
let illustration: Texture | null = null
/** 指针 uniform 数组（与 UniformGroup 共享引用，改数组即改 uniform） */
let pointer: Float32Array | null = null
/** 视口在插画 UV 空间中的矩形：与 UniformGroup 共享引用 */
let visRect: Float32Array | null = null

/** WebGL 可用性探测（不可用直接回退静态图） */
function hasWebgl(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}

/**
 * 按 cover 布局把视口映射到插画 UV，并把 Mesh 四边形外扩 margin 写入几何与 uVisRect。
 * 还原现有立绘的 object-fit: cover + object-position: 50% 30%。
 */
function fitGeometry(): void {
  if (!app || !mesh || !illustration) return
  const sw = app.screen.width
  const sh = app.screen.height
  const iw = illustration.width
  const ih = illustration.height
  // ⚠️ 视口尺寸为 0 时必须直接返回，否则会写入无效几何
  if (sw < 1 || sh < 1 || !iw || !ih) return

  const cover = Math.max(sw / iw, sh / ih)
  const dispW = iw * cover
  const dispH = ih * cover
  const posX = -(dispW - sw) * 0.5
  const posY = -(dispH - sh) * PARALLAX_2D5.objectPositionY

  // 视口四角在插画 UV 空间中的坐标
  const u0 = -posX / dispW
  const u1 = (sw - posX) / dispW
  const v0 = -posY / dispH
  const v1 = (sh - posY) / dispH

  // 四边形相对视口外扩，视差偏移采样到视口外时仍取到真实像素
  const mx = sw * PARALLAX_2D5.margin
  const my = sh * PARALLAX_2D5.margin
  const sx = (u1 - u0) / sw
  const sy = (v1 - v0) / sh

  const geometry = mesh.geometry as MeshGeometry
  geometry.positions = new Float32Array([
    -mx, -my,
    sw + mx, -my,
    sw + mx, sh + my,
    -mx, sh + my
  ])
  geometry.uvs = new Float32Array([
    u0 - mx * sx, v0 - my * sy,
    u1 + mx * sx, v0 - my * sy,
    u1 + mx * sx, v1 + my * sy,
    u0 - mx * sx, v1 + my * sy
  ])

  if (visRect) {
    visRect[0] = u0
    visRect[1] = v0
    visRect[2] = u1
    visRect[3] = v1
  }
}

/** 每帧更新视差 uniform（指针视差 + 呼吸微动） */
function tick(deltaMS: number): void {
  if (!uniforms || !pointer) return
  breathMs += deltaMS
  const phase = (breathMs / PARALLAX_2D5.breathPeriodMs) * Math.PI * 2
  uniforms.uniforms.uBreath = Math.sin(phase) * PARALLAX_2D5.breathAmp
  const gain = PARALLAX_2D5.pointerGain
  pointer[0] = (props.pointerX ?? 0) * gain
  pointer[1] = (props.pointerY ?? 0) * gain
}

function onTick(ticker: Ticker): void {
  tick(ticker.deltaMS)
}

/** 彻底销毁一个 Application，并确保它占用的 WebGL 上下文被真正释放 */
function hardDestroyApp(application: Application): void {
  const gl = (application.renderer as unknown as { gl?: WebGLRenderingContext } | undefined)?.gl
  try {
    application.destroy(true, { children: true })
  } catch {
    /* 重复销毁时忽略 */
  }
  try {
    if (gl && !gl.isContextLost()) gl.getExtension('WEBGL_lose_context')?.loseContext()
  } catch {
    /* 部分环境无该扩展，忽略 */
  }
}

/** 销毁当前舞台（可重入，确保同一时刻只有一个上下文） */
function destroyStage(): void {
  resizeObserver?.disconnect()
  resizeObserver = null
  const application = app
  app = null
  mesh = null
  uniforms = null
  illustration = null
  pointer = null
  visRect = null
  loadedKey = null
  if (registry.app === application) registry.app = null
  if (!application) return
  application.ticker.remove(onTick)
  application.canvas.removeEventListener('webglcontextlost', onContextLost)
  hardDestroyApp(application)
}

/** 上下文丢失：直接回退到静态 <img> 方案（由 StageSprite 接管） */
function onContextLost(e: Event): void {
  e.preventDefault()
  emit('failed')
}

/** 切换日/夜：只换纹理资源，不重建组件与上下文 */
async function loadScene(key: StageSceneKey): Promise<void> {
  if (!app || !mesh) return
  const scene = PARALLAX_SCENES[key]
  const [ill, depth] = await Promise.all([
    Assets.load<Texture>(scene.src),
    Assets.load<Texture>(scene.depth)
  ])
  if (destroyed || !mesh) return
  illustration = ill
  const shader = mesh.shader
  // Mesh.shader 在类型上是可空的；正常流程里刚初始化完必然存在
  if (!shader) return
  shader.resources.uIllustration = ill.source
  shader.resources.uIllustrationSampler = ill.source.style
  shader.resources.uDepth = depth.source
  shader.resources.uDepthSampler = depth.source.style
  loadedKey = key
  fitGeometry()
}

/** 完整初始化：销毁旧舞台 → 新建上下文 → 建 Mesh → 载图 */
async function initStage(): Promise<void> {
  const el = host.value
  if (!el || destroyed) return
  if (!hasWebgl()) {
    emit('failed')
    return
  }
  try {
    destroyStage()
    // 兜底：清理可能残留的孤儿上下文（HMR 换模块后旧 closure 的实例）
    if (registry.app) {
      hardDestroyApp(registry.app)
      registry.app = null
    }

    const application = new Application()
    await application.init({
      resizeTo: el,
      backgroundAlpha: 0,
      antialias: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      autoDensity: true
    })
    if (destroyed) {
      hardDestroyApp(application)
      return
    }
    app = application
    registry.app = application
    el.appendChild(application.canvas)

    const scene = PARALLAX_SCENES[theme.value]
    const [ill, depth] = await Promise.all([
      Assets.load<Texture>(scene.src),
      Assets.load<Texture>(scene.depth)
    ])
    if (destroyed) {
      destroyStage()
      return
    }
    illustration = ill
    loadedKey = theme.value

    pointer = new Float32Array([0, 0])
    visRect = new Float32Array([0, 0, 1, 1])
    uniforms = new UniformGroup({
      uStrength: { value: PARALLAX_2D5.strength, type: 'f32' },
      uPointer: { value: pointer, type: 'vec2<f32>' },
      uBreath: { value: 0, type: 'f32' },
      uVisRect: { value: visRect, type: 'vec4<f32>' }
    })

    const shader = new Shader({
      glProgram: GlProgram.from({ vertex: VERTEX, fragment: FRAGMENT, name: 'depth-parallax' }),
      resources: {
        uIllustration: ill.source,
        uIllustrationSampler: ill.source.style,
        uDepth: depth.source,
        uDepthSampler: depth.source.style,
        parallaxUniforms: uniforms
      }
    })

    const geometry = new MeshGeometry({
      positions: new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]),
      uvs: new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]),
      indices: new Uint32Array([0, 1, 2, 0, 2, 3])
    })
    const created = new Mesh({ geometry, shader }) as unknown as Mesh
    mesh = created
    application.stage.addChild(created)
    fitGeometry()

    // resizeTo 只监听 window.resize；容器自身尺寸变化（面板显隐）需自行重算几何
    resizeObserver = new ResizeObserver(() => {
      if (app) fitGeometry()
    })
    resizeObserver.observe(el)

    application.ticker.add(onTick)
    application.canvas.addEventListener('webglcontextlost', onContextLost)
  } catch (err) {
    console.error('[StageParallax] 初始化失败：', err)
    emit('failed')
  }
}

// 日/夜切换：换图（同源资源时自动跳过）
watch(theme, (next) => {
  if (!app || loadedKey === next) return
  void loadScene(next).catch((err) => console.error('[StageParallax] 切换日/夜失败：', err))
})

onMounted(() => {
  destroyed = false
  void initStage()
})

onBeforeUnmount(() => {
  destroyed = true
  destroyStage()
})

/**
 * HMR 兜底：热更新会换掉整个模块，旧 closure 持有的 Application 会变成"孤儿"，
 * 其 WebGL 上下文不会被 onBeforeUnmount 回收。这里在模块被替换前主动销毁。
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
  <div ref="host" class="parallax-viewport"></div>
</template>

<style scoped>
.parallax-viewport {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.parallax-viewport :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
