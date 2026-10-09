<script setup lang="ts">
import { ref } from 'vue'
import { searchChat } from '@/api/chat'
import { extractErrorMessage } from '@/api/http'
import type { SearchResult } from '@/api/types'
import { todayStr } from '@/utils/format'

// 默认搜索最近 7 天
function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

const start = ref(daysAgo(7))
const end = ref(todayStr())
const keyword = ref('')
const results = ref<SearchResult[]>([])
const searched = ref(false)
const loading = ref(false)
const error = ref('')

async function doSearch(): Promise<void> {
  if (!keyword.value.trim()) return
  loading.value = true
  error.value = ''
  try {
    results.value = await searchChat(start.value, end.value, keyword.value.trim())
    searched.value = true
  } catch (err) {
    error.value = extractErrorMessage(err)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="panel search">
    <h3 class="panel-title">🔍 聊天记录搜索</h3>
    <div class="search__form">
      <div class="search__dates">
        <input v-model="start" type="date" class="input" aria-label="开始日期" />
        <span>→</span>
        <input v-model="end" type="date" class="input" aria-label="结束日期" />
      </div>
      <input
        v-model="keyword"
        class="input"
        type="text"
        placeholder="关键词，比如「想我了吗」"
        @keyup.enter="doSearch"
      />
      <button class="btn btn--primary" type="button" :disabled="loading" @click="doSearch">
        {{ loading ? '搜索中…' : '搜索' }}
      </button>
    </div>

    <p v-if="error" class="search__error">⚠️ {{ error }}</p>
    <p v-else-if="searched && results.length === 0" class="panel-empty">
      这段时间没有找到相关回忆～
    </p>

    <ul v-if="results.length" class="search__list">
      <li v-for="(item, i) in results" :key="i" class="search__item">
        <span class="search__time">🕐 {{ item.time }}</span>
        <p class="search__line search__line--user"><b>你：</b>{{ item.user }}</p>
        <p class="search__line"><b>希亚：</b>{{ item.assistant }}</p>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.search__form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.search__dates {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-soft);
  font-size: 12px;
}

.search__dates .input {
  flex: 1;
  min-width: 0;
}

.search__error {
  margin: 8px 0 0;
  font-size: 12.5px;
  color: #d81b60;
}

.search__list {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 320px;
  overflow-y: auto;
}

.search__item {
  padding: 8px 10px;
  border-radius: 12px;
  background: var(--card-soft);
  border: 1px solid var(--border);
}

.search__time {
  font-size: 11px;
  color: var(--text-soft);
}

.search__line {
  margin: 4px 0 0;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text);
}

.search__line--user {
  color: var(--text-soft);
}

.search__line b {
  color: var(--primary);
  font-weight: 600;
}
</style>
