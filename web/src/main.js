import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

import Today from './views/Today.vue'
import Library from './views/Library.vue'
import SongDetail from './views/SongDetail.vue'
import Wordbook from './views/Wordbook.vue'
import Cards from './views/Cards.vue'
import Settings from './views/Settings.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'today', component: Today },
    { path: '/library', name: 'library', component: Library },
    { path: '/song/:id', name: 'song', component: SongDetail },
    { path: '/wordbook', name: 'wordbook', component: Wordbook },
    { path: '/cards', name: 'cards', component: Cards },
    { path: '/settings', name: 'settings', component: Settings },
  ]
})

createApp(App).use(router).mount('#app')
