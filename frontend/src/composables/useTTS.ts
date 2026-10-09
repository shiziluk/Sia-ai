import { onBeforeUnmount, ref, type Ref } from 'vue'
import { textToSpeech } from '@/api/voice'

/**
 * TTS 语音回复：合成 mp3 blob → Audio 播放。
 * - 打字机与语音并行，互不等待；
 * - 自动播放被浏览器拦截（NotAllowedError）时置 autoplayBlocked=true，
 *   保留音频等用户点击「点此播放」胶囊再播；
 * - 统一 revoke blob URL，组件卸载时停止。
 */
export function useTTS(enabled: Ref<boolean>) {
  const autoplayBlocked = ref(false)
  const speaking = ref(false)

  let audio: HTMLAudioElement | null = null
  let url: string | null = null
  let seq = 0 // 播放请求序号：新请求/stop 会使在途合成结果失效

  /** 播放一段文本（TTS 合成失败时静默，不打断文字对话） */
  async function speak(text: string): Promise<void> {
    stop()
    if (!enabled.value) return
    // 去掉 emoji 等符号，避免 TTS 念出"笑哭脸"之类的内容
    const clean = text
      .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}]/gu, '')
      .trim()
    if (!clean) return

    const mySeq = ++seq
    try {
      const blob = await textToSpeech(clean)
      if (mySeq !== seq || !enabled.value) return
      url = URL.createObjectURL(blob)
      audio = new Audio(url)
      audio.onended = () => stop()
      audio.onerror = () => stop()
      try {
        await audio.play()
        if (mySeq !== seq) {
          stop()
          return
        }
        speaking.value = true
        autoplayBlocked.value = false
      } catch (err) {
        if ((err as DOMException)?.name === 'NotAllowedError') {
          // 自动播放被拦：保留音频等用户手动触发
          autoplayBlocked.value = true
        } else {
          stop()
        }
      }
    } catch {
      // 合成失败静默
    }
  }

  /** 自动播放被拦时，由用户点击胶囊触发播放 */
  function resume(): void {
    if (!audio || !autoplayBlocked.value) return
    void audio
      .play()
      .then(() => {
        speaking.value = true
        autoplayBlocked.value = false
      })
      .catch(() => stop())
  }

  /** 停止当前播放并丢弃在途请求 */
  function stop(): void {
    seq += 1
    if (audio) {
      audio.pause()
      audio.onended = null
      audio.onerror = null
    }
    if (url) URL.revokeObjectURL(url)
    audio = null
    url = null
    speaking.value = false
    autoplayBlocked.value = false
  }

  onBeforeUnmount(stop)

  return { speaking, autoplayBlocked, speak, resume, stop }
}
