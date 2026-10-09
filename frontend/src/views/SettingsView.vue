<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { extractErrorMessage } from '@/api/http'
import type { PersonaUpdate } from '@/api/types'
import { useChatStore } from '@/stores/chat'
import { usePersonaStore } from '@/stores/persona'

const persona = usePersonaStore()
const chat = useChatStore()

// 表单：likes 等多值字段用逗号分隔字符串编辑
const form = reactive({
  name: '',
  birthday: '',
  likes: '',
  dislikes: '',
  fears: '',
  recent_events: ''
})

const notice = ref('')
const error = ref('')
const busy = ref(false)
let noticeTimer: number | undefined

onMounted(async () => {
  try {
    if (!persona.data) await persona.load()
    fillForm()
  } catch (err) {
    error.value = `加载档案失败：${extractErrorMessage(err)}`
  }
})

/** 用后端档案回填表单 */
function fillForm(): void {
  const p = persona.data?.profile
  if (!p) return
  form.name = p.name ?? ''
  form.birthday = p.birthday ?? ''
  form.likes = (p.likes ?? []).join(',')
  form.dislikes = (p.dislikes ?? []).join(',')
  form.fears = (p.fears ?? []).join(',')
  form.recent_events = (p.recent_events ?? []).join(',')
}

function showNotice(msg: string): void {
  notice.value = msg
  window.clearTimeout(noticeTimer)
  noticeTimer = window.setTimeout(() => {
    notice.value = ''
  }, 3000)
}

/** 保存档案：只提交非空字段 */
async function save(): Promise<void> {
  busy.value = true
  error.value = ''
  try {
    const payload: PersonaUpdate = {}
    if (form.name.trim()) payload.name = form.name.trim()
    if (form.birthday) payload.birthday = form.birthday
    if (form.likes.trim()) payload.likes = form.likes.trim()
    if (form.dislikes.trim()) payload.dislikes = form.dislikes.trim()
    if (form.fears.trim()) payload.fears = form.fears.trim()
    if (form.recent_events.trim()) payload.recent_events = form.recent_events.trim()
    await persona.save(payload)
    fillForm()
    showNotice('希亚记住了 ✨')
  } catch (err) {
    error.value = `保存失败：${extractErrorMessage(err)}`
  } finally {
    busy.value = false
  }
}

/** 重置好感度（需确认） */
async function doResetAffinity(): Promise<void> {
  if (!window.confirm('确定要重置与希亚的好感度吗？这段感情要重新开始培养了！')) return
  error.value = ''
  try {
    await persona.reset()
    await chat.init()
    showNotice('好感度已重置 🔄')
  } catch (err) {
    error.value = `重置失败：${extractErrorMessage(err)}`
  }
}

/** 清空聊天记录（需确认） */
async function doClearHistory(): Promise<void> {
  if (!window.confirm('确定要清空所有聊天记录吗？希亚会忘记你们聊过的内容！')) return
  error.value = ''
  try {
    await chat.clear()
    showNotice('聊天记录已清空 🧹')
  } catch (err) {
    error.value = `清空失败：${extractErrorMessage(err)}`
  }
}
</script>

