<template>
  <div v-if="detail">
    <div style="display:flex; align-items:baseline; gap:12px; margin-bottom:4px">
      <h1>{{ song.title }}</h1>
      <span class="muted">{{ song.artist }}</span>
    </div>
    <p class="muted" style="margin-bottom:16px; font-size:13px">
      彩色<b>点线</b>为备考词汇（点击查词/收藏）；点击行尾 ＋句 收藏句卡。
      <template v-if="analyzing"><span class="spin" style="margin-left:8px"></span> AI 分析中…</template>
    </p>

    <!-- 歌词 -->
    <div class="card" style="margin-bottom:20px">
      <div v-for="ln in lines" :key="ln.line_no" class="lyric-line" style="display:flex; align-items:flex-start">
        <div style="flex:1">
          <div>
            <template v-for="(seg, i) in segs(ln)" :key="i">
              <span v-if="seg.type === 'plain'">{{ seg.text }}</span>
              <span v-else class="w" :class="cls(seg.tok)" @click="openWord(seg.tok, ln)">{{ seg.text }}</span>
            </template>
            <button class="btn sm ghost" style="margin-left:8px; opacity:.55" @click="collectLine(ln)">＋句</button>
          </div>
          <span v-if="zhOf(ln.line_no)" class="zh">{{ zhOf(ln.line_no) }}</span>
          <span v-for="(n, i) in notesOf(ln.line_no)" :key="'n' + i" class="note-chip">✎ {{ n }}</span>
        </div>
      </div>
    </div>

    <!-- 可选栏目 -->
    <div style="display:flex; gap:8px; margin-bottom:14px; flex-wrap:wrap; align-items:center">
      <button v-for="s in SECTIONS" :key="s.key" class="btn sm"
              :class="{ primary: tab === s.key }"
              :style="!hasSection(s.key) ? 'opacity:.45' : ''"
              @click="tab = s.key">
        {{ s.label }}<template v-if="hasSection(s.key)"> · {{ (material.sections[s.key] || []).length }}</template>
      </button>
      <span class="spacer" style="flex:1" />
      <details style="position:relative">
        <summary class="btn sm">↻ 补充生成</summary>
        <div class="card" style="position:absolute; right:0; z-index:30; margin-top:6px; min-width:220px">
          <label v-for="s in SECTIONS" :key="s.key" style="display:block; margin:6px 0; font-size:13px; cursor:pointer">
            <input type="checkbox" v-model="reSec[s.key]" /> {{ s.label }}
          </label>
          <button class="btn sm primary" style="margin-top:8px" @click="reanalyze" :disabled="analyzing">
            生成勾选栏目
          </button>
        </div>
      </details>
    </div>

    <!-- 词汇汇总表 -->
    <div v-if="tab === 'vocab' && hasSection('vocab')" class="card" style="overflow-x:auto">
      <table class="tbl">
        <tr><th>单词</th><th>出现原句</th><th>翻译 & 释义</th><th>词根词缀 & 变形</th><th></th></tr>
        <tr v-for="(v, i) in material.sections.vocab" :key="i">
          <td><b>{{ v.word }}</b><br /><span class="tag plain">{{ v.scope }}</span></td>
          <td class="muted">{{ v.sentence }}</td>
          <td>{{ v.sentence_zh }}<br /><span class="muted">{{ v.meaning }}</span></td>
          <td class="muted">{{ v.root }}<br />{{ v.derivatives }}</td>
          <td><button class="btn sm" @click="quickAdd(v.word)">收藏</button></td>
        </tr>
      </table>
    </div>

    <!-- 长难句 -->
    <div v-if="tab === 'sentences' && hasSection('sentences')">
      <div v-for="(s, i) in material.sections.sentences" :key="i" class="card" style="margin-bottom:12px">
        <b>{{ s.sentence }}</b>
        <p class="muted" style="margin:6px 0 10px">{{ s.zh }}</p>
        <p style="font-size:13.5px; line-height:1.9">🔍 {{ s.analysis.split('；').join('\n') }}</p>
        <button class="btn sm" style="margin-top:8px" @click="collectSentenceText(s.sentence, s.zh)">＋ 收藏为句卡</button>
      </div>
    </div>

    <!-- 固定搭配 -->
    <div v-if="tab === 'collocations' && hasSection('collocations')" class="card">
      <table class="tbl">
        <tr><th>搭配</th><th>含义</th><th>可迁移表达</th><th></th></tr>
        <tr v-for="(c, i) in material.sections.collocations" :key="i">
          <td><b>{{ c.phrase }}</b></td>
          <td>{{ c.zh }}</td>
          <td class="muted">{{ c.example }}</td>
          <td>
            <button class="btn sm" @click="addKnowledge('collocation', c.phrase, c.zh, c.example)">收藏知识点</button>
          </td>
        </tr>
      </table>
    </div>

    <!-- 写作仿写 -->
    <div v-if="tab === 'writing' && hasSection('writing')">
      <div v-for="(w, i) in material.sections.writing" :key="i" class="card" style="margin-bottom:12px">
        <span class="tag plain">句型</span> <b>{{ w.pattern }}</b>
        <p style="margin-top:8px">{{ w.example }}</p>
        <p class="muted" style="margin-top:4px">{{ w.zh }}</p>
        <button class="btn sm" style="margin-top:8px" @click="addKnowledge('grammar', w.pattern, '', w.example, w.zh)">收藏知识点</button>
      </div>
    </div>

    <WordDrawer :word="drawerWord" :song-id="song.id"
                @close="drawerWord = null"
                @collected="onCollected"
                @known-changed="onKnownChanged">
      <template #source>
        <span v-if="drawerWord">{{ drawerWord.source_line }}</span>
      </template>
    </WordDrawer>
  </div>
  <p v-else style="text-align:center; padding:60px 0" class="muted"><span class="spin" /> 加载中…</p>
