<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { extractErrorMessage } from '@/api/http'
import type { PersonaUpdate } from '@/api/types'
import { useChatStore } from '@/stores/chat'
import { usePersonaStore } from '@/stores/persona'
import { useUiStore } from '@/stores/ui'
import { storeToRefs } from 'pinia'

const persona = usePersonaStore()
const chat = useChatStore()
const ui = useUiStore()
const { enableCritique } = storeToRefs(ui)

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
  <Teleport to="body">
    <Transition name="slide" appear>
      <div class="settings-wrap">
        <!-- 点遮罩关闭 -->
        <div class="settings-mask" @click="ui.closeOverlay()"></div>

        <aside class="settings-drawer">
          <header class="drawer-head">
            <h2>⚙️ 设置</h2>
            <button class="close-btn" type="button" title="关闭（Esc）" @click="ui.closeOverlay()">
              ✕
            </button>
          </header>

          <div class="drawer-scroll">
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

              <button
                class="btn btn--primary save-btn"
                type="button"
                :disabled="persona.saving"
                @click="save"
              >
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

            <!-- 人格自检开关（原侧边栏收编至此） -->
            <section class="section">
              <h2>🪞 人格自检</h2>
              <label class="critique-row">
                <span>让希亚每句话后自我反省，回复更走心（略慢）</span>
                <input
                  :checked="enableCritique"
                  type="checkbox"
                  class="critique-switch"
                  @change="ui.toggleCritique"
                />
              </label>
            </section>

            <!-- 调试区 -->
            <section class="section section--debug">
              <h2>🛠 调试</h2>
              <p class="hint">危险操作，点了就没有回头路啦。</p>
              <div class="debug-btns">
                <button class="btn btn--danger" type="button" @click="doResetAffinity">
                  重置好感度
                </button>
                <button class="btn btn--danger" type="button" @click="doClearHistory">
                  清空聊天记录
                </button>
              </div>
            </section>
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.settings-wrap {
  position: fixed;
  inset: 0;
  z-index: 40;
}

.settings-mask {
  position: absolute;
  inset: 0;
  background: rgba(10, 8, 16, 0.45);
  backdrop-filter: blur(4px);
}

.settings-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(400px, 92vw);
  background: var(--card);
  border-left: 1px solid var(--border);
  box-shadow: -8px 0 30px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
}

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
}

.drawer-head h2 {
  margin: 0;
  font-size: 16px;
  color: var(--text);
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-soft);
  font-size: 15px;
  cursor: pointer;
}

.close-btn:hover {
  background: var(--primary-soft-bg);
  color: var(--primary);
}

.drawer-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px calc(16px + env(safe-area-inset-bottom));
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

.critique-row {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12.5px;
  color: var(--text);
  cursor: pointer;
}

.critique-switch {
  width: 18px;
  height: 18px;
  accent-color: var(--primary);
  cursor: pointer;
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

/* ---- 过渡：右侧滑入滑出 ---- */
.slide-enter-active,
.slide-leave-active {
  transition: opacity 0.25s ease;
}

.slide-enter-active .settings-drawer,
.slide-leave-active .settings-drawer {
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
}

.slide-enter-from .settings-drawer,
.slide-leave-to .settings-drawer {
  transform: translateX(100%);
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
