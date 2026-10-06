<template>
  <div>
    <nav class="topnav">
      <span class="logo">♪ Lyric Learner</span>
      <router-link class="nav-item" to="/">今日复习<sup v-if="dueCount" class="due-badge">{{ dueCount }}</sup></router-link>
      <router-link class="nav-item" to="/library">歌词库</router-link>
      <router-link class="nav-item" to="/wordbook">生词本</router-link>
      <router-link class="nav-item" to="/cards">句卡</router-link>
      <router-link class="nav-item" to="/settings">设置</router-link>
      <span class="spacer" />
      <button class="btn sm ghost" @click="toggleTheme" :title="theme === 'midnight' ? '切换到学习仪表盘' : '切换到午夜唱片'">
        {{ theme === 'midnight' ? '🌙' : '☀️' }}
      </button>
    </nav>
    <main style="max-width: 860px; margin: 0 auto; padding: 26px 20px 80px;">
      <router-view @due-changed="dueCount = $event" />
    </main>
    <transition name="fade">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, provide } from 'vue'
import { api } from './api'

const theme = ref(localStorage.getItem('theme') || 'midnight')
const dueCount = ref(0)
const toast = ref('')
let toastTimer = null

function applyTheme(t) {
  theme.value = t
  document.documentElement.dataset.theme = t
  localStorage.setItem('theme', t)
}

function toggleTheme() {
  applyTheme(theme.value === 'midnight' ? 'dashboard' : 'midnight')
  api.post('/api/settings', { theme: theme.value }).catch(() => {})
}

provide('notify', (msg) => {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2200)
})

onMounted(async () => {
  applyTheme(theme.value)
  try {
    const s = await api.get('/api/settings')
    if (s.theme && s.theme !== theme.value) applyTheme(s.theme)
  } catch { /* ignore */ }
  try {
    const t = await api.get('/api/review/today')
    dueCount.value = t.total
  } catch { /* ignore */ }
})
</script>

<style>
.due-badge {
  background: linear-gradient(135deg, #ff6b81, #ff9f43);
  color: #fff; font-size: 10px; border-radius: 8px;
  padding: 1px 5px; margin-left: 2px; font-weight: 700;
}
</style>
