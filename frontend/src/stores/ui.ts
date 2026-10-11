import { defineStore } from 'pinia'
import { ref } from 'vue'

const THEME_KEY = 'xia-theme'
const CRITIQUE_KEY = 'xia-critique'
const TTS_KEY = 'xia-tts'
const RENDER_KEY = 'xia-render'

export type Theme = 'day' | 'night'

/** 覆层类型：互斥显示（none=全部关闭） */
export type OverlayKind = 'none' | 'history' | 'panels' | 'settings'

/** 界面状态：主题、覆层、人格自检开关、TTS 开关 */
export const useUiStore = defineStore('ui', () => {
  // 主题：用户手动切换过就锁定并持久化，否则默认跟随服务端的 is_night
  const theme = ref<Theme>((localStorage.getItem(THEME_KEY) as Theme | null) ?? 'day')
  const themeLocked = ref(Boolean(localStorage.getItem(THEME_KEY)))

  // 覆层：历史 / 面板 / 设置（互斥）
  const overlay = ref<OverlayKind>('none')

  // 人格自检开关（随 POST /api/chat 传给后端），默认开启
  const enableCritique = ref(localStorage.getItem(CRITIQUE_KEY) !== '0')

  // 语音回复开关（TTS），默认开启
  const ttsEnabled = ref(localStorage.getItem(TTS_KEY) !== '0')

  // 形象渲染模式：默认 Live2D，可切换写实立绘（原 StageView 临时开关收编至此）
  const useLive2d = ref(localStorage.getItem(RENDER_KEY) !== '0')

  /** 手动切换日间/夜间主题（锁定，不再跟随服务端） */
  function toggleTheme(): void {
    theme.value = theme.value === 'day' ? 'night' : 'day'
    themeLocked.value = true
    localStorage.setItem(THEME_KEY, theme.value)
  }

  /** 首次加载时跟随服务端的 is_night（用户未手动切换过才生效） */
  function syncThemeWithServer(isNight: boolean): void {
    if (themeLocked.value) return
    theme.value = isNight ? 'night' : 'day'
  }

  function toggleCritique(): void {
    enableCritique.value = !enableCritique.value
    localStorage.setItem(CRITIQUE_KEY, enableCritique.value ? '1' : '0')
  }

  function openOverlay(kind: Exclude<OverlayKind, 'none'>): void {
    overlay.value = kind
  }

  function closeOverlay(): void {
    overlay.value = 'none'
  }

  function toggleTts(): void {
    ttsEnabled.value = !ttsEnabled.value
    localStorage.setItem(TTS_KEY, ttsEnabled.value ? '1' : '0')
  }

  function toggleRenderMode(): void {
    useLive2d.value = !useLive2d.value
    localStorage.setItem(RENDER_KEY, useLive2d.value ? '1' : '0')
  }

  return {
    theme,
    themeLocked,
    overlay,
    enableCritique,
    ttsEnabled,
    useLive2d,
    toggleTheme,
    syncThemeWithServer,
    toggleCritique,
    openOverlay,
    closeOverlay,
    toggleTts,
    toggleRenderMode
  }
})
