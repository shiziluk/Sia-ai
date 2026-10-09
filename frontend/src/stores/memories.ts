import { defineStore } from 'pinia'
import { ref } from 'vue'
import { addMemory, getMemories } from '@/api/memories'
import type { MemoriesResponse } from '@/api/types'

/** 记忆库状态 */
export const useMemoriesStore = defineStore('memories', () => {
  const count = ref(0)
  const items = ref<string[]>([])
  const loading = ref(false)

  /** 拉取记忆列表 */
  async function load(): Promise<void> {
    loading.value = true
    try {
      const res: MemoriesResponse = await getMemories()
      count.value = res.count
      items.value = res.items
    } finally {
      loading.value = false
    }
  }

  /** 手动添加一条记忆，成功后刷新列表 */
  async function add(text: string): Promise<void> {
    await addMemory(text)
    await load()
  }

  return { count, items, loading, load, add }
})
