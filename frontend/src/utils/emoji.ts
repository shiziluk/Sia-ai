/** 情绪 → emoji 映射（前端常量，覆盖后端常用情绪词） */
const EMOJI_MAP: Record<string, string> = {
  开心: '😊',
  喜悦: '😄',
  兴奋: '🎉',
  幸福: '🥰',
  难过: '😢',
  伤心: '😭',
  沮丧: '😞',
  疲惫: '🥱',
  累: '😴',
  困: '😪',
  焦虑: '😰',
  紧张: '😟',
  压力大: '😓',
  生气: '😠',
  愤怒: '😡',
  平静: '🙂',
  普通: '🙂',
  没事: '🙂'
}

/** 默认 emoji */
export const DEFAULT_EMOJI = '🙂'

/**
 * 情绪词转 emoji：先精确匹配，再模糊包含匹配（如「开心(0.9)」也能命中「开心」）。
 */
export function emotionEmoji(emotion?: string | null): string {
  if (!emotion) return DEFAULT_EMOJI
  const key = emotion.trim()
  if (EMOJI_MAP[key]) return EMOJI_MAP[key]
  const hit = Object.keys(EMOJI_MAP).find((k) => key.includes(k))
  return hit ? EMOJI_MAP[hit] : DEFAULT_EMOJI
}
