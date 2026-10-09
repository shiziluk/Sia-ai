import { defineStore } from 'pinia'
import { ref } from 'vue'

const THEME_KEY = 'xia-theme'
const CRITIQUE_KEY = 'xia-critique'

export type Theme = 'day' | 'night'

/** 界面状态：主题、侧边栏抽屉、人格自检开关 */
export const useUiStore = defineStore('ui', () => {
  // 主题：用户手动切换过就锁定并持久化，否则默认跟随服务端的 is_night
  const theme = ref<Theme>((localStorage.getItem(THEME_KEY) as Theme | null) ?? 'day')
  const themeLocked = ref(Boolean(localStorage.getItem(THEME_KEY)))

  // 移动端侧边栏抽屉开关
  const sidebarOpen = ref(false)

  // 人格自检开关（随 POST /api/chat 传给后端），默认开启
  const enableCritique = ref(localStorage.getItem(CRITIQUE_KEY) !== '0')

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

  return { theme, themeLocked, sidebarOpen, enableCritique, toggleTheme, syncThemeWithServer, toggleCritique }
})
