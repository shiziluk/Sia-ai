import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  clearChatHistory,
  getChatContext,
  getChatHistory,
  sendChat
} from '@/api/chat'
import { extractErrorMessage } from '@/api/http'
import type { ChatContext, ChatState, HistoryItem } from '@/api/types'
import { useUiStore } from '@/stores/ui'
import { nowHM } from '@/utils/format'

/** 前端消息模型：role 额外包含 system（记忆/错误提示气泡） */
export interface ChatMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  emotion?: string
  time?: string
}

let nextId = 1

/** 聊天业务状态：消息列表、上下文、好感度 */
export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const context = ref<ChatContext | null>(null)
  const state = ref<ChatState | null>(null)
  const sending = ref(false)
  const initialized = ref(false)

  /** 把后端历史记录转换为前端消息列表 */
  function fromHistory(items: HistoryItem[]): ChatMessage[] {
    return items.map((it) => ({
      id: nextId++,
      role: it.role,
      content: it.content,
      emotion: it.emotion,
      time: it.time
    }))
  }

  /** 初始化：拉取上下文 + 历史；空会话时展示欢迎语 */
  async function init(): Promise<void> {
    const ui = useUiStore()
    try {
      const [ctx, history] = await Promise.all([getChatContext(), getChatHistory()])
      context.value = ctx
      state.value = ctx.state
      ui.syncThemeWithServer(ctx.is_night)
      if (history.length > 0) {
        messages.value = fromHistory(history)
      } else {
        // 空会话：显示欢迎语（保留换行渲染）
        messages.value = [{ id: nextId++, role: 'assistant', content: ctx.welcome }]
      }
    } catch (err) {
      messages.value = [
        { id: nextId++, role: 'system', content: `⚠️ 连接希亚失败了：${extractErrorMessage(err)}` }
      ]
    } finally {
      initialized.value = true
    }
  }

  /** 发送一条消息 */
  async function send(text: string): Promise<void> {
    const trimmed = text.trim()
    if (!trimmed || sending.value) return
    const ui = useUiStore()

    messages.value.push({ id: nextId++, role: 'user', content: trimmed, time: nowHM() })
    sending.value = true
    try {
      const res = await sendChat(trimmed, ui.enableCritique)
      messages.value.push({
        id: nextId++,
        role: 'assistant',
        content: res.reply,
        emotion: res.emotion,
        time: nowHM()
      })
      // 记忆静默沉淀：不再把「记下这件事」当作一条消息说出口（沉浸感），
      // 事实已在后端入库，会自然融入她之后的对话里。
      state.value = res.state
    } catch (err) {
      messages.value.push({
        id: nextId++,
        role: 'system',
        content: `⚠️ 发送失败了：${extractErrorMessage(err)}`
      })
    } finally {
      sending.value = false
    }
  }

  /** 清空聊天记录并回到欢迎语状态 */
  async function clear(): Promise<void> {
    await clearChatHistory()
    await init()
  }

  return { messages, context, state, sending, initialized, init, send, clear }
})
