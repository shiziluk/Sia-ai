/** 获取今天的日期字符串（YYYY-MM-DD，本地时区） */
export function todayStr(): string {
  return formatDate(new Date())
}

/** Date → YYYY-MM-DD */
export function formatDate(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

/**
 * 从后端时间字符串中提取 HH:MM（兼容「2026-10-09 21:30:00」等格式）。
 * 提取不到时原样返回。
 */
export function shortTime(time?: string | null): string {
  if (!time) return ''
  const matches = [...time.matchAll(/(\d{1,2}:\d{2})/g)]
  const last = matches[matches.length - 1]
  return last ? last[1] : time
}

/** 当前时间 HH:MM */
export function nowHM(): string {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
