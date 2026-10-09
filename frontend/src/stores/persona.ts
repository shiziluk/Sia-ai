import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getPersona, resetAffinity, updatePersona } from '@/api/persona'
import type { PersonaResponse, PersonaUpdate } from '@/api/types'

/** 人格档案业务状态 */
export const usePersonaStore = defineStore('persona', () => {
  const data = ref<PersonaResponse | null>(null)
  const loading = ref(false)
  const saving = ref(false)

  /** 目标列表（只读展示） */
  const goals = computed(() => data.value?.goals ?? [])

  /** 拉取人格档案（设置页回填用） */
  async function load(): Promise<void> {
    loading.value = true
    try {
      data.value = await getPersona()
    } finally {
      loading.value = false
    }
  }

  /** 保存人格档案修改 */
  async function save(payload: PersonaUpdate): Promise<void> {
    saving.value = true
    try {
      data.value = await updatePersona(payload)
    } finally {
      saving.value = false
    }
  }

  /** 重置好感度（调试用），成功后刷新档案 */
  async function reset(): Promise<void> {
    await resetAffinity()
    await load()
  }

  return { data, goals, loading, saving, load, save, reset }
})
