<template>
  <div>
    <h1 style="margin-bottom:16px">🃏 句卡 & 知识点</h1>

    <h3 style="margin:6px 0 12px">歌词句卡 <span class="muted" style="font-size:12.5px">（复习时中译英默写）</span></h3>
    <div v-for="c in sentences" :key="c.id" class="card" style="margin-bottom:10px; padding:14px 18px">
      <div style="display:flex; align-items:center; gap:12px">
        <div style="flex:1">
          <b>{{ c.en }}</b>
          <p class="muted" style="font-size:12.5px; margin-top:4px">{{ c.zh }}</p>
          <p class="muted" style="font-size:11.5px; margin-top:4px">♫ {{ c.song_title }}{{ c.song_artist ? ' - ' + c.song_artist : '' }}</p>
        </div>
        <span v-if="c.next_date" class="tag plain">{{ c.next_date }} 复习</span>
        <button class="btn sm danger" @click="delSentence(c)">删除</button>
      </div>
    </div>
    <p v-if="!sentences.length" class="muted" style="padding:10px 0 24px">还没有句卡，在歌词阅读页点 ＋句 收藏</p>

    <h3 style="margin:22px 0 12px">知识点卡 <span class="muted" style="font-size:12.5px">（语法/固定搭配，进入每日复习）</span></h3>
    <div v-for="k in knowledges" :key="k.id" class="card" style="margin-bottom:10px; padding:14px 18px">
      <div style="display:flex; align-items:center; gap:12px">
        <div style="flex:1">
          <span class="tag" :class="k.kind === 'grammar' ? 'cet6' : 'ky'">{{ k.kind === 'grammar' ? '语法' : '搭配' }}</span>
          <b style="margin-left:8px">{{ k.title }}</b>
          <p v-if="k.content" class="muted" style="font-size:12.5px; margin-top:4px">{{ k.content }}</p>
          <p v-if="k.example_en" style="font-size:12.5px; margin-top:4px">{{ k.example_en }}</p>
        </div>
        <span v-if="k.next_date" class="tag plain">{{ k.next_date }} 复习</span>
        <button class="btn sm danger" @click="delKnowledge(k)">删除</button>
      </div>
    </div>
    <p v-if="!knowledges.length" class="muted" style="padding:10px 0">在分析栏目里点击"收藏知识点"添加</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const sentences = ref([])
const knowledges = ref([])

async function load() {
  sentences.value = await api.get('/api/sentence-cards')
  knowledges.value = await api.get('/api/knowledge-cards')
}
async function delSentence(c) {
  if (!confirm('删除该句卡？')) return
  await api.del(`/api/sentence-cards/${c.id}`)
  load()
}
async function delKnowledge(k) {
  if (!confirm(`删除知识点「${k.title}」？`)) return
  await api.del(`/api/knowledge-cards/${k.id}`)
  load()
}
onMounted(load)
</script>
