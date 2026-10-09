import { http } from './http'

/** 文本转语音，返回 audio/mpeg 的 Blob */
export function textToSpeech(text: string, voice?: string): Promise<Blob> {
  return http
    .post<Blob>('/voice/tts', { text, voice }, { responseType: 'blob' })
    .then((r) => r.data)
}

/**
 * 语音转文本。
 * @param audioBase64 webm 音频的纯 base64 字符串（不带 dataURL 前缀）
 */
export function speechToText(audioBase64: string): Promise<string> {
  return http.post<{ text: string }>('/voice/stt', { audio: audioBase64 }).then((r) => r.data.text)
}
