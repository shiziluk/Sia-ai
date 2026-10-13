import { http } from './http'
import type { ChatContext, ChatResponse, Diary, HistoryItem, SearchResult } from './types'

/** 获取聊天上下文（欢迎语、环境状态、好感度） */
export function getChatContext(): Promise<ChatContext> {
  return http.get<ChatContext>('/chat/context').then((r) => r.data)
}

/** 获取历史聊天记录 */
export function getChatHistory(limit = 100): Promise<HistoryItem[]> {
  return http.get<HistoryItem[]>('/chat/history', { params: { limit } }).then((r) => r.data)
}

/** 发送消息 */
export function sendChat(text: string, enablePolish: boolean): Promise<ChatResponse> {
  return http
    .post<ChatResponse>('/chat', { text, enable_polish: enablePolish })
    .then((r) => r.data)
}

/** 清空聊天记录 */
export function clearChatHistory(): Promise<void> {
  return http.delete<void>('/chat/history').then(() => undefined)
}

/** 按日期范围 + 关键词搜索聊天记录（最新在前） */
export function searchChat(start: string, end: string, q: string): Promise<SearchResult[]> {
  return http
    .get<SearchResult[]>('/chat/search', { params: { start, end, q } })
    .then((r) => r.data)
}

/** 获取某天的情绪日记 */
export function getDiary(date: string): Promise<Diary> {
  return http.get<Diary>(`/chat/diary/${date}`).then((r) => r.data)
}
