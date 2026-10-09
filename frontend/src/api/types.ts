/** 后端返回的好感度状态 */
export interface ChatState {
  trust: number
  intimacy_level: number
  intimacy_label: string
  tip?: string
}

/** 聊天上下文（欢迎语、环境状态等） */
export interface ChatContext {
  welcome: string
  user_name: string
  days_to_birthday: number
  is_birthday: boolean
  is_thunderstorm: boolean
  is_night: boolean
  notify_birthday_eve: boolean
  notify_thunder: boolean
  notify_idle: boolean
  state: ChatState
}

/** 单条聊天记录 */
export interface HistoryItem {
  role: 'user' | 'assistant'
  content: string
  emotion?: string
  time?: string
}

/** 发送消息的响应 */
export interface ChatResponse {
  reply: string
  emotion: string
  saved_memory: string
  state: ChatState
}

/** 聊天记录搜索结果（一条对话对） */
export interface SearchResult {
  time: string
  user: string
  assistant: string
}

/** 今日日记（empty=true 时只有 text，否则为结构化数据） */
export interface Diary {
  date: string
  empty: boolean
  text?: string
  main_emotion?: string
  /** 情绪流：兼容纯字符串或对象形式 */
  emotion_sequence?: Array<string | { emotion?: string }>
  keywords?: string[]
  memories?: string[]
  night_count?: number
}

/** 记忆库列表 */
export interface MemoriesResponse {
  count: number
  items: string[]
}

/** 人格目标 */
export interface Goal {
  id: string
  description: string
  status: string
  cooldown_days: number
  last_triggered: string | null
}

/** 人格档案（GET /api/persona） */
export interface PersonaResponse {
  profile: {
    name: string
    birthday: string
    likes: string[]
    dislikes: string[]
    fears: string[]
    recent_events: string[]
  }
  state: ChatState
  goals: Goal[]
}

/** 更新人格档案的请求体（likes 等传逗号分隔字符串） */
export interface PersonaUpdate {
  name?: string
  birthday?: string
  likes?: string
  dislikes?: string
  fears?: string
  recent_events?: string
}
