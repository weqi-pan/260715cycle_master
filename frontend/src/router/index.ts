import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/play' },
    {
      path: '/play',
      name: 'play',
      component: () => import('@/views/GamePlay.vue'),
    },
  ],
})

export default router
