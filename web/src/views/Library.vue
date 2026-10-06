<template>
  <div>
    <h1 style="margin-bottom:16px">🎵 歌词库</h1>

    <div class="card" style="margin-bottom:22px">
      <h3 style="margin-bottom:12px">➕ 添加歌词</h3>

      <div style="display:flex; gap:8px; margin-bottom:14px">
        <button class="btn sm" :class="{ primary: mode === 'search' }" @click="mode = 'search'">🔍 在线搜索</button>
        <button class="btn sm" :class="{ primary: mode === 'paste' }" @click="mode = 'paste'">📋 粘贴歌词</button>
      </div>

      <template v-if="mode === 'search'">
        <div style="display:flex; gap:10px">
          <input class="input" v-model="query" placeholder="歌名 歌手，例: Yesterday Once More" @keyup.enter="search" />
          <button class="btn primary" @click="search" :disabled="searching">
            <span v-if="searching" class="spin" /> 搜索
          </button>
        </div>
        <p v-if="searchErr" class="muted" style="color:#ff6b81; margin-top:8px">{{ searchErr }}</p>
        <div v-if="tracks.length" style="margin-top:12px">
          <div v-for="(t, i) in tracks" :key="i"
               style="display:flex; justify-content:space-between; align-items:center; padding:9px 12px; border-radius:10px; cursor:pointer"
               class="track-row" @click="importTrack(t)">
            <span>
              <b>{{ t.track_name }}</b>
              <span class="muted"> — {{ t.artist_name }}</span>
              <span v-if="!t.has_lyrics" class="tag plain" style="margin-left:8px">⚠️ 无歌词</span>
            </span>
            <span class="btn sm primary">导入</span>
          </div>
        </div>
      </template>

      <template v-else>
        <div style="display:flex; gap:10px; margin-bottom:10px">
          <input class="input" v-model="pTitle" placeholder="歌名 *" style="flex:1" />
          <input class="input" v-model="pArtist" placeholder="歌手" style="flex:1" />
        </div>
        <textarea class="input" v-model="pLyrics" rows="7" placeholder="粘贴完整英文歌词…"></textarea>
      </template>

      <div style="margin-top:14px">
        <div class="muted" style="font-size:12px; margin-bottom:6px">生成栏目（逐句翻译与行内标注始终生成；需先在设置页配置 Kimi Key）</div>
        <label v-for="s in SECTIONS" :key="s.key" style="margin-right:16px; cursor:pointer; font-size:13.5px">
          <input type="checkbox" v-model="sections[s.key]" /> {{ s.label }}
        </label>
      </div>
      <button v-if="mode === 'paste'" class="btn primary" style="margin-top:14px" @click="importPaste" :disabled="busy">
        <span v-if="busy" class="spin" /> 分析并添加
      </button>
    </div>

    <div v-for="s in songs" :key="s.id" class="card song-row" style="margin-bottom:12px; display:flex; align-items:center; cursor:pointer"
         @click="$router.push(`/song/${s.id}`)">
      <div style="flex:1">
        <b>{{ s.title }}</b> <span class="muted">— {{ s.artist || '未知歌手' }}</span>
        <div class="muted" style="font-size:12px; margin-top:4px">
          {{ s.created_at }} · 收藏 {{ s.wb_cnt }} 词
        </div>
      </div>
      <button class="btn sm danger" @click.stop="del(s)">删除</button>
    </div>
    <p v-if="!songs.length" class="muted" style="text-align:center; padding:30px 0">还没有歌曲，先添加一首吧</p>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, inject } from 'vue'
import { api } from '../api'
import { useRouter } from 'vue-router'

const SECTIONS = [
  { key: 'vocab', label: '词汇汇总表' },
  { key: 'sentences', label: '长难句解析' },
  { key: 'collocations', label: '固定搭配' },
  { key: 'writing', label: '写作仿写' },
]

const router = useRouter()
const notify = inject('notify')

const mode = ref('search')
const query = ref('')
const tracks = ref([])
const searching = ref(false)
const searchErr = ref('')
const pTitle = ref(''), pArtist = ref(''), pLyrics = ref('')
const busy = ref(false)
const songs = ref([])
const sections = reactive({ vocab: true, sentences: true, collocations: true, writing: false })

onMounted(load)

async function load() {
  songs.value = await api.get('/api/songs')
}

async function search() {
  if (!query.value.trim()) return
  searching.value = true
  searchErr.value = ''
  tracks.value = []
  try {
    const r = await api.post('/api/lyrics/search', { query: query.value })
    tracks.value = r.tracks
    if (!r.tracks.length) searchErr.value = '没有找到相关歌曲，可换关键词或改用粘贴歌词'
  } catch (e) {
    searchErr.value = e.message
  }
  searching.value = false
}

async function importTrack(t) {
  busy.value = true
  const r = await api.post('/api/lyrics/fetch', {
    track_name: t.track_name, artist_name: t.artist_name, duration: t.duration,
  })
  busy.value = false
  if (!r.found) { notify('该结果没有歌词，换一个试试'); return }
  const created = await api.post('/api/songs', {
    title: t.track_name, artist: t.artist_name, lyrics: r.lyrics,
    source: 'search', sections: { ...sections },
  })
  notify('已添加，AI 分析中…')
  router.push(`/song/${created.id}?job=${created.job}`)
}

async function importPaste() {
  if (!pLyrics.value.trim() || !pTitle.value.trim()) { notify('请填写歌名和歌词'); return }
  busy.value = true
  const created = await api.post('/api/songs', {
    title: pTitle.value, artist: pArtist.value, lyrics: pLyrics.value,
    source: 'paste', sections: { ...sections },
  })
  busy.value = false
  notify('已添加，AI 分析中…')
  router.push(`/song/${created.id}?job=${created.job}`)
}

async function del(s) {
  if (!confirm(`删除《${s.title}》？生词本中收藏的词会保留。`)) return
  await api.del(`/api/songs/${s.id}`)
  load()
}
</script>

<style scoped>
.track-row:hover { background: var(--card); }
.song-row:hover { border-color: var(--accent); }
</style>
