<template>
  <div>
    <h1 style="margin-bottom:16px">⚙️ 设置</h1>

    <div class="card" style="margin-bottom:16px">
      <h3 style="margin-bottom:12px">AI 分析接口（Kimi / 任意 OpenAI 兼容接口）</h3>
      <label class="muted" style="font-size:12.5px">API Key（仅保存在本机）</label>
      <input class="input" v-model="s.kimi_key" type="password" placeholder="sk-..." style="margin:6px 0 14px" />
      <label class="muted" style="font-size:12.5px">接口地址</label>
      <input class="input" v-model="s.base_url" style="margin:6px 0 14px" />
      <label class="muted" style="font-size:12.5px">模型（auto = 按歌词长度自动选 moonshot-v1-8k/32k）</label>
      <input class="input" v-model="s.model" style="margin:6px 0 14px" placeholder="auto / moonshot-v1-8k / ..." />
      <button class="btn primary" @click="save">保存设置</button>
      <span v-if="saved" class="muted" style="margin-left:12px; font-size:13px">✓ 已保存</span>
    </div>

    <div class="card" style="margin-bottom:16px">
      <h3 style="margin-bottom:12px">主题</h3>
      <div style="display:flex; gap:10px">
        <button class="btn" :class="{ primary: s.theme === 'midnight' }" @click="s.theme = 'midnight'">🌙 午夜唱片</button>
        <button class="btn" :class="{ primary: s.theme === 'dashboard' }" @click="s.theme = 'dashboard'">☀️ 学习仪表盘</button>
      </div>
    </div>

    <div class="card">
      <h3 style="margin-bottom:12px">数据备份（本地 SQLite，换电脑需手动迁移）</h3>
      <div style="display:flex; gap:10px; flex-wrap:wrap">
        <button class="btn" @click="exportBackup">⬇ 导出备份 JSON</button>
        <label class="btn" style="cursor:pointer">
          ⬆ 导入备份
          <input type="file" accept=".json" style="display:none" @change="importBackup" />
        </label>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, inject } from 'vue'
import { api } from '../api'

const notify = inject('notify')
const saved = ref(false)
const s = reactive({ kimi_key: '', base_url: 'https://api.moonshot.cn/v1', model: 'auto', theme: 'midnight' })

onMounted(async () => Object.assign(s, await api.get('/api/settings')))

async function save() {
  await api.post('/api/settings', { ...s })
  saved.value = true
  setTimeout(() => (saved.value = false), 2000)
  if (s.theme) {
    document.documentElement.dataset.theme = s.theme
    localStorage.setItem('theme', s.theme)
  }
  notify('设置已保存')
}

async function exportBackup() {
  const data = await api.get('/api/backup')
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `lyric-learner-backup-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

async function importBackup(e) {
  const f = e.target.files[0]
  if (!f) return
  if (!confirm('导入会覆盖同名数据，确认？')) return
  const data = JSON.parse(await f.text())
  await api.post('/api/backup/import', { data })
  notify('导入完成')
  e.target.value = ''
}
</script>
