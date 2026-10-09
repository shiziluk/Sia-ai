/**
 * 后端情绪词 → 立绘心情类别（驱动动效与滤镜）。
 * 匹配模式与 utils/emoji.ts 一致：先精确匹配，再模糊包含匹配（如「开心(0.9)」也能命中「开心」）。
 */
export type Mood = '' | 'happy' | 'sad' | 'angry' | 'anxious' | 'sleepy'

const MOOD_RULES: Array<{ keywords: string[]; mood: Exclude<Mood, ''> }> = [
  { keywords: ['开心', '喜悦', '兴奋', '幸福', '快乐', '乐'], mood: 'happy' },
  { keywords: ['难过', '伤心', '沮丧', '失落', '委屈'], mood: 'sad' },
  { keywords: ['生气', '愤怒', '恼'], mood: 'angry' },
  { keywords: ['焦虑', '紧张', '担心', '不安', '害怕', '压力大'], mood: 'anxious' },
  { keywords: ['疲惫', '累', '困', '倦'], mood: 'sleepy' }
]

/** 情绪词 → 心情类别；匹配不到返回空串（回落呼吸待机） */
export function moodOf(emotion?: string | null): Mood {
  if (!emotion) return ''
  const key = emotion.trim()
  if (!key) return ''
  for (const rule of MOOD_RULES) {
    if (rule.keywords.some((k) => key === k || key.includes(k))) return rule.mood
  }
  return ''
}
