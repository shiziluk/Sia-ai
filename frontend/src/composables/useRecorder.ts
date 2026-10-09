import { onBeforeUnmount, ref } from 'vue'
import { speechToText } from '@/api/voice'

interface RecorderOptions {
  /** 识别成功回调（返回识别文本） */
  onText: (text: string) => void
  /** 各类失败（不支持/权限/太短/识别失败）提示回调 */
  onError: (message: string) => void
}

/**
 * 麦克风录音 → webm base64 → POST /api/voice/stt。
 * 录音时长不足 1 秒视为「录音太短」，不上传。
 */
export function useRecorder(options: RecorderOptions) {
  const recording = ref(false)
  const busy = ref(false)

  let recorder: MediaRecorder | null = null
  let chunks: Blob[] = []
  let startedAt = 0

  /** 点击麦克风：未录音则开始，录音中则停止并识别 */
  async function toggle(): Promise<void> {
    if (recording.value) {
      recorder?.stop()
      return
    }
    // 环境能力检测
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      options.onError('当前浏览器不支持语音输入')
      return
    }
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      options.onError('无法访问麦克风，请检查权限')
      return
    }

    chunks = []
    recorder = new MediaRecorder(stream)
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data)
    }
    recorder.onstop = () => {
      // 释放麦克风
      stream.getTracks().forEach((t) => t.stop())
      recording.value = false
      const duration = Date.now() - startedAt
      const type = recorder?.mimeType || 'audio/webm'
      recorder = null

      if (duration < 1000) {
        options.onError('录音太短，希亚没听清～')
        return
      }
      void transcribe(new Blob(chunks, { type }))
    }
    recorder.start()
    startedAt = Date.now()
    recording.value = true
  }

  /** 上传音频做语音识别 */
  async function transcribe(blob: Blob): Promise<void> {
    busy.value = true
    try {
      const base64 = await blobToBase64(blob)
      const text = await speechToText(base64)
      if (!text.trim()) {
        options.onError('希亚没听清，再试一次吧')
        return
      }
      options.onText(text)
    } catch {
      // 后端 422 = 识别失败
      options.onError('语音识别失败，请重试')
    } finally {
      busy.value = false
    }
  }

  onBeforeUnmount(() => {
    // 组件卸载时停止录音并释放麦克风
    if (recorder && recorder.state !== 'inactive') recorder.stop()
    recorder = null
  })

  return { recording, busy, toggle }
}

/** Blob → 纯 base64（去掉 dataURL 前缀） */
function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result)
      const comma = result.indexOf(',')
      resolve(comma >= 0 ? result.slice(comma + 1) : result)
    }
    reader.onerror = () => reject(new Error('读取音频失败'))
    reader.readAsDataURL(blob)
  })
}
