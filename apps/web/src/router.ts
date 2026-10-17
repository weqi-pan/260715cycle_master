import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import GamePlay from './views/GamePlay.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/play', component: GamePlay },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
