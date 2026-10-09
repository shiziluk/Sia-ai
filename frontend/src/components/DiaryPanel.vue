<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getDiary } from '@/api/chat'
import type { Diary } from '@/api/types'
import { emotionEmoji } from '@/utils/emoji'
import { todayStr } from '@/utils/format'

const diary = ref<Diary | null>(null)
const loading = ref(false)
const error = ref('')

onMounted(load)

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    diary.value = await getDiary(todayStr())
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

/** 情绪流归一化：兼容字符串或 {emotion} 对象 */
const sequence = computed(() =>
  (diary.value?.emotion_sequence ?? []).map((item) =>
    typeof item === 'string' ? item : (item?.emotion ?? '')
  )
)
</script>

<template>
  <section class="panel diary">
    <h3 class="panel-title">📖 今天的情绪日记</h3>

    <p v-if="loading" class="panel-empty">翻看日记中…</p>
    <p v-else-if="error" class="diary__error">⚠️ {{ error }}</p>

    <template v-else-if="diary">
      <!-- 空日记：后端返回文案 -->
      <p v-if="diary.empty" class="panel-empty">{{ diary.text || '今天还没有日记，多和希亚聊聊吧～' }}</p>

      <template v-else>
        <div class="diary__main">
          <span class="diary__emoji">{{ emotionEmoji(diary.main_emotion) }}</span>
          <div>
            <div class="diary__label">今日主情绪</div>
            <div class="diary__value">{{ diary.main_emotion || '平静' }}</div>
          </div>
        </div>

        <div v-if="sequence.length" class="diary__block">
          <div class="diary__label">情绪流</div>
          <div class="diary__chips">
            <span v-for="(emo, i) in sequence" :key="i" class="diary__chip">
              {{ emotionEmoji(emo) }} {{ emo }}
            </span>
          </div>
        </div>

        <div v-if="diary.keywords?.length" class="diary__block">
          <div class="diary__label">今天聊了什么</div>
          <div class="diary__chips">
            <span v-for="kw in diary.keywords" :key="kw" class="diary__chip diary__chip--kw"># {{ kw }}</span>
          </div>
        </div>

        <div v-if="diary.memories?.length" class="diary__block">
          <div class="diary__label">记住了这些</div>
          <ul class="diary__memories">
            <li v-for="(m, i) in diary.memories" :key="i">🧠 {{ m }}</li>
          </ul>
        </div>

        <div v-if="diary.night_count != null" class="diary__night">
          🌙 今天陪希亚聊到深夜 {{ diary.night_count }} 次
        </div>
      </template>
    </template>
  </section>
</template>

<style scoped>
.diary__error {
  margin: 0;
  font-size: 12.5px;
  color: #d81b60;
}

.diary__main {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--card-soft);
  border: 1px solid var(--border);
}

.diary__emoji {
  font-size: 30px;
}

.diary__label {
  font-size: 11.5px;
  color: var(--text-soft);
  margin-bottom: 2px;
}

.diary__value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.diary__block {
  margin-top: 12px;
}

.diary__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.diary__chip {
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--card-soft);
  border: 1px solid var(--border);
  font-size: 12px;
  color: var(--text);
}

.diary__chip--kw {
  color: var(--primary);
}

.diary__memories {
  list-style: none;
  margin: 6px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12.5px;
  color: var(--text);
}

.diary__night {
  margin-top: 12px;
  font-size: 12.5px;
  color: var(--accent);
}
</style>
