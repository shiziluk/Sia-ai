/**
 * 情绪/文本 → 立绘心情（驱动动效、滤镜与台词气泡）。
 * 情绪词匹配模式与 utils/emoji.ts 一致：先精确匹配，再模糊包含匹配（如「开心(0.9)」也能命中「开心」）。
 */
export type Mood =
  | ''
  | 'happy'
  | 'sad'
  | 'angry'
  | 'anxious'
  | 'sleepy'
  | 'shy'
  | 'surprised'
  | 'tsundere'

const MOOD_RULES: Array<{ keywords: string[]; mood: Exclude<Mood, ''> }> = [
  { keywords: ['开心', '喜悦', '兴奋', '幸福', '快乐', '乐'], mood: 'happy' },
  { keywords: ['难过', '伤心', '沮丧', '失落', '委屈'], mood: 'sad' },
  { keywords: ['生气', '愤怒', '恼'], mood: 'angry' },
  { keywords: ['焦虑', '紧张', '担心', '不安', '害怕', '压力大'], mood: 'anxious' },
  { keywords: ['疲惫', '累', '困', '倦'], mood: 'sleepy' },
  { keywords: ['害羞', '脸红', '不好意思', '心动'], mood: 'shy' },
  { keywords: ['惊讶', '吃惊', '震惊', '意外'], mood: 'surprised' },
  { keywords: ['傲娇', '嘴硬', '别扭'], mood: 'tsundere' }
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

// ---- 她对"你说的话"的反应：文本关键词触发（撩她→害羞，夸她→傲娇，惊叹→惊讶） ----

/** 撩她的话 → 她害羞 */
const LOVE_WORDS = ['喜欢你', '爱你', '抱抱', '亲亲', '心动', '撩', '想你']

/** 夸她的话 → 她傲娇（嘴上嫌弃心里美） */
const PRAISE_WORDS = ['可爱', '漂亮', '好看', '美丽', '厉害', '聪明', '温柔', '夸', '最棒', '天才']

/** 惊叹的话 → 她惊讶 */
const AMAZED_WORDS = ['竟然', '居然', '哇', '太强了', '难以置信', '惊了']

/**
 * 综合判定她这一刻的心情：
 * 1) 你说的内容先看（撩/夸/惊叹 → 害羞/傲娇/惊讶，这是"她对你的话做反应"）；
 * 2) 否则按你当前的情绪标签直传（你难过时她陪着你低落）。
 */
export function reactionMood(userText: string, userEmotion?: string | null): Mood {
  const text = userText ?? ''
  if (text) {
    if (LOVE_WORDS.some((w) => text.includes(w))) return 'shy'
    if (PRAISE_WORDS.some((w) => text.includes(w))) return 'tsundere'
    if (AMAZED_WORDS.some((w) => text.includes(w))) return 'surprised'
  }
  return moodOf(userEmotion)
}
