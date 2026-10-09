import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'stage',
      component: () => import('@/views/StageView.vue')
    },
    {
      // 旧版设置页入口（PWA 缓存/收藏夹）重定向回舞台，防止 404
      path: '/settings',
      redirect: '/'
    }
  ]
})

export default router
