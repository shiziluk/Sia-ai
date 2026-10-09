import axios from 'axios'

/**
 * 统一的 axios 实例。
 * baseURL 固定为 /api，开发环境由 Vite proxy 转发到后端，生产环境同源部署，免 CORS。
 */
export const http = axios.create({
  baseURL: '/api',
  timeout: 120000
})

/** 从 axios 错误中提取可读的中文错误信息 */
export function extractErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { detail?: unknown } | undefined
    const detail = data?.detail
    if (typeof detail === 'string' && detail) return detail
    if (detail != null) return JSON.stringify(detail)
    return err.message
  }
  return err instanceof Error ? err.message : String(err)
}
