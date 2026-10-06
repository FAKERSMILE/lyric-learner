<template>
  <div>
    <transition name="fade">
      <div v-if="word" class="drawer-mask" @click="$emit('close')" />
    </transition>
    <transition name="slide">
      <div v-if="word" class="drawer">
        <div class="head">
          <div>
            <h2 style="display:inline">{{ word.word }}</h2>
            <span class="muted" style="margin-left:10px">{{ word.phonetic }}</span>
            <div style="margin-top:6px">
              <span v-for="t in scopeTags" :key="t" class="tag" :class="tagClass(t)">{{ t }}</span>
            </div>
          </div>
          <button class="btn ghost" @click="$emit('close')">✕</button>
        </div>

        <p v-if="loading" style="margin:16px 0"><span class="spin" /> 查询词典中…</p>
        <template v-else>
          <p style="white-space:pre-wrap; margin:14px 0; line-height:1.8">{{ dict?.translation || '（词库未收录释义）' }}</p>
          <p v-if="dict?.exchange" class="muted" style="font-size:13px; margin-bottom:12px">变形：{{ dict.exchange }}</p>

          <div v-if="$slots.source" class="card" style="padding:12px 16px; margin:10px 0">
            <div class="muted" style="font-size:11px; margin-bottom:4px">歌词原句</div>
            <slot name="source" />
          </div>

          <div style="display:flex; gap:10px; margin-top:16px; flex-wrap:wrap">
            <button class="btn primary" :disabled="collected" @click="collect">
              {{ collected ? '✓ 已在生词本' : '＋ 收藏到生词本' }}
            </button>
            <button class="btn" @click="markKnown">{{ known ? '取消"我会了"' : '我已掌握（不再高亮）' }}</button>
          </div>
        </template>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { api } from '../api'

const props = defineProps({ word: Object, songId: Number })
const emit = defineEmits(['close', 'collected', 'known-changed'])

const dict = ref(null)
const loading = ref(false)
const collected = ref(false)
const known = ref(false)

const scopeTags = computed(() => (props.word?.exam || '').split('/').filter(Boolean))

function tagClass(t) {
  if (t.includes('四级')) return 'cet4'
  if (t.includes('六级')) return 'cet6'
  if (t.includes('考研')) return 'ky'
  if (t) return 'exam'
  return 'plain'
}

watch(() => props.word, async (w) => {
  if (!w) return
  dict.value = null
  collected.value = !!w.in_wordbook
  known.value = !!w.known
  loading.value = true
  try {
    dict.value = await api.get(`/api/dict/${encodeURIComponent(w.word)}`)
    collected.value = dict.value.in_wordbook || collected.value
    known.value = dict.value.known
  } catch { /* 未收录也允许收藏 */ }
  loading.value = false
})

async function collect() {
  await api.post('/api/wordbook', {
    word: props.word.word,
    source_song_id: props.songId || null,
    source_line: props.word.source_line || '',
  })
  collected.value = true
  emit('collected', props.word.word)
}

async function markKnown() {
  await api.post('/api/known-words', { word: props.word.word, known: !known.value })
  known.value = !known.value
  emit('known-changed', { word: props.word.word, known: known.value })
}
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: flex-start; }
</style>
