import { http } from './http'
import type { MemoriesResponse } from './types'

/** 获取记忆库列表 */
export function getMemories(): Promise<MemoriesResponse> {
  return http.get<MemoriesResponse>('/memories').then((r) => r.data)
}

/** 手动添加一条记忆 */
export function addMemory(text: string): Promise<void> {
  return http.post<void>('/memories', { text }).then(() => undefined)
}
