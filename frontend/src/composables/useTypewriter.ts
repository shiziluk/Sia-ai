import { onBeforeUnmount, ref } from 'vue'

/**
 * 打字机效果：按码点逐字显示（emoji 等代理对不会被拆坏）。
 * 新文本调用 start 会打断当前重放；skip 直接显示全文。
 */
export function useTypewriter(intervalMs = 35) {
  const typedText = ref('')
  const typing = ref(false)

  let chars: string[] = []
  let idx = 0
  let timer = 0

  function stopTimer(): void {
    if (timer) {
      window.clearInterval(timer)
      timer = 0
    }
    typing.value = false
  }

  function start(text: string): void {
    stopTimer()
    chars = Array.from(text)
    idx = 0
    typedText.value = ''
    if (chars.length === 0) return
    typing.value = true
    timer = window.setInterval(() => {
      idx += 1
      typedText.value = chars.slice(0, idx).join('')
      if (idx >= chars.length) stopTimer()
    }, intervalMs)
  }

  function skip(): void {
    if (!typing.value) return
    stopTimer()
    typedText.value = chars.join('')
  }

  onBeforeUnmount(stopTimer)

  return { typedText, typing, start, skip }
}
