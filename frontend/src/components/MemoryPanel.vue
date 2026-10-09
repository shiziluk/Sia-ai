<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { extractErrorMessage } from '@/api/http'
import { useMemoriesStore } from '@/stores/memories'

const store = useMemoriesStore()
const draft = ref('')
const adding = ref(false)
const error = ref('')

onMounted(() => {
  void store.load()
})

async function submit(): Promise<void> {
  const text = draft.value.trim()
  if (!text || adding.value) return
  adding.value = true
  error.value = ''
  try {
    await store.add(text)
    draft.value = ''
  } catch (err) {
    error.value = extractErrorMessage(err)
  } finally {
    adding.value = false
  }
}
</script>

<template>
  <section class="panel memory">
    <h3 class="panel-title">🧠 记忆小本本（{{ store.count }}）</h3>

    <div class="memory__add">
      <input
        v-model="draft"
        class="input"
        type="text"
        placeholder="偷偷告诉她一件想被记住的事…"
        @keyup.enter="submit"
      />
      <button class="btn btn--primary" type="button" :disabled="adding || !draft.trim()" @click="submit">
        添加
      </button>
    </div>
    <p v-if="error" class="memory__error">⚠️ {{ error }}</p>

    <p v-if="!store.loading && store.items.length === 0" class="panel-empty">
      希亚的小本本还是空白的，和她说说话吧～
    </p>

    <ul v-else class="memory__list">
      <li v-for="(item, i) in store.items" :key="i" class="memory__item">🌸 {{ item }}</li>
    </ul>
  </section>
</template>

<style scoped>
.memory__add {
  display: flex;
  gap: 8px;
}

.memory__add .input {
  flex: 1;
  min-width: 0;
}

.memory__error {
  margin: 8px 0 0;
  font-size: 12.5px;
  color: #d81b60;
}

.memory__list {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 260px;
  overflow-y: auto;
}

.memory__item {
  padding: 8px 10px;
  border-radius: 12px;
  background: var(--card-soft);
  border: 1px solid var(--border);
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text);
}
</style>