</template>

<script setup>
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import WordDrawer from '../components/WordDrawer.vue'

const SECTIONS = [
  { key: 'vocab', label: '词汇汇总表' },
  { key: 'sentences', label: '长难句解析' },
  { key: 'collocations', label: '固定搭配' },
  { key: 'writing', label: '写作仿写' },
]

const route = useRoute()
const notify = inject('notify')

const detail = ref(null)
const analyzing = ref(false)
const drawerWord = ref(null)
const tab = ref('vocab')
const reSec = reactive({ vocab: true, sentences: true, collocations: true, writing: true })

const song = computed(() => detail.value?.song || {})
const lines = computed(() => detail.value?.lines || [])
const material = computed(() => detail.value?.material || { line_zh: [], sections: {}, sections_done: [] })

function hasSection(key) {
  return (material.value.sections_done || []).includes(key)
}

function segs(ln) {
  const out = []
  let pos = 0
  for (const t of ln.tokens) {
    if (t.start > pos) out.push({ type: 'plain', text: ln.text.slice(pos, t.start) })
    out.push({ type: 'word', text: ln.text.slice(t.start, t.end), tok: t })
    pos = t.end
  }
  if (pos < ln.text.length) out.push({ type: 'plain', text: ln.text.slice(pos) })
  return out
}

function cls(tok) {
  if (tok.known) return 'known'
  const tags = tok.tags || []
  if (tags.includes('ielts') || tags.includes('toefl')) return 'exam'
  if (tags.includes('ky')) return 'ky'
  if (tags.includes('cet6')) return 'cet6'
  if (tags.includes('cet4')) return 'cet4'
  return 'cet4'
}

function zhOf(no) {
  const it = (material.value.line_zh || []).find((x) => x.line_no === no)
  return it?.zh || ''
}

function notesOf(no) {
  const it = (material.value.line_zh || []).find((x) => x.line_no === no)
  if (!it?.note) return []
  return it.note.split(/[；;。]/).filter((s) => s.trim().length > 1).slice(0, 3)
}

function openWord(tok, ln) {
  drawerWord.value = {
    ...tok,
    in_wordbook: tok.in_wordbook,
    source_line: ln.text,
  }
}

async function onCollected(word) {
  for (const ln of lines.value)
    for (const t of ln.tokens)
      if (t.word === word) { t.in_wordbook = true }
  notify(`已收藏「${word}」`)
}

async function onKnownChanged({ word, known }) {
  for (const ln of lines.value)
    for (const t of ln.tokens)
      if (t.word === word) t.known = known
  notify(known ? `「${word}」已标记掌握，不再高亮` : `「${word}」恢复高亮`)
}

async function collectLine(ln) {
  const r = await api.post('/api/sentence-cards', { song_id: song.value.id, line_no: ln.line_no })
  notify(r.ok ? '已收藏句卡' : (r.msg || '已收藏过'))
}

async function collectSentenceText(en, zh) {
  // 找到匹配行号收藏；找不到则直接记到该歌最后一行
  let line_no = null
  for (const ln of lines.value)
    if (ln.text.includes(en.slice(0, 20)) || en.includes(ln.text.slice(0, 20))) { line_no = ln.line_no; break }
  const r = await api.post('/api/sentence-cards', { song_id: song.value.id, line_no: line_no || 1 })
  notify(r.ok ? '已收藏句卡' : (r.msg || '已收藏过'))
}

async function quickAdd(word) {
  await api.post('/api/wordbook', { word, source_song_id: song.value.id })
  onCollected(word)
  notify(`已收藏「${word}」`)
}

async function addKnowledge(kind, title, content = '', example_en = '', example_zh = '') {
  await api.post('/api/knowledge-cards', {
    kind, title, content, example_en, example_zh, source_song_id: song.value.id,
  })
  notify('已收藏知识点卡，进入每日复习')
}

async function reanalyze() {
  analyzing.value = true
  const r = await api.post(`/api/songs/${song.value.id}/analyze`, { sections: { ...reSec } })
  pollJob(r.job)
}

function pollJob(jobId) {
  if (!jobId) { analyzing.value = false; return }
  const timer = setInterval(async () => {
    const st = await api.get(`/api/jobs/${jobId}`)
    if (st.status === 'done' || st.status === 'error') {
      clearInterval(timer)
      analyzing.value = false
      if (st.status === 'error') { notify('分析失败：' + st.error); return }
      detail.value = await api.get(`/api/songs/${route.params.id}`)
      notify('分析完成')
    }
  }, 1500)
}

onMounted(async () => {
  detail.value = await api.get(`/api/songs/${route.params.id}`)
  if (!material.value.sections_done.length) tab.value = ''
  const jobId = route.query.job
  if (jobId) {
    analyzing.value = true
    pollJob(jobId)
  }
})
</script>