<template>
  <div class="settings-page">
    <div class="settings-card">
      <header class="settings-head">
        <router-link class="back-btn" to="/">← 返回</router-link>
        <h1>⚙️ 设置</h1>
      </header>

      <Transition name="fade">
        <div v-if="notice" class="notice">✅ {{ notice }}</div>
      </Transition>
      <p v-if="error" class="error">⚠️ {{ error }}</p>

      <!-- 用户画像 -->
      <section class="section">
        <h2>👤 用户画像</h2>
        <p class="hint">这些是希亚认识的你，改完她会重新记住。</p>

        <label class="field">
          <span>怎么称呼你</span>
          <input v-model="form.name" type="text" class="input" placeholder="比如：阿宇" />
        </label>

        <label class="field">
          <span>你的生日</span>
          <input v-model="form.birthday" type="date" class="input" />
        </label>

        <label class="field">
          <span>喜欢的东西 <i>（逗号分隔）</i></span>
          <input v-model="form.likes" type="text" class="input" placeholder="猫, 打游戏, 火锅" />
        </label>

        <label class="field">
          <span>不喜欢的东西 <i>（逗号分隔）</i></span>
          <input v-model="form.dislikes" type="text" class="input" placeholder="香菜, 加班" />
        </label>

        <label class="field">
          <span>害怕的东西 <i>（逗号分隔）</i></span>
          <input v-model="form.fears" type="text" class="input" placeholder="打雷, 恐怖片" />
        </label>

        <label class="field">
          <span>最近发生的事 <i>（逗号分隔）</i></span>
          <input
            v-model="form.recent_events"
            type="text"
            class="input"
            placeholder="项目上线了, 准备搬家"
          />
        </label>

        <button class="btn btn--primary save-btn" type="button" :disabled="persona.saving" @click="save">
          {{ persona.saving ? '保存中…' : '保存' }}
        </button>
      </section>

      <!-- 目标列表（只读） -->
      <section class="section">
        <h2>🎯 希亚的小目标</h2>
        <p v-if="persona.goals.length === 0" class="hint">暂时没有目标。</p>
        <ul class="goal-list">
          <li v-for="g in persona.goals" :key="g.id" class="goal-item">
            <span class="goal-status">{{ g.status }}</span>
            <span class="goal-desc">{{ g.description }}</span>
            <span class="goal-cd">冷却 {{ g.cooldown_days }} 天</span>
          </li>
        </ul>
      </section>

      <!-- 调试区 -->
      <section class="section section--debug">
        <h2>🛠 调试</h2>
        <p class="hint">危险操作，点了就没有回头路啦。</p>
        <div class="debug-btns">
          <button class="btn btn--danger" type="button" @click="doResetAffinity">重置好感度</button>
          <button class="btn btn--danger" type="button" @click="doClearHistory">清空聊天记录</button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  min-height: 100dvh;
  padding: 24px 16px;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.settings-card {
  width: min(640px, 100%);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 22px;
  box-shadow: var(--shadow);
  padding: 24px;
}

.settings-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.settings-head h1 {
  margin: 0;
  font-size: 20px;
  color: var(--text);
}

.back-btn {
  padding: 6px 12px;
  border-radius: 12px;
  background: var(--card-soft);
  color: var(--text-soft);
  font-size: 13px;
  text-decoration: none;
  border: 1px solid var(--border);
}

.back-btn:hover {
  color: var(--primary);
}

.notice {
  padding: 8px 14px;
  border-radius: 12px;
  background: var(--primary-soft-bg);
  color: var(--primary);
  font-size: 13px;
  margin-bottom: 12px;
}

.error {
  padding: 8px 14px;
  border-radius: 12px;
  background: #ffe3ea;
  color: #c2185b;
  font-size: 13px;
  margin-bottom: 12px;
}

html.night .error {
  background: rgba(244, 67, 54, 0.15);
  color: #ef9a9a;
}

.section {
  padding: 16px 0;
  border-top: 1px dashed var(--border);
}

.section h2 {
  margin: 0 0 6px;
  font-size: 15px;
  color: var(--text);
}

.hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--text-soft);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 12px;
}

.field span {
  font-size: 12.5px;
  color: var(--text);
}

.field i {
  color: var(--text-soft);
  font-style: normal;
  font-size: 11.5px;
}

.save-btn {
  margin-top: 4px;
  width: 100%;
}

.goal-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.goal-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 12px;
  background: var(--card-soft);
  border: 1px solid var(--border);
  font-size: 12.5px;
}

.goal-status {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--primary-soft-bg);
  color: var(--primary);
  font-size: 11px;
}

.goal-desc {
  flex: 1;
  color: var(--text);
}

.goal-cd {
  flex-shrink: 0;
  color: var(--text-soft);
  font-size: 11px;
}

.section--debug {
  border-top: 1px solid var(--border);
}

.debug-btns {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.btn--danger {
  background: transparent;
  border: 1px solid #e57373;
  color: #e57373;
}

.btn--danger:hover {
  background: rgba(229, 115, 115, 0.1);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
