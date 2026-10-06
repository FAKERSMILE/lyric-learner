<template>
  <div>
    <h1 style="margin-bottom:16px">⭐ 生词本</h1>

    <div style="display:flex; gap:8px; margin-bottom:14px">
      <button class="btn sm" :class="{ primary: filter === 'active' }" @click="filter = 'active'">未掌握</button>
      <button class="btn sm" :class="{ primary: filter === 'mastered' }" @click="filter = 'mastered'">已掌握</button>
      <button class="btn sm" :class="{ primary: filter === 'all' }" @click="filter = 'all'">全部</button>
      <span class="spacer" style="flex:1" />
      <span class="muted" style="font-size:12.5px; align-self:center">{{ list.length }} 词 · 艾宾浩斯循环复习直到掌握</span>
    </div>

    <div v-for="w in list" :key="w.id" class="card" style="margin-bottom:10px; padding:14px 18px">
      <div style="display:flex; align-items:center; gap:12px">
        <div style="flex:1">
          <b style="font-size:16px">{{ w.word }}</b>
          <span class="muted" style="margin-left:8px; font-size:12.5px">{{ w.phonetic }}</span>
          <span class="tag plain" style="margin-left:8px">{{ w.exam_scope }}</span>
          <span v-if="w.next_date" class="tag" :class="dueClass(w)">{{ dueLabel(w) }}</span>
        </div>
        <button v-if="w.status !== 'mastered'" class="btn sm" @click="master(w)">✓ 我会了</button>
        <button v-else class="btn sm ghost" @click="unmaster(w)">恢复复习</button>
        <button class="btn sm danger" @click="del(w)">删除</button>
      </div>
      <p class="muted" style="font-size:12.5px; margin-top:6px">{{ w.translation }}</p>
      <p v-if="w.source_line" class="muted" style="font-size:12.5px; font-style:italic">♫ {{ w.source_line }}</p>
    </div>
    <p v-if="!list.length" class="muted" style="text-align:center; padding:30px 0">这里还空着，去歌词里点词收藏吧</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { api } from '../api'

const notify = inject('notify')
const filter = ref('active')
const all = ref([])

const list = computed(() =>
  all.value.filter((w) => filter.value === 'all' || w.status === filter.value))

const today = new Date().toISOString().slice(0, 10)

function dueLabel(w) {
  if (!w.next_date) return '新词'
  if (w.next_date <= today) return '今日待复习'
  return `${w.next_date} 复习`
}
function dueClass(w) {
  return w.next_date && w.next_date <= today ? 'ky' : 'plain'
}

async function load() { all.value = await api.get('/api/wordbook?include_mastered=true') }
async function master(w) {
  await api.post(`/api/wordbook/${w.id}/master`)
  notify(`「${w.word}」已标记掌握`)
  load()
}
async function unmaster(w) {
  await api.post(`/api/wordbook/${w.id}/unmaster`)
  load()
}
async function del(w) {
  if (!confirm(`从生词本删除「${w.word}」？`)) return
  await api.del(`/api/wordbook/${w.id}`)
  load()
}
onMounted(load)
</script>
