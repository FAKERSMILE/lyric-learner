<template>
  <div>
    <h1 style="margin-bottom:6px">🔄 今日复习</h1>
    <p class="muted" style="margin-bottom:20px">{{ today }} · 依据艾宾浩斯记忆曲线安排</p>

    <!-- 完成态 -->
    <div v-if="finished" class="card" style="text-align:center; padding:50px 20px">
      <div style="font-size:52px">🎉</div>
      <h2 style="margin:12px 0 6px">今日复习完成</h2>
      <p class="muted">共 {{ total }} 项 · 记得 {{ cnt.remember }} · 模糊 {{ cnt.fuzzy }} · 不会 {{ cnt.forget }}</p>
      <button class="btn primary" style="margin-top:18px" @click="$router.push('/library')">去学习新歌词</button>
    </div>

    <!-- 空态 -->
    <div v-else-if="!queue.length" class="card" style="text-align:center; padding:50px 20px">
      <div style="font-size:52px">☕</div>
      <h2 style="margin:12px 0 6px">今日没有到期的复习</h2>
      <p class="muted">收藏新的生词或句卡后，明天会出现在这里</p>
      <button class="btn primary" style="margin-top:18px" @click="$router.push('/library')">去歌词库</button>
    </div>

    <!-- 答题 -->
    <div v-else>
      <div class="progress-track" style="margin-bottom:18px">
        <div class="progress-fill" :style="{ width: (done / total * 100) + '%' }" />
      </div>
      <p class="muted" style="font-size:12.5px; margin-bottom:14px">
        第 {{ done + 1 }} / {{ total }} 项 · {{ typeLabel }}
        <template v-if="cur.song_title"> · {{ cur.song_title }}</template>
      </p>

      <div class="card" style="min-height:220px; display:flex; flex-direction:column; justify-content:center">
        <!-- 歌词挖空 -->
        <template v-if="cur._t === 'word'">
          <p style="font-size:19px; line-height:2">
            {{ cur._before }}
            <span class="blank">{{ revealed ? cur.word : (typed || '____') }}</span>
            {{ cur._after }}
          </p>
          <p class="muted" style="font-size:13px; margin-top:10px">
            {{ cur.exam_scope }} · {{ cur.translation || '' }}
          </p>
        </template>

        <!-- 中译英 -->
        <template v-else-if="cur._t === 'sentence'">
          <p style="font-size:19px; line-height:1.9">{{ cur.zh || '（无翻译，请凭记忆默写）' }}</p>
        </template>

        <!-- 知识点 -->
        <template v-else>
          <p style="font-size:18px"><b>{{ cur.title }}</b></p>
          <p v-if="cur.content" class="muted" style="margin-top:8px">{{ cur.content }}</p>
          <p v-if="cur.example_en" style="margin-top:10px">{{ cur.example_en }}</p>
          <p v-if="cur.example_zh" class="muted" style="margin-top:4px">{{ cur.example_zh }}</p>
        </template>

        <!-- 输入与判定 -->
        <div v-if="cur._t !== 'knowledge' && !revealed" style="display:flex; gap:10px; margin-top:22px">
          <input class="input" v-model="typed" :placeholder="cur._t === 'word' ? '填入空缺的单词' : '默写英文原句（忽略大小写/标点/词形）'"
                 @keyup.enter="check" ref="inputEl" autocomplete="off" />
          <button class="btn primary" @click="check">检查</button>
        </div>
        <template v-if="revealed">
          <p v-if="cur._t === 'sentence'" style="margin-top:16px">
            <b>原句：</b>{{ cur.en }}
            <template v-if="sentScore !== null">
              <span class="tag" :class="sentScore >= 0.8 ? 'cet4' : 'plain'" style="margin-left:8px">匹配度 {{ Math.round(sentScore * 100) }}%</span>
            </template>
          </p>
          <p v-else-if="cur._t === 'word'" class="muted" style="margin-top:14px">
            答案：<b style="color:var(--accent2)">{{ cur.word }}</b>
            <span v-if="checkPass" class="tag cet4" style="margin-left:8px">✓ 正确</span>
            <span v-else class="tag plain" style="margin-left:8px">再看看</span>
          </p>
          <div class="fb-btns">
            <button class="btn fb-remember" @click="answer('remember')">😊 记得</button>
            <button class="btn fb-fuzzy" @click="answer('fuzzy')">😐 模糊</button>
            <button class="btn fb-forget" @click="answer('forget')">😵 不会</button>
          </div>
        </template>
      </div>
      <div style="text-align:right; margin-top:10px">
        <button class="btn sm ghost" @click="skip">跳过这项</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, inject } from 'vue'
import { api } from '../api'

const emit = defineEmits(['due-changed'])
const notify = inject('notify')

const today = new Date().toISOString().slice(0, 10)
const queue = ref([])
const idx = ref(0)
const typed = ref('')
const revealed = ref(false)
const checkPass = ref(false)
const sentScore = ref(null)
const cnt = reactive({ remember: 0, fuzzy: 0, forget: 0 })
const inputEl = ref()

const total = computed(() => queue.value.length)
const done = computed(() => idx.value)
const finished = computed(() => total.value > 0 && idx.value >= total.value)
const cur = computed(() => queue.value[idx.value] || {})
const typeLabel = computed(() =>
  ({ word: '歌词挖空', sentence: '中译英默写', knowledge: '知识点回顾' }[cur.value._t] || ''))

function buildBlank(item) {
  // 在原句中找到该词的变形位置并挖空
  const line = item.source_line || ''
  const re = /[A-Za-z][A-Za-z']*/g
  let m, found = false
  const stem = item.word.slice(0, Math.max(4, item.word.length - 2)).toLowerCase()
  while ((m = re.exec(line))) {
    const t = m[0].toLowerCase()
    if (t === item.word || t.startsWith(stem) || item.word.startsWith(t.slice(0, Math.max(4, t.length - 2)))) {
      item._before = line.slice(0, m.index)
      item._after = line.slice(m.index + m[0].length)
      found = true
      break
    }
  }
  if (!found) { item._before = line; item._after = '' }
}

function next() {
  typed.value = ''
  revealed.value = false
  checkPass.value = false
  sentScore.value = null
  idx.value++
  if (!finished.value && cur.value._t !== 'knowledge') nextTick(() => inputEl.value?.focus())
}

function skip() {
  next()
}

async function check() {
  if (!typed.value.trim()) return
  if (cur.value._t === 'word') {
    const r = await api.post('/api/review/check', { typed: typed.value, target: cur.value.word, mode: 'word' })
    checkPass.value = r.pass
  } else {
    const r = await api.post('/api/review/check', { typed: typed.value, target: cur.value.en, mode: 'sentence' })
    sentScore.value = r.score
    checkPass.value = r.pass
  }
  revealed.value = true
}

async function answer(result) {
  cnt[result]++
  await api.post('/api/review/answer', {
    card_type: cur.value._t, card_id: cur.value.id, result,
  })
  next()
}

onMounted(async () => {
  const t = await api.get('/api/review/today')
  today.value = t.date
  const q = []
  for (const w of t.word) q.push({ ...w, _t: 'word' })
  for (const s of t.sentence) q.push({ ...s, _t: 'sentence' })
  for (const k of t.knowledge) q.push({ ...k, _t: 'knowledge' })
  queue.value = q
  queue.value.forEach(buildBlankOf)
  emit('due-changed', q.length)
  nextTick(() => inputEl.value?.focus())
})

function buildBlankOf(item) {
  if (item._t === 'word') buildBlank(item)
}
</script>
