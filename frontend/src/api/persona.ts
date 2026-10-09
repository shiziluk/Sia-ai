import { http } from './http'
import type { PersonaResponse, PersonaUpdate } from './types'

/** 获取人格档案 + 状态 + 目标 */
export function getPersona(): Promise<PersonaResponse> {
  return http.get<PersonaResponse>('/persona').then((r) => r.data)
}

/** 更新人格档案（likes 等传逗号分隔字符串） */
export function updatePersona(payload: PersonaUpdate): Promise<PersonaResponse> {
  return http.put<PersonaResponse>('/persona', payload).then((r) => r.data)
}

/** 重置好感度（调试用） */
export function resetAffinity(): Promise<void> {
  return http.post<void>('/persona/reset-affinity').then(() => undefined)
}
